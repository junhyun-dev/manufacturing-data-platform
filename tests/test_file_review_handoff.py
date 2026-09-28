"""Portable review handoff stays pinned to the exported evidence."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from hashlib import sha256
from zipfile import ZipFile

from fastapi.testclient import TestClient

from manufacturing_data_platform.file_review.app import create_app


SERIES = {"equipment": "APU-1", "tag": "temperature"}
LOCAL_CSV = (
    "timestamp,equipment,tag,value,unit\n"
    "2026-01-01T00:00:00,APU-1,temperature,10,degC\n"
    "2026-01-01T00:00:10,APU-1,temperature,20,degC\n"
    "2026-01-01T00:00:20,APU-1,temperature,30,degC\n"
).encode()


def session(client):
    response = client.get("/api/session")
    assert response.status_code == 200, response.text
    return {"X-Review-CSRF": response.json()["csrf_token"]}


def upload(client, headers, raw=LOCAL_CSV, *, name="observations.csv", dataset_id=None):
    route = "/api/datasets" if dataset_id is None else f"/api/datasets/{dataset_id}/replace"
    response = client.post(
        route,
        params={"name": name},
        content=raw,
        headers={**headers, "Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    return response.json()["dataset"]


def exported(client, dataset, *, series=SERIES, version=None, **filters):
    response = client.get(
        f"/api/datasets/{dataset['id']}/export",
        params={**series, **filters, "version": version or dataset["current"]["version"]},
    )
    assert response.status_code == 200, response.text
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == ["review.txt", "observations.csv", "manifest.json"]
        review = archive.read("review.txt").decode("utf-8")
        csv_bytes = archive.read("observations.csv")
        manifest = json.loads(archive.read("manifest.json"))
    return review, csv_bytes, manifest


def test_review_text_matches_independent_half_open_values_and_zip_hashes(tmp_path):
    with TestClient(create_app(tmp_path / "review.sqlite3")) as client:
        headers = session(client)
        dataset = upload(client, headers, name="line-a.csv")
        review, csv_bytes, manifest = exported(
            client,
            dataset,
            start="2026-01-01T00:00:00",
            end="2026-01-01T00:00:20",
        )

    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    values = [float(row["value"]) for row in rows]
    assert values == [10.0, 20.0]
    assert len(values) == 2
    assert sum(values) / len(values) == 15.0
    assert manifest["summary"]["count"] == 2
    assert manifest["summary"]["mean"] == 15.0
    assert manifest["filter"] == {
        "start": "2026-01-01T00:00:00.000000",
        "end": "2026-01-01T00:00:20.000000",
    }
    assert manifest["source_sha256"] == sha256(LOCAL_CSV).hexdigest()
    assert manifest["observations_sha256"] == sha256(csv_bytes).hexdigest()
    for exact_value in (
        manifest["version"],
        manifest["source_sha256"],
        manifest["observations_sha256"],
        manifest["generated_at"],
        manifest["filter"]["start"],
        manifest["filter"]["end"],
    ):
        assert exact_value in review
    assert "관측값 수: 2" in review
    assert "표본 평균: 15.0" in review
    assert "시작 포함, 종료 미포함" in review
    assert "서버가 ZIP을 준비한 시각(UTC)" in review
    assert "관측 시각이 아닙니다" in review


def test_review_identifies_retained_and_explicit_older_source_at_export_time(tmp_path):
    with TestClient(create_app(tmp_path / "review.sqlite3")) as client:
        headers = session(client)
        original = upload(client, headers, name="accepted.csv")
        old_version = original["current"]["version"]
        rejected = upload(
            client,
            headers,
            b"wrong,header\nx,y\n",
            name="rejected.csv",
            dataset_id=original["id"],
        )
        assert rejected["latest"]["status"] == "blocked"
        blocked_review, _, blocked_manifest = exported(client, rejected, version=old_version)
        assert blocked_manifest["source_name"] == "accepted.csv"
        assert blocked_manifest["source_sha256"] == sha256(LOCAL_CSV).hexdigest()
        assert blocked_manifest["latest_status"] == "blocked"
        assert blocked_manifest["previous_result"] is True
        assert "latest_status: blocked" in blocked_review
        assert "previous_result: true" in blocked_review
        assert "보관된 검증 결과" in blocked_review

        newer_raw = LOCAL_CSV.replace(b",30,degC", b",90,degC")
        newer = upload(client, headers, newer_raw, name="newer.csv", dataset_id=original["id"])
        assert newer["latest"]["status"] == "ready"
        older_review, _, older_manifest = exported(client, newer, version=old_version)

    assert older_manifest["version"] == old_version
    assert older_manifest["source_name"] == "accepted.csv"
    assert older_manifest["source_sha256"] == sha256(LOCAL_CSV).hexdigest()
    assert older_manifest["latest_status"] == "ready"
    assert older_manifest["previous_result"] is True
    assert "latest_status: ready" in older_review
    assert "previous_result: true" in older_review
    assert "명시적으로 고른 이전 버전" in older_review
    assert newer["current"]["source_sha256"] not in older_review


def test_empty_and_one_row_utc_exports_keep_bounds_and_absent_statistics_honest(tmp_path):
    utc_csv = (
        "timestamp,equipment,tag,value,unit\n"
        "2026-01-01T00:00:00+09:00,APU-1,temperature,10,degC\n"
        "2026-01-01T00:00:10+09:00,APU-1,temperature,20,degC\n"
    ).encode()
    with TestClient(create_app(tmp_path / "review.sqlite3")) as client:
        headers = session(client)
        dataset = upload(client, headers, utc_csv)
        full_review, _, full_manifest = exported(client, dataset)
        one_review, _, one_manifest = exported(
            client,
            dataset,
            start="2025-12-31T15:00:00Z",
            end="2025-12-31T15:00:10Z",
        )
        empty_review, _, empty_manifest = exported(
            client,
            dataset,
            start="2025-12-31T16:00:00Z",
            end="2025-12-31T16:01:00Z",
        )

    assert full_manifest["time_basis"] == "utc"
    assert "시작(포함): 없음 — 하한 필터 없음" in full_review
    assert "종료(미포함): 없음 — 상한 필터 없음" in full_review
    assert one_manifest["summary"]["count"] == 1
    assert one_manifest["filter"]["start"] == "2025-12-31T15:00:00.000000+00:00"
    assert one_manifest["filter"]["end"] == "2025-12-31T15:00:10.000000+00:00"
    assert "관측값 수: 1" in one_review
    assert "관측값이 2개 미만이므로 간격을 판단할 수 없습니다" in one_review
    assert empty_manifest["summary"]["count"] == 0
    assert empty_manifest["summary"]["mean"] is None
    assert empty_manifest["summary"]["min"] is None
    assert empty_manifest["summary"]["max"] is None
    assert "관측값 수: 0" in empty_review
    assert "표본 평균: 없음" in empty_review
    assert "최솟값: 없음" in empty_review
    assert "최댓값: 없음" in empty_review


def test_uploaded_labels_stay_plain_and_spreadsheet_escape_is_disclosed(tmp_path):
    equipment = "=2+2 <script>alert(1)</script>"
    tag = "@SUM(A1) <img src=x>"
    unit = "+danger"
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("timestamp", "equipment", "tag", "value", "unit"))
    writer.writerow(("2026-01-01T00:00:00", equipment, tag, -4, unit))
    raw = output.getvalue().encode()
    with TestClient(create_app(tmp_path / "review.sqlite3")) as client:
        headers = session(client)
        dataset = upload(client, headers, raw, name="<source & quoted>.csv")
        review, csv_bytes, manifest = exported(
            client,
            dataset,
            series={"equipment": equipment, "tag": tag},
        )

    row = next(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert row["equipment"] == "'" + equipment
    assert row["tag"] == "'" + tag
    assert row["unit"] == "'" + unit
    assert float(row["value"]) == -4
    assert manifest["spreadsheet_escape"] == {"prefix": "'", "escaped_text_cells": 3}
    assert json.dumps(equipment, ensure_ascii=False) in review
    assert json.dumps(tag, ensure_ascii=False) in review
    assert json.dumps(unit, ensure_ascii=False) in review
    assert json.dumps("<source & quoted>.csv", ensure_ascii=False) in review
    assert "UTF-8 일반 텍스트" in review
    assert "텍스트 셀 3개" in review
    assert "HTML/Markdown" in review
    assert datetime.fromisoformat(manifest["generated_at"]).utcoffset().total_seconds() == 0
