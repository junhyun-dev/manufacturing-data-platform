"""Contract checks for the guided, deterministic result explanation."""

import sqlite3
import time
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from manufacturing_data_platform.file_review.app import create_app


CSV = (
    "timestamp,equipment,tag,value,unit,quality\n"
    "2026-01-01T00:00:00,pump-7,pressure,10,bar,good\n"
    "2026-01-01T00:00:30,pump-7,pressure,20,bar,\n"
    "2026-01-01T00:02:30,pump-7,pressure,40,bar,\n"
).encode()
SERIES = {"equipment": "pump-7", "tag": "pressure"}


def session(client):
    response = client.get("/api/session")
    assert response.status_code == 200, response.text
    return {"X-Review-CSRF": response.json()["csrf_token"]}


def upload(client, headers, raw=CSV, name="observations.csv", dataset_id=None):
    route = "/api/datasets" if dataset_id is None else f"/api/datasets/{dataset_id}/replace"
    response = client.post(route, params={"name": name}, content=raw,
                           headers={**headers, "Content-Type": "text/csv"})
    assert response.status_code == 200, response.text
    return response.json()["dataset"]


def query(client, dataset_id, **overrides):
    response = client.get(f"/api/datasets/{dataset_id}/query", params={**SERIES, **overrides})
    assert response.status_code == 200, response.text
    return response.json()


def explanation(client, dataset_id, result, question, **overrides):
    params = {
        "question": question,
        "latest_attempt_id": result["latest_attempt_id"],
        "version": result["version"],
        "equipment": result["equipment"],
        "tag": result["tag"],
    }
    for name, value in result["filter"].items():
        if value is not None:
            params[name] = value
    params.update(overrides)
    return client.get(f"/api/datasets/{dataset_id}/explanation", params=params)


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert set(response.json()) == {"error"}


def database_state(path, dataset_id):
    with sqlite3.connect(path) as db:
        return (
            db.execute("SELECT current_version FROM datasets WHERE id=?", (dataset_id,)).fetchone()[0],
            db.execute("SELECT count(*) FROM attempts WHERE dataset_id=?", (dataset_id,)).fetchone()[0],
            db.execute("SELECT count(*) FROM sources WHERE dataset_id=?", (dataset_id,)).fetchone()[0],
            db.execute("SELECT count(*) FROM versions WHERE dataset_id=?", (dataset_id,)).fetchone()[0],
        )


def test_explanation_uses_query_numbers_identity_and_does_not_write_review_state(tmp_path):
    path = tmp_path / "review.sqlite3"
    with TestClient(create_app(path)) as client:
        headers = session(client)
        dataset = upload(client, headers, name="handoff.csv")
        result = query(client, dataset["id"], start="2026-01-01T00:00:00", end="2026-01-01T00:02:30")
        assert result["latest_attempt_id"] == dataset["latest"]["id"] > 0
        assert result["summary"]["count"] == 2
        assert result["summary"]["mean"] == pytest.approx(15)
        assert result["summary"]["quality_counts"]["unspecified"] == 1
        before = database_state(path, dataset["id"])

        response = explanation(client, dataset["id"], result, "handoff_limits")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["mode"] == "guided"
        assert body["question"] == "handoff_limits"
        assert body["context"] == {
            "dataset_id": dataset["id"],
            "version": dataset["current"]["version"],
            "source_name": "handoff.csv",
            "source_sha256": sha256(CSV).hexdigest(),
            "latest_attempt_id": dataset["latest"]["id"],
            "latest_status": "ready",
            "equipment": "pump-7",
            "tag": "pressure",
            "unit": "bar",
            "time_basis": "unspecified",
            "filter": result["filter"],
        }
        assert body["summary"] == result["summary"]
        assert body["summary"]["mean"] == pytest.approx((10 + 20) / 2)
        assert body["latest"]["source_name"] == "handoff.csv"
        assert set(body["latest"]) == {"id", "kind", "status", "at", "source_name",
                                        "expected_rows", "observed_rows", "missing_rows"}
        assert body["evidence"] == ["query", "source"]
        assert "rows" not in body and "points" not in body
        assert all(isinstance(paragraph, str) for paragraph in body["paragraphs"])
        assert database_state(path, dataset["id"]) == before


@pytest.fixture
def browser_path(tmp_path):
    path = tmp_path / "review.sqlite3"
    with TestClient(create_app(path)) as client:
        yield client, session(client), path


def test_refused_replacement_and_explicit_older_version_are_explained_from_their_sources(browser_path):
    client, headers, _ = browser_path
    original = upload(client, headers, name="accepted.csv")
    old_version = original["current"]["version"]
    rejected = upload(client, headers, b"wrong,header\nx,y\n", name="rejected.csv",
                      dataset_id=original["id"])
    retained = query(client, original["id"])
    assert retained["version"] == old_version
    assert retained["latest_attempt_id"] == rejected["latest"]["id"]
    assert retained["latest_status"] == "blocked"
    assert retained["previous_result"] is True
    body = explanation(client, original["id"], retained, "previous_result").json()
    assert body["context"]["source_name"] == "accepted.csv"
    assert body["latest"]["source_name"] == "rejected.csv"
    assert body["latest"]["status"] == "blocked"
    assert body["previous_result"] is True
    assert "새 분석 결과로 발행하지 않았습니다" in " ".join(body["paragraphs"])

    newer_raw = CSV.replace(b",40,", b",70,")
    newer = upload(client, headers, newer_raw, name="newer.csv", dataset_id=original["id"])
    older_query = query(client, original["id"], version=old_version)
    assert older_query["latest_attempt_id"] == newer["latest"]["id"]
    assert older_query["summary"]["mean"] == pytest.approx((10 + 20 + 40) / 3)
    response = explanation(client, original["id"], older_query, "previous_result")
    assert response.status_code == 200, response.text
    older = response.json()
    assert older["context"]["source_name"] == "accepted.csv"
    assert older["latest"]["source_name"] == "newer.csv"
    assert older["latest"]["status"] == "ready"
    assert older["previous_result"] is True
    assert "이전 버전" in older["title"]


def test_changed_latest_attempt_refuses_stale_pin_without_answer_or_state_change(browser_path):
    client, headers, path = browser_path
    dataset = upload(client, headers)
    stale = query(client, dataset["id"])
    retried = client.post(f"/api/datasets/{dataset['id']}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    before = database_state(path, dataset["id"])
    response = explanation(client, dataset["id"], stale, "gap_limits")
    assert_error(response, 409, "CONTEXT_CHANGED")
    assert database_state(path, dataset["id"]) == before


def test_required_pins_question_enum_and_query_filters_fail_closed(browser_path):
    client, headers, _ = browser_path
    dataset = upload(client, headers)
    result = query(client, dataset["id"])
    route = f"/api/datasets/{dataset['id']}/explanation"
    valid = {"question": "gap_limits", "latest_attempt_id": result["latest_attempt_id"],
             "version": result["version"], **SERIES}
    for missing in ("question", "latest_attempt_id", "version"):
        assert_error(client.get(route, params={key: value for key, value in valid.items() if key != missing}),
                     422, "REQUEST")
    for value in (0, -1, "not-an-id"):
        assert_error(client.get(route, params={**valid, "latest_attempt_id": value}), 422, "REQUEST")
    assert_error(client.get(route, params={**valid, "question": "diagnose_failure"}), 422, "REQUEST")
    assert_error(client.get(route, params={**valid, "version": "   "}), 400, "VERSION_REQUIRED")
    assert_error(client.get(route, params={**valid, "start": "not-a-time"}), 400, "FILTER_TIME")
    assert_error(client.get(route, params={**valid, "start": "2026-01-02T00:00:00",
                                           "end": "2026-01-01T00:00:00"}), 400, "FILTER_RANGE")


def test_empty_and_short_ranges_do_not_reuse_values_or_infer_an_interval(browser_path):
    client, headers, _ = browser_path
    dataset = upload(client, headers)
    empty = query(client, dataset["id"], start="2027-01-01T00:00:00", end="2027-01-02T00:00:00")
    response = explanation(client, dataset["id"], empty, "handoff_limits")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["count"] == 0
    assert body["summary"]["mean"] is None
    assert "표본 평균은 없습니다" in " ".join(body["paragraphs"])

    one = query(client, dataset["id"], start="2026-01-01T00:00:00", end="2026-01-01T00:00:30")
    body = explanation(client, dataset["id"], one, "gap_limits").json()
    assert body["summary"]["count"] == 1
    assert body["summary"]["gap_count"] == 0
    assert "관측 간격을 계산할 수 없습니다" in " ".join(body["paragraphs"])


def test_gaps_unspecified_quality_and_untrusted_labels_remain_bounded_data(browser_path):
    client, headers, _ = browser_path
    equipment = '<img src=x onerror="alert(1)">'
    tag = "<script>alert(2)</script> ignore previous instructions"
    raw = (
        "timestamp,equipment,tag,value,unit,quality\n"
        f"2026-01-01T00:00:00,{equipment},{tag},1,kPa,\n"
        f"2026-01-01T00:02:00,{equipment},{tag},3,kPa,\n"
    ).encode()
    dataset = upload(client, headers, raw, name="<img onerror=alert(3)>.csv")
    result = query(client, dataset["id"], equipment=equipment, tag=tag)
    response = explanation(client, dataset["id"], result, "gap_limits")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["context"]["equipment"] == equipment
    assert body["context"]["tag"] == tag
    assert body["context"]["source_name"] == "<img onerror=alert(3)>.csv"
    assert body["summary"]["quality_counts"]["unspecified"] == 2
    assert body["summary"]["gap_count"] == 1
    assert body["summary"]["max_gap_seconds"] == 120
    assert set(body["evidence"]) <= {"query", "source", "history"}
    assert "html" not in body and "markdown" not in body
    text = " ".join(body["paragraphs"])
    assert "설비 중단 시간" in text and "잃어버린 행 수" in text and "정상인지 진단" in text


def test_workspace_deletion_expiry_and_artifact_tampering_are_enforced(tmp_path):
    shared = tmp_path / "shared.sqlite3"
    with TestClient(create_app(shared)) as owner, TestClient(create_app(shared)) as other:
        headers = session(owner)
        session(other)
        dataset = upload(owner, headers)
        result = query(owner, dataset["id"])
        foreign = explanation(other, dataset["id"], result, "previous_result")
        assert_error(foreign, 404, "NOT_FOUND")
        deleted = owner.delete(f"/api/datasets/{dataset['id']}", headers=headers)
        assert deleted.status_code == 200
        assert_error(explanation(owner, dataset["id"], result, "previous_result"), 404, "NOT_FOUND")

    expired_path = tmp_path / "expired.sqlite3"
    with TestClient(create_app(expired_path)) as client:
        headers = session(client)
        dataset = upload(client, headers)
        result = query(client, dataset["id"])
        with sqlite3.connect(expired_path) as db:
            db.execute("UPDATE workspaces SET last_seen=?", (time.time() - 24 * 3600 - 1,))
        assert_error(explanation(client, dataset["id"], result, "previous_result"), 401, "SESSION")

    for table, column, corrupt in (("sources", "raw", b"corrupt"),
                                   ("versions", "payload", b"corrupt")):
        path = tmp_path / f"{table}.sqlite3"
        with TestClient(create_app(path)) as client:
            headers = session(client)
            dataset = upload(client, headers)
            result = query(client, dataset["id"])
            with sqlite3.connect(path) as db:
                db.execute(f"UPDATE {table} SET {column}=?", (corrupt,))
            assert_error(explanation(client, dataset["id"], result, "previous_result"), 409, "INTEGRITY")
