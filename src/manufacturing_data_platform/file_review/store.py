"""Transactional retained inputs, attempts and checked versions for anonymous workspaces."""
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .model import (CONTRACT, ReviewError, canonical, current_summary, digest, now,
                    parse_csv, payload_for, quality_counts)

MAX_DATASETS = 10
WORKSPACE_BYTES = 32 * 1024 * 1024
GLOBAL_BYTES = 256 * 1024 * 1024
EXPIRY_SECONDS = 24 * 3600


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY, csrf TEXT NOT NULL, last_seen REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    name TEXT NOT NULL, source_kind TEXT NOT NULL, current_version TEXT, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS dataset_owner ON datasets(workspace_id);
                CREATE TABLE IF NOT EXISTS sources (
                    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                    sha TEXT NOT NULL, raw BLOB NOT NULL, PRIMARY KEY(dataset_id,sha));
                CREATE TABLE IF NOT EXISTS versions (
                    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                    version TEXT NOT NULL, payload BLOB NOT NULL, source_sha TEXT NOT NULL,
                    source_name TEXT NOT NULL, published_at TEXT NOT NULL, PRIMARY KEY(dataset_id,version));
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                    report TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS attempt_dataset ON attempts(dataset_id,id);
            """)
        with self.transaction(write=True) as db:
            self.cleanup(db)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self, write=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def cleanup(self, db):
        db.execute("DELETE FROM workspaces WHERE last_seen < ?", (time.time() - EXPIRY_SECONDS,))

    def session(self, token=None):
        with self.transaction(write=True) as db:
            self.cleanup(db)
            row = db.execute("SELECT * FROM workspaces WHERE id=?", (token or "",)).fetchone()
            if row is None:
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                db.execute("INSERT INTO workspaces VALUES (?,?,?)", (token, csrf, time.time()))
            else:
                csrf = row["csrf"]
                db.execute("UPDATE workspaces SET last_seen=? WHERE id=?", (time.time(), token))
            return token, csrf

    def authorize(self, token, csrf=None, mutate=False):
        with self.transaction(write=True) as db:
            row = db.execute("SELECT * FROM workspaces WHERE id=? AND last_seen>=?",
                             (token or "", time.time() - EXPIRY_SECONDS)).fetchone()
            if row is None:
                raise ReviewError("SESSION", "작업 공간이 만료되었습니다. 페이지를 새로 열어 주세요.", 401)
            if mutate and (not csrf or not secrets.compare_digest(csrf.encode("utf-8"), row["csrf"].encode("ascii"))):
                raise ReviewError("CSRF", "요청 확인 정보가 유효하지 않습니다. 페이지를 새로 열어 주세요.", 403)
            if row["last_seen"] < time.time() - 60:
                db.execute("UPDATE workspaces SET last_seen=? WHERE id=?", (time.time(), token))
        return token

    @staticmethod
    def owned(db, workspace, dataset):
        row = db.execute("SELECT * FROM datasets WHERE id=? AND workspace_id=?", (dataset, workspace)).fetchone()
        if row is None:
            raise ReviewError("NOT_FOUND", "이 작업 공간에서 파일을 찾을 수 없습니다.", 404)
        return row

    @staticmethod
    def latest(db, dataset):
        row = db.execute("SELECT id,report FROM attempts WHERE dataset_id=? ORDER BY id DESC LIMIT 1", (dataset,)).fetchone()
        if row is None:
            raise ReviewError("INTEGRITY", "검토 이력이 손상되어 결과를 열 수 없습니다.", 409)
        report = json.loads(row["report"])
        return dict(report, id=row["id"])

    @staticmethod
    def source(db, dataset, sha):
        row = db.execute("SELECT raw FROM sources WHERE dataset_id=? AND sha=?", (dataset, sha)).fetchone()
        if row is None or digest(row["raw"]) != sha:
            raise ReviewError("INTEGRITY", "보관 원본이 손상되었습니다. 이 파일 항목을 삭제한 뒤 원본을 새로 올려 주세요.", 409)
        return row["raw"]

    def version(self, db, dataset, version):
        row = db.execute("SELECT * FROM versions WHERE dataset_id=? AND version=?", (dataset, version)).fetchone()
        if row is None:
            raise ReviewError("VERSION_NOT_FOUND", "이 파일의 요청한 결과 버전을 찾을 수 없습니다.", 404)
        if digest(row["payload"]) != version:
            raise ReviewError("INTEGRITY", "보관 결과의 무결성을 확인할 수 없습니다.", 409)
        payload = json.loads(row["payload"])
        if payload["contract"] != CONTRACT or payload["source_sha256"] != row["source_sha"]:
            raise ReviewError("INTEGRITY", "보관 결과의 계약 또는 원본 연결이 일치하지 않습니다.", 409)
        self.source(db, dataset, row["source_sha"])
        return payload, row

    def describe(self, db, dataset):
        current, current_error = None, None
        if dataset["current_version"]:
            try:
                payload, stored = self.version(db, dataset["id"], dataset["current_version"])
                current = current_summary(payload, stored["version"], stored["source_name"], stored["published_at"])
            except ReviewError as error:
                current_error = {"code": error.code, "message": error.message}
        history = [dict(json.loads(r["report"]), id=r["id"]) for r in db.execute(
            "SELECT id,report FROM attempts WHERE dataset_id=? ORDER BY id DESC LIMIT 12", (dataset["id"],))]
        return {"id": dataset["id"], "name": dataset["name"], "source_kind": dataset["source_kind"],
                "latest": history[0], "current": current, "history": history, "current_error": current_error}

    def check_owner(self, workspace, dataset):
        with self.transaction() as db:
            self.owned(db, workspace, dataset)

    def get(self, workspace, dataset):
        with self.transaction() as db:
            return self.describe(db, self.owned(db, workspace, dataset))

    def list(self, workspace):
        with self.transaction() as db:
            return [self.describe(db, row) for row in db.execute(
                "SELECT * FROM datasets WHERE workspace_id=? ORDER BY created_at DESC,id", (workspace,)).fetchall()]

    @staticmethod
    def bounded_name(name):
        name = (name or "observations.csv").replace("\\", "/").split("/")[-1].strip()
        if not name or len(name) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise ReviewError("NAME", "파일 이름은 제어문자 없이 1–160자로 입력해 주세요.")
        return name

    @staticmethod
    def enforce_storage(db, workspace):
        usage = """SELECT COALESCE(SUM(size),0) FROM (
            SELECT s.dataset_id,length(s.raw) AS size FROM sources s
            UNION ALL SELECT v.dataset_id,length(v.payload) AS size FROM versions v
        ) u JOIN datasets d ON d.id=u.dataset_id"""
        local_size = db.execute(usage + " WHERE d.workspace_id=?", (workspace,)).fetchone()[0]
        total_size = db.execute(usage).fetchone()[0]
        if local_size > WORKSPACE_BYTES or total_size > GLOBAL_BYTES:
            raise ReviewError("STORAGE_LIMIT", "보관 용량이 가득 찼습니다. 필요 없는 파일을 삭제한 뒤 다시 시도해 주세요.", 413)

    def submit(self, workspace, raw=None, name=None, dataset=None, source_kind="upload", kind="import"):
        name = self.bounded_name(name) if raw is not None else None
        # Uploaded bytes are parsed before the write lock; retained recovery is read and checked inside it.
        parsed = parse_csv(raw) if raw is not None else None
        with self.transaction(write=True) as db:
            if dataset:
                existing = self.owned(db, workspace, dataset)
            else:
                count = db.execute("SELECT COUNT(*) FROM datasets WHERE workspace_id=?", (workspace,)).fetchone()[0]
                if count >= MAX_DATASETS:
                    raise ReviewError("DATASET_LIMIT", "작업 공간에는 파일 10개까지 보관할 수 있습니다.", 409)
                dataset = secrets.token_urlsafe(18)
                db.execute("INSERT INTO datasets VALUES (?,?,?,?,NULL,?)", (dataset, workspace, name, source_kind, now()))
                existing = self.owned(db, workspace, dataset)
            if raw is None:
                latest = self.latest(db, dataset)
                name = latest["source_name"]
                raw = self.source(db, dataset, latest["source_sha256"])
                parsed = parse_csv(raw)
            elif kind == "replace":
                db.execute("UPDATE datasets SET source_kind='upload' WHERE id=?", (dataset,))
            if kind == "delivery-check" and existing["source_kind"] != "sample":
                raise ReviewError("SAMPLE_ONLY", "전달 누락 체험은 공개 샘플에서만 실행할 수 있습니다.")
            sha = digest(raw)
            # Never replace an immutable source. A corrupt existing row must be refused too.
            db.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?)", (dataset, sha, raw))
            self.source(db, dataset, sha)
            rows = parsed["rows"]
            delivered = rows
            if kind == "delivery-check" and not parsed["issues"]:
                start, withheld = len(rows) // 3, max(1, len(rows) // 10)
                delivered = rows[:start] + rows[start + withheld:]
            missing = max(0, parsed["expected_rows"] - len(delivered))
            issues = list(parsed["issues"])
            status = "blocked" if issues else "incomplete" if missing else "ready"
            if status == "incomplete":
                issues.append({"code": "DELIVERY_MISSING", "message": f"샘플 전달 중 {missing:,}개 관측을 제외했습니다. 보관 원본으로 복구할 수 있습니다."})
            version, changed = None, False
            stamp = now()
            if status == "ready":
                payload = canonical(payload_for(parsed, sha))
                version = digest(payload)
                db.execute("INSERT OR IGNORE INTO versions VALUES (?,?,?,?,?,?)", (dataset, version, payload, sha, name, stamp))
                self.version(db, dataset, version)
                changed = version != existing["current_version"]
                db.execute("UPDATE datasets SET current_version=? WHERE id=?", (version, dataset))
            report = {"kind": kind, "status": status, "at": stamp, "source_name": name, "source_sha256": sha,
                      "expected_rows": parsed["expected_rows"], "observed_rows": len(delivered), "missing_rows": missing,
                      "issues": issues, "issue_count": parsed["issue_count"] + (status == "incomplete"),
                      "quality_counts": quality_counts(delivered), "version": version, "version_changed": changed}
            db.execute("INSERT INTO attempts(dataset_id,report) VALUES (?,?)", (dataset, canonical(report).decode()))
            db.execute("DELETE FROM attempts WHERE dataset_id=? AND id NOT IN (SELECT id FROM attempts WHERE dataset_id=? ORDER BY id DESC LIMIT 100)", (dataset, dataset))
            self.enforce_storage(db, workspace)
            return self.describe(db, self.owned(db, workspace, dataset))

    def delete(self, workspace, dataset):
        with self.transaction(write=True) as db:
            self.owned(db, workspace, dataset)
            db.execute("DELETE FROM datasets WHERE id=?", (dataset,))

    def snapshot(self, workspace, dataset, version=None):
        with self.transaction() as db:
            owned = self.owned(db, workspace, dataset)
            selected = version or owned["current_version"]
            if not selected:
                raise ReviewError("NO_RESULT", "아직 분석할 수 있는 정상 결과가 없습니다. 파일의 문제를 수정해 주세요.", 409)
            payload, stored = self.version(db, dataset, selected)
            return payload, dict(stored), self.latest(db, dataset)
