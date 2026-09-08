"""File contract and content identities, independent of transport and storage."""
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone

CONTRACT = "telemetry_file_review_v1"
UPLOAD_BYTES = 8 * 1024 * 1024
MAX_ROWS = 50_000
QUALITIES = ("good", "unspecified", "uncertain", "bad")
FIELDS = ("timestamp", "equipment", "tag", "value", "unit", "quality")


class ReviewError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def quality_counts(rows):
    counts = Counter(row["quality"] for row in rows)
    return {key: counts[key] for key in QUALITIES}


def parse_time(value):
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
        raise ValueError("ISO timestamp with seconds required")
    if re.search(r"[.,]\d{7,}", value):
        raise ValueError("Sub-microsecond precision cannot be retained")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    aware = result.utcoffset() is not None
    if aware:
        result = result.astimezone(timezone.utc)
    return result.isoformat(timespec="microseconds"), "utc" if aware else "unspecified"


def parse_csv(raw):
    issues, rows, seen, units = [], [], set(), {}
    expected, basis, issue_count = 0, None, 0

    def issue(code, message, row=None):
        nonlocal issue_count
        issue_count += 1
        if len(issues) < 20:
            item = {"code": code, "message": message}
            if row is not None:
                item["row"] = row
            issues.append(item)

    if len(raw) > UPLOAD_BYTES:
        raise ReviewError("UPLOAD_LIMIT", "CSV는 8 MiB 이하로 올려 주세요.", 413)
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"rows": [], "time_basis": None, "expected_rows": 0,
                "issues": [{"code": "ENCODING", "message": "UTF-8 CSV 파일이 필요합니다."}], "issue_count": 1}
    # The CSV library's field-size limit also refuses abnormally long quoted fields.
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        header = next(reader, [])
        if len(set(header)) != len(header) or set(header) not in (set(FIELDS), set(FIELDS[:-1])):
            issue("HEADER", "열 이름은 timestamp,equipment,tag,value,unit 및 선택 quality여야 합니다.")
            return {"rows": rows, "time_basis": basis, "expected_rows": 0, "issues": issues, "issue_count": issue_count}
        for number, values in enumerate(reader, 1):
            expected = number
            if number > MAX_ROWS:
                issue("ROW_LIMIT", "한 파일은 50,000개 관측까지 검토할 수 있습니다.")
                break
            if len(values) != len(header):
                issue("COLUMNS", "이 레코드의 열 수가 헤더와 다릅니다.", number)
                continue
            row = dict(zip(header, values))
            quality = row.get("quality", "").strip().lower() or "unspecified"
            if quality not in QUALITIES:
                issue("QUALITY", "quality는 good, unspecified, uncertain, bad 중 하나여야 합니다.", number)
                continue
            try:
                timestamp, row_basis = parse_time(row["timestamp"].strip())
            except (ValueError, OverflowError):
                issue("TIMESTAMP", "초를 포함한 ISO 날짜·시간이 필요합니다.", number)
                continue
            if basis is None:
                basis = row_basis
            elif basis != row_basis:
                issue("TIME_BASIS", "시간대가 있는 값과 없는 값을 한 파일에 섞을 수 없습니다.", number)
            valid_text = True
            for field in ("equipment", "tag", "unit"):
                row[field] = row[field].strip()
                if not row[field] or len(row[field]) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in row[field]):
                    issue("LABEL", "설비·태그·단위는 제어문자 없이 1–128자로 입력해 주세요.", number)
                    valid_text = False
            if not valid_text:
                continue
            try:
                value = None if quality == "bad" and not row["value"].strip() else float(row["value"])
                if value is not None and not math.isfinite(value):
                    raise ValueError()
            except ValueError:
                issue("VALUE", "값은 유한한 숫자여야 합니다.", number)
                continue
            key = row["equipment"], row["tag"], timestamp
            if key in seen:
                issue("DUPLICATE", "같은 설비·태그·시간의 관측이 중복되었습니다.", number)
            seen.add(key)
            series = key[:2]
            if series in units and units[series] != row["unit"]:
                issue("UNIT_CHANGE", "같은 설비·태그에 서로 다른 단위를 사용할 수 없습니다.", number)
            units[series] = row["unit"]
            if quality in ("bad", "uncertain"):
                issue("QUALITY_BLOCK", "제공된 bad 또는 uncertain 품질 때문에 이 파일의 분석 결과를 발행하지 않습니다.", number)
            rows.append({"timestamp": timestamp, "equipment": row["equipment"], "tag": row["tag"],
                         "value": value, "unit": row["unit"], "quality": quality})
    except csv.Error:
        issue("CSV", "CSV 인용부호 또는 필드 길이를 확인해 주세요.")
    if not expected:
        issue("EMPTY", "헤더 뒤에 관측 데이터가 필요합니다.")
    rows.sort(key=lambda r: (r["equipment"], r["tag"], r["timestamp"]))
    return {"rows": rows, "time_basis": basis, "expected_rows": expected, "issues": issues, "issue_count": issue_count}


def payload_for(parsed, source_sha):
    return {"contract": CONTRACT, "source_sha256": source_sha, "time_basis": parsed["time_basis"], "rows": parsed["rows"]}


def current_summary(payload, version, source_name, published_at):
    rows = payload["rows"]
    series = Counter((r["equipment"], r["tag"], r["unit"]) for r in rows)
    return {"version": version, "source_name": source_name, "source_sha256": payload["source_sha256"],
            "rows": len(rows), "time_basis": payload["time_basis"], "published_at": published_at,
            "range": {"start": min(r["timestamp"] for r in rows), "end": max(r["timestamp"] for r in rows)},
            "quality_counts": quality_counts(rows),
            "series": [{"equipment": e, "tag": t, "unit": u, "count": count} for (e, t, u), count in sorted(series.items())]}
