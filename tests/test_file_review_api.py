"""User-visible file review behavior, independently checked through HTTP."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from manufacturing_data_platform.file_review.app import create_app


CSV = (
    "timestamp,equipment,tag,value,unit\n"
    "2020-02-01T00:00:00,APU-1,temperature,10,degC\n"
    "2020-02-01T00:00:10,APU-1,temperature,20,degC\n"
    "2020-02-01T00:00:20,APU-1,temperature,30,degC\n"
).encode()
SERIES = {"equipment": "APU-1", "tag": "temperature"}


def _session(client: TestClient) -> dict[str, str]:
    response = client.get("/api/session")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expires_hours"] == 24
    assert body["limits"]["upload_bytes"] == 8 * 1024 * 1024
    assert body["limits"]["rows"] == 50_000
    assert body["limits"]["datasets"] == 10
    assert body["csrf_token"] and client.cookies
    return {"X-Review-CSRF": body["csrf_token"]}


@pytest.fixture
def browser(tmp_path: Path):
    with TestClient(create_app(tmp_path / "review.sqlite3")) as client:
        yield client, _session(client)


def _upload(client, headers, content=CSV, *, dataset_id=None, name="observations.csv"):
    route = "/api/datasets" if dataset_id is None else f"/api/datasets/{dataset_id}/replace"
    response = client.post(
        route,
        params={"name": name},
        content=content,
        headers={**headers, "Content-Type": "text/csv"},
    )
    assert 200 <= response.status_code < 300, response.text
    return response.json()["dataset"]


def _query(client, dataset_id, **filters):
    response = client.get(f"/api/datasets/{dataset_id}/query", params={**SERIES, **filters})
    assert response.status_code == 200, response.text
    return response.json()


def _error(response, statuses):
    assert response.status_code in statuses, response.text
    error = response.json()["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    return error


def _blocked(dataset):
    assert dataset["latest"]["status"] == "blocked"
    assert dataset["latest"]["issues"]
    assert all(issue["code"] and issue["message"] for issue in dataset["latest"]["issues"])


def test_upload_query_half_open_range_and_export_same_version(browser):
    client, headers = browser
    dataset = _upload(client, headers)
    current = dataset["current"]
    assert dataset["latest"]["status"] == "ready"
    assert current["rows"] == 3
    assert current["source_sha256"] == sha256(CSV).hexdigest()
    assert current["time_basis"] == "unspecified"
    assert current["quality_counts"]["unspecified"] == 3
    assert current["quality_counts"]["good"] == 0

    all_rows = _query(client, dataset["id"])
    assert all_rows["summary"]["count"] == 3
    assert all_rows["summary"]["mean"] == pytest.approx(20)
    assert all_rows["summary"]["min"] == 10
    assert all_rows["summary"]["max"] == 30
    assert all_rows["previous_result"] is False
    filters = {"start": "2020-02-01T00:00:00", "end": "2020-02-01T00:00:20"}
    selected = _query(client, dataset["id"], **filters)
    assert selected["summary"]["count"] == 2
    assert selected["summary"]["mean"] == pytest.approx(15)
    assert selected["version"] == current["version"]

    response = client.get(
        f"/api/datasets/{dataset['id']}/export",
        params={**SERIES, **filters, "version": selected["version"]},
    )
    assert response.status_code == 200, response.text
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"observations.csv", "manifest.json"}
        csv_bytes = archive.read("observations.csv")
        manifest = json.loads(archive.read("manifest.json"))
    exported = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert [float(row["value"]) for row in exported] == [10, 20]
    assert {row["quality"] for row in exported} == {"unspecified"}
    # Check the exported evidence independently instead of reusing its producer.
    assert manifest["version"] == selected["version"]
    assert manifest["source_sha256"] == sha256(CSV).hexdigest()
    assert manifest["observations_sha256"] == sha256(csv_bytes).hexdigest()
    assert manifest["summary"]["quality_counts"]["unspecified"] == 2
    assert manifest["summary"]["count"] == len(exported)


def test_failed_replacement_preserves_result_then_corrected_file_changes_version(browser):
    client, headers = browser
    original = _upload(client, headers)
    dataset_id = original["id"]
    old_version = original["current"]["version"]
    bad = (
        "timestamp,equipment,tag,value,unit,quality\n"
        "2020-02-01T00:00:00,APU-1,temperature,,degC,bad\n"
    ).encode()
    rejected = _upload(client, headers, bad, dataset_id=dataset_id, name="bad.csv")
    _blocked(rejected)
    assert rejected["current"] == original["current"]
    previous = _query(client, dataset_id)
    assert previous["version"] == old_version
    assert previous["latest_status"] == "blocked"
    assert previous["previous_result"] is True
    assert previous["summary"]["mean"] == pytest.approx(20)

    corrected_bytes = CSV.replace(b",20,degC", b",50,degC")
    corrected = _upload(client, headers, corrected_bytes, dataset_id=dataset_id, name="corrected.csv")
    assert corrected["latest"]["status"] == "ready"
    assert corrected["current"]["version"] != old_version
    assert corrected["current"]["source_sha256"] == sha256(corrected_bytes).hexdigest()
    assert _query(client, dataset_id)["summary"]["mean"] == pytest.approx(30)
    historical = _query(client, dataset_id, version=old_version)
    assert historical["summary"]["mean"] == pytest.approx(20)
    assert historical["previous_result"] is True


def test_identical_bytes_ignore_upload_filename_and_attempt_clock(browser):
    client, headers = browser
    first = _upload(client, headers)
    second = _upload(client, headers, dataset_id=first["id"], name="renamed.csv")
    assert second["latest"]["id"] != first["latest"]["id"]
    assert second["current"]["version"] == first["current"]["version"]
    assert second["latest"]["version_changed"] is False


def test_sample_delivery_failure_keeps_last_good_and_retry_converges(browser):
    client, headers = browser
    response = client.post("/api/datasets/sample", headers=headers)
    assert 200 <= response.status_code < 300, response.text
    sample = response.json()["dataset"]
    dataset_id = sample["id"]
    version = sample["current"]["version"]
    series = sample["current"]["series"][0]
    query_params = {"equipment": series["equipment"], "tag": series["tag"]}
    before = client.get(f"/api/datasets/{dataset_id}/query", params=query_params).json()

    response = client.post(f"/api/datasets/{dataset_id}/delivery-check", headers=headers)
    assert response.status_code == 200, response.text
    failed = response.json()["dataset"]
    assert failed["latest"]["status"] == "incomplete"
    assert failed["latest"]["expected_rows"] > failed["latest"]["observed_rows"]
    assert failed["latest"]["missing_rows"] > 0
    assert failed["current"]["version"] == version
    during = client.get(f"/api/datasets/{dataset_id}/query", params=query_params).json()
    assert during["summary"] == before["summary"]
    assert during["previous_result"] is True
    assert during["latest_status"] == "incomplete"

    for _ in range(2):
        response = client.post(f"/api/datasets/{dataset_id}/retry", headers=headers)
        assert response.status_code == 200, response.text
        recovered = response.json()["dataset"]
        assert recovered["latest"]["status"] == "ready"
        assert recovered["latest"]["missing_rows"] == 0
        assert recovered["current"]["version"] == version
        assert recovered["latest"]["version_changed"] is False
    after = client.get(f"/api/datasets/{dataset_id}/query", params=query_params).json()
    assert after["summary"] == before["summary"]
    assert after["previous_result"] is False


@pytest.mark.parametrize(
    "rows",
    [
        # Different strings describe the same instant and logical observation.
        "2020-02-01T00:00:00Z,APU-1,temperature,10,degC\n"
        "2020-02-01T09:00:00+09:00,APU-1,temperature,10,degC\n",
        "2020-02-01T00:00:00,APU-1,temperature,10,degC\n"
        "2020-02-01T00:00:00,APU-1,temperature,10,degC\n",
        "2020-02-01T00:00:00,APU-1,temperature,10,degC\n"
        "2020-02-01T00:00:10,APU-1,temperature,20,K\n",
        "2020-02-01T00:00:00Z,APU-1,temperature,10,degC\n"
        "2020-02-01T00:00:10,APU-1,temperature,20,degC\n",
        "2020-02-01T00:00:00,APU-1,temperature,NaN,degC\n",
        "2020-02-01T00:00:00,APU-1,temperature,Infinity,degC\n",
    ],
    ids=["equivalent-instant", "identical-duplicate", "mixed-units", "mixed-time-basis", "nan", "infinity"],
)
def test_ambiguous_or_nonfinite_input_is_recorded_without_publication(browser, rows):
    client, headers = browser
    dataset = _upload(client, headers, ("timestamp,equipment,tag,value,unit\n" + rows).encode())
    _blocked(dataset)
    assert dataset["current"] is None


@pytest.mark.parametrize("quality", ["uncertain", "BAD", "goood"])
def test_supplied_unusable_or_unknown_quality_never_becomes_good(browser, quality):
    client, headers = browser
    content = (
        "timestamp,equipment,tag,value,unit,quality\n"
        f"2020-02-01T00:00:00,APU-1,temperature,10,degC,{quality}\n"
    ).encode()
    dataset = _upload(client, headers, content)
    _blocked(dataset)
    assert dataset["current"] is None


def test_header_order_and_explicit_quality_are_preserved(browser):
    client, headers = browser
    content = (
        "tag,unit,timestamp,quality,equipment,value\n"
        "temperature,degC,2020-02-01T09:00:00+09:00,GOOD,APU-1,10\n"
        "temperature,degC,2020-02-01T00:00:10Z,,APU-1,20\n"
    ).encode()
    dataset = _upload(client, headers, content)
    assert dataset["latest"]["status"] == "ready"
    result = _query(client, dataset["id"], start="2020-02-01T00:00:00Z", end="2020-02-01T00:00:10Z")
    assert result["summary"]["count"] == 1
    assert result["summary"]["mean"] == 10
    assert dataset["current"]["quality_counts"]["good"] == 1
    assert dataset["current"]["quality_counts"]["unspecified"] == 1


def test_empty_query_returns_null_statistics_not_a_reused_previous_answer(browser):
    client, headers = browser
    dataset = _upload(client, headers)
    result = _query(client, dataset["id"], start="2021-01-01T00:00:00", end="2021-01-02T00:00:00")
    assert result["summary"]["count"] == 0
    assert result["summary"]["mean"] is None
    assert result["summary"]["min"] is None
    assert result["summary"]["max"] is None
    assert result["points"] == []
    assert result["rows"] == []


def test_invalid_filters_and_unpinned_export_are_structured_errors(browser):
    client, headers = browser
    dataset = _upload(client, headers)
    route = f"/api/datasets/{dataset['id']}"
    for filters in (
        {"start": "not-a-time"},
        {"start": "2020-02-02T00:00:00", "end": "2020-02-01T00:00:00"},
        {"start": "2020-02-01T00:00:00Z"},
        {"equipment": "unrecognized-equipment"},
        {"tag": "unrecognized-tag"},
    ):
        _error(client.get(route + "/query", params={**SERIES, **filters}), {400, 404, 422})
    _error(client.get(route + "/export", params=SERIES), {400, 422})
    _error(client.get(route + "/query", params={**SERIES, "version": "0" * 64}), {400, 404, 409, 422})


def test_csrf_and_cross_browser_ownership_on_every_dataset_action(tmp_path):
    database = tmp_path / "review.sqlite3"
    with TestClient(create_app(database)) as owner, TestClient(create_app(database)) as other:
        owner_headers, other_headers = _session(owner), _session(other)
        _error(owner.post("/api/datasets", content=CSV), {403})
        _error(owner.post("/api/datasets", content=CSV, headers=other_headers), {403})
        dataset = _upload(owner, owner_headers)
        route = f"/api/datasets/{dataset['id']}"
        version = dataset["current"]["version"]
        assert other.get("/api/datasets").json()["datasets"] == []
        for suffix in ("", "/query", "/export"):
            _error(other.get(route + suffix, params={**SERIES, "version": version}), {404})
        for suffix in ("/replace", "/delivery-check", "/retry"):
            _error(other.post(route + suffix, content=CSV, headers=other_headers), {404})
        _error(other.delete(route, headers=other_headers), {404})
        _error(owner.delete(route), {403})
        assert _query(owner, dataset["id"])["summary"]["count"] == 3


def test_version_and_latest_failure_survive_restart(tmp_path):
    database = tmp_path / "review.sqlite3"
    with TestClient(create_app(database)) as client:
        headers = _session(client)
        dataset = _upload(client, headers)
        version = dataset["current"]["version"]
        rejected = _upload(client, headers, b"wrong,header\nx,y\n", dataset_id=dataset["id"])
        _blocked(rejected)
        cookies = dict(client.cookies)
    with TestClient(create_app(database), cookies=cookies) as client:
        restored = client.get(f"/api/datasets/{dataset['id']}")
        assert restored.status_code == 200, restored.text
        body = restored.json()["dataset"]
        assert body["current"]["version"] == version
        assert body["latest"]["status"] == "blocked"
        assert _query(client, dataset["id"])["summary"]["mean"] == 20


def test_oversized_upload_is_refused_before_it_creates_a_dataset(browser):
    client, headers = browser
    response = client.post("/api/datasets", content=b"x" * (8 * 1024 * 1024 + 1), headers=headers)
    _error(response, {413})
    assert client.get("/api/datasets").json()["datasets"] == []


def test_too_many_records_cannot_publish_even_when_all_values_are_valid(browser):
    client, headers = browser
    base = datetime(2020, 1, 1)
    text = "timestamp,equipment,tag,value,unit\n" + "".join(
        f"{(base + timedelta(seconds=i)).isoformat()},APU-1,temperature,1,degC\n"
        for i in range(50_001)
    )
    assert len(text.encode()) < 8 * 1024 * 1024
    dataset = _upload(client, headers, text.encode())
    _blocked(dataset)
    assert dataset["current"] is None


def test_template_can_be_used_and_delete_removes_dataset(browser):
    client, headers = browser
    template = client.get("/api/template.csv")
    assert template.status_code == 200
    dataset = _upload(client, headers, template.content, name="template.csv")
    assert dataset["latest"]["status"] == "ready"
    deleted = client.delete(f"/api/datasets/{dataset['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    _error(client.get(f"/api/datasets/{dataset['id']}"), {404})
    assert client.get("/api/datasets").json()["datasets"] == []


def test_plot_and_preview_limits_do_not_truncate_aggregate_or_download(browser):
    client, headers = browser
    base = datetime(2020, 1, 1)
    records = 601
    content = "timestamp,equipment,tag,value,unit\n" + "".join(
        f"{(base + timedelta(seconds=i)).isoformat()},APU-1,temperature,{i},degC\n"
        for i in range(records)
    )
    dataset = _upload(client, headers, content.encode())
    result = _query(client, dataset["id"])
    assert result["summary"]["count"] == records
    assert result["summary"]["mean"] == pytest.approx(300)
    assert 0 < len(result["points"]) <= 500
    assert result["displayed_points"] == len(result["points"])
    assert 0 < len(result["rows"]) <= 100
    assert all(point["value"] in range(records) for point in result["points"])
    response = client.get(
        f"/api/datasets/{dataset['id']}/export",
        params={**SERIES, "version": result["version"]},
    )
    assert response.status_code == 200, response.text
    with ZipFile(io.BytesIO(response.content)) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read("observations.csv").decode("utf-8-sig"))))
    assert len(rows) == records
    assert sum(float(row["value"]) for row in rows) / len(rows) == pytest.approx(300)


def test_export_escapes_uploaded_formula_text_without_changing_numeric_values(browser):
    client, headers = browser
    equipment, tag = "=2+2", "@SUM(A1)"
    content = (
        "timestamp,equipment,tag,value,unit\n"
        f"2020-02-01T00:00:00,{equipment},{tag},-4,degC\n"
    ).encode()
    dataset = _upload(client, headers, content)
    assert dataset["latest"]["status"] == "ready"
    response = client.get(
        f"/api/datasets/{dataset['id']}/export",
        params={"equipment": equipment, "tag": tag, "version": dataset["current"]["version"]},
    )
    assert response.status_code == 200, response.text
    with ZipFile(io.BytesIO(response.content)) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read("observations.csv").decode("utf-8-sig"))))
        manifest = json.loads(archive.read("manifest.json"))
    assert len(rows) == 1
    assert rows[0]["equipment"] != equipment
    assert rows[0]["tag"] != tag
    assert not rows[0]["equipment"].startswith(("=", "+", "-", "@"))
    assert not rows[0]["tag"].startswith(("=", "+", "-", "@"))
    assert float(rows[0]["value"]) == -4
    assert manifest["spreadsheet_escape"]["escaped_text_cells"] == 2
    assert manifest["spreadsheet_escape"]["prefix"] == "'"


def test_workspace_dataset_limit_is_enforced_without_hiding_existing_results(browser):
    client, headers = browser
    ids = {_upload(client, headers)["id"] for _ in range(10)}
    assert len(ids) == 10
    response = client.post("/api/datasets", content=CSV, headers=headers)
    _error(response, {409, 413, 429})
    listed = client.get("/api/datasets").json()["datasets"]
    assert {dataset["id"] for dataset in listed} == ids
