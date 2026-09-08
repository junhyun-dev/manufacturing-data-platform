"""Failure injection at the stored artifact and transaction boundaries."""
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from manufacturing_data_platform.file_review.app import create_app
from manufacturing_data_platform.file_review.store import Store

RAW = b"timestamp,equipment,tag,value,unit\n2020-01-01T00:00:00,pump,pressure,10,bar\n"


@pytest.mark.parametrize("table,column", [("sources", "raw"), ("versions", "payload")])
def test_tampered_artifact_is_never_queried_exported_or_recovered(tmp_path, table, column):
    path = tmp_path / "review.db"
    with TestClient(create_app(path)) as client:
        headers = {"X-Review-CSRF": client.get("/api/session").json()["csrf_token"]}
        dataset = client.post("/api/datasets", content=RAW, headers=headers).json()["dataset"]
        with sqlite3.connect(path) as db:
            db.execute(f"UPDATE {table} SET {column}=?", (b"corrupt",))
        base = f"/api/datasets/{dataset['id']}"
        for response in (client.get(base + "/query"),
                         client.get(base + "/export", params={"version": dataset["current"]["version"]}),
                         client.post(base + "/retry", headers=headers)):
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "INTEGRITY"


def test_write_failure_rolls_back_source_version_attempt_and_pointer(tmp_path):
    path = tmp_path / "review.db"
    store = Store(path)
    owner, _ = store.session()
    old = store.submit(owner, raw=RAW, name="original.csv")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER fail_attempt BEFORE INSERT ON attempts BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        store.submit(owner, raw=RAW.replace(b",10,", b",20,"), name="corrected.csv", dataset=old["id"], kind="replace")
    assert Store(path).get(owner, old["id"]) == old
    with sqlite3.connect(path) as db:
        assert [db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("sources", "versions", "attempts")] == [1, 1, 1]


def test_corrupt_dataset_stays_manageable_and_does_not_hide_other_files(tmp_path):
    path = tmp_path / "review.db"
    with TestClient(create_app(path)) as client:
        headers = {"X-Review-CSRF": client.get("/api/session").json()["csrf_token"]}
        bad = client.post("/api/datasets", content=RAW, headers=headers).json()["dataset"]
        healthy = client.post("/api/datasets", content=RAW, headers=headers).json()["dataset"]
        with sqlite3.connect(path) as db:
            db.execute("UPDATE sources SET raw=? WHERE dataset_id=?", (b"corrupt", bad["id"]))
        items = {d["id"]: d for d in client.get("/api/datasets").json()["datasets"]}
        assert items[bad["id"]]["current"] is None
        assert items[bad["id"]]["current_error"]["code"] == "INTEGRITY"
        assert items[healthy["id"]]["current"] == healthy["current"]
        fixed = client.post(f"/api/datasets/{bad['id']}/replace", content=RAW.replace(b",10,", b",20,"), headers=headers)
        assert fixed.status_code == 200
        assert fixed.json()["dataset"]["current_error"] is None
        assert fixed.json()["dataset"]["current"]["version"] != bad["current"]["version"]


def test_export_requires_nonblank_pin_and_malformed_csrf_is_structured(tmp_path):
    with TestClient(create_app(tmp_path / "review.db")) as client:
        headers = {"X-Review-CSRF": client.get("/api/session").json()["csrf_token"]}
        dataset = client.post("/api/datasets", content=RAW, headers=headers).json()["dataset"]
        for value in ("", "   "):
            response = client.get(f"/api/datasets/{dataset['id']}/export", params={"version": value})
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "VERSION_REQUIRED"
        response = client.post("/api/datasets", content=RAW, headers=[(b"X-Review-CSRF", b"\xff")])
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF"


def test_storage_limit_refusal_preserves_prior_dataset(tmp_path, monkeypatch):
    from manufacturing_data_platform.file_review import store as module
    storage = Store(tmp_path / "review.db")
    owner, _ = storage.session()
    old = storage.submit(owner, raw=RAW, name="original.csv")
    monkeypatch.setattr(module, "WORKSPACE_BYTES", 1)
    with pytest.raises(module.ReviewError, match="보관 용량"):
        storage.submit(owner, raw=RAW.replace(b",10,", b",20,"), name="new.csv", dataset=old["id"], kind="replace")
    assert storage.get(owner, old["id"]) == old


def test_simultaneous_recovery_converges_and_persists_each_attempt(tmp_path):
    storage = Store(tmp_path / "review.db")
    owner, _ = storage.session()
    first = storage.submit(owner, raw=RAW, name="original.csv")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: storage.submit(owner, dataset=first["id"], kind="retry"), range(4)))
    assert {r["current"]["version"] for r in results} == {first["current"]["version"]}
    assert all(not r["latest"]["version_changed"] for r in results)
    assert len(storage.get(owner, first["id"])["history"]) == 5


def test_expired_workspace_is_removed_with_its_artifacts_on_restart(tmp_path):
    path = tmp_path / "review.db"
    storage = Store(path)
    owner, _ = storage.session()
    storage.submit(owner, raw=RAW, name="private.csv")
    with sqlite3.connect(path) as db:
        db.execute("UPDATE workspaces SET last_seen=?", (time.time() - 24 * 3600 - 1,))
    Store(path)
    with sqlite3.connect(path) as db:
        for table in ("workspaces", "datasets", "sources", "versions", "attempts"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_large_finite_values_produce_finite_mean(tmp_path):
    with TestClient(create_app(tmp_path / "review.db")) as client:
        headers = {"X-Review-CSRF": client.get("/api/session").json()["csrf_token"]}
        raw = RAW.replace(b",10,", b",1e308,") + b"2020-01-01T00:00:10,pump,pressure,1e308,bar\n"
        dataset = client.post("/api/datasets", content=raw, headers=headers).json()["dataset"]
        result = client.get(f"/api/datasets/{dataset['id']}/query")
        assert result.status_code == 200
        assert result.json()["summary"]["mean"] == 1e308


def test_sub_microsecond_source_time_is_refused_instead_of_silently_truncated(tmp_path):
    storage = Store(tmp_path / "review.db")
    owner, _ = storage.session()
    dataset = storage.submit(owner, raw=RAW.replace(b"T00:00:00,", b"T00:00:00.0000001,"), name="nanoseconds.csv")
    assert dataset["current"] is None
    assert dataset["latest"]["status"] == "blocked"
    assert dataset["latest"]["issues"][0]["code"] == "TIMESTAMP"


def test_gap_flag_uses_underlying_rows_not_plot_decimation(tmp_path):
    from datetime import datetime, timedelta
    from manufacturing_data_platform.file_review.query import query
    from manufacturing_data_platform.file_review.model import parse_csv, payload_for, digest
    start = datetime(2020, 1, 1)
    lines = ["timestamp,equipment,tag,value,unit"]
    # 2,000 points at 30 s intervals: decimated display intervals >60 s are not source gaps.
    for n in range(2000):
        lines.append(f"{(start + timedelta(seconds=30*n + (300 if n >= 1001 else 0))).isoformat()},pump,pressure,{n},bar")
    raw = ("\n".join(lines) + "\n").encode()
    parsed = parse_csv(raw)
    result, _ = query(payload_for(parsed, digest(raw)), {"version": "v"}, {"status": "ready", "version": "v"})
    assert result["summary"]["gap_count"] == 1
    assert sum(point["gap_before"] for point in result["points"]) == 1
