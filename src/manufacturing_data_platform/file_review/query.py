"""SQL analysis of an integrity-checked version and portable, pinned result export."""
import csv
import io
import json
import sqlite3
import zipfile
from datetime import datetime

from .model import CONTRACT, FIELDS, ReviewError, digest, now, parse_time, quality_counts


def query(payload, stored, latest, equipment=None, tag=None, start=None, end=None):
    rows = payload["rows"]
    if equipment is None:
        equipment = rows[0]["equipment"]
    if tag is None:
        tag = next((r["tag"] for r in rows if r["equipment"] == equipment), None)
    series = next((r for r in rows if r["equipment"] == equipment and r["tag"] == tag), None)
    if series is None:
        raise ReviewError("SERIES", "선택한 설비·태그가 이 결과에 없습니다.")
    bounds = []
    for bound in (start, end):
        if bound is None or bound == "":
            bounds.append(None)
            continue
        # Browser datetime-local may omit seconds; the API accepts this unambiguous filter form.
        if len(bound) == 16:
            bound += ":00"
        if payload["time_basis"] == "utc" and len(bound) in (19, 26):
            bound += "+00:00"
        try:
            normalized, basis = parse_time(bound)
            if basis != payload["time_basis"]:
                raise ValueError()
        except (ValueError, OverflowError):
            raise ReviewError("FILTER_TIME", "조회 시간과 파일의 시간대 표기를 확인해 주세요.") from None
        bounds.append(normalized)
    start, end = bounds
    if start is not None and end is not None and start >= end:
        raise ReviewError("FILTER_RANGE", "종료 시간은 시작 시간보다 뒤여야 합니다.")
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    try:
        db.execute("CREATE TABLE observations(timestamp TEXT,equipment TEXT,tag TEXT,value REAL,unit TEXT,quality TEXT)")
        db.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", (tuple(r[k] for k in FIELDS) for r in rows))
        where = "equipment=? AND tag=?"
        args = [equipment, tag]
        for operator, value in ((">=", start), ("<", end)):
            if value is not None:
                where += f" AND timestamp {operator} ?"
                args.append(value)
        stats = dict(db.execute(f"SELECT COUNT(*) AS count,MIN(value) AS min,MAX(value) AS max FROM observations WHERE {where}", args).fetchone())
        scale = max(abs(stats["min"] or 0), abs(stats["max"] or 0)) or 1
        # Scale before AVG so a series of finite large values cannot overflow the SQL accumulator.
        avg = db.execute(f"SELECT AVG(value / ?) FROM observations WHERE {where}", [scale] + args).fetchone()[0]
        stats["mean"] = None if avg is None else max(-1.0, min(1.0, avg)) * scale
        selected = [dict(r) for r in db.execute(f"SELECT * FROM observations WHERE {where} ORDER BY timestamp", args)]
    finally:
        db.close()
    deltas = [0.0] + [(datetime.fromisoformat(b["timestamp"]) - datetime.fromisoformat(a["timestamp"])).total_seconds()
                      for a, b in zip(selected, selected[1:])]
    stats.update(gap_count=sum(d > 60 for d in deltas), max_gap_seconds=max(deltas), quality_counts=quality_counts(selected))
    indexes = list(range(len(selected))) if len(selected) <= 500 else sorted({i * (len(selected) - 1) // 499 for i in range(500)})
    points, previous = [], 0
    for index in indexes:
        row = selected[index]
        points.append({"timestamp": row["timestamp"], "value": row["value"], "quality": row["quality"],
                       "gap_before": any(d > 60 for d in deltas[previous + 1:index + 1])})
        previous = index
    result = {"version": stored["version"], "latest_status": latest["status"],
              "previous_result": latest["status"] != "ready" or stored["version"] != latest["version"],
              "time_basis": payload["time_basis"], "equipment": equipment, "tag": tag, "unit": series["unit"],
              "filter": {"start": start, "end": end}, "summary": stats, "points": points,
              "displayed_points": len(points), "rows": selected[:100]}
    return result, selected


def export_zip(result, rows, stored):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(FIELDS)
    escaped = 0
    for row in rows:
        values = []
        for field in FIELDS:
            value = row[field]
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
                escaped += 1
            values.append(value)
        writer.writerow(values)
    csv_bytes = output.getvalue().encode("utf-8-sig")
    manifest = {"contract": CONTRACT, "version": result["version"], "source_sha256": stored["source_sha"],
                "source_name": stored["source_name"], "generated_at": now(), "time_basis": result["time_basis"],
                "equipment": result["equipment"], "tag": result["tag"], "unit": result["unit"],
                "filter": result["filter"], "summary": result["summary"], "latest_status": result["latest_status"],
                "previous_result": result["previous_result"], "observations_sha256": digest(csv_bytes),
                "spreadsheet_escape": {"prefix": "'", "escaped_text_cells": escaped},
                "limitations": ["File validation does not certify physical sensor accuracy.",
                                "Unspecified source quality is not Good quality.",
                                "Intervals above 60 seconds are descriptive gaps, not inferred outages.",
                                "Sample mean over selected observations; no interpolation or time weighting."]}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("observations.csv", csv_bytes)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return buffer.getvalue()
