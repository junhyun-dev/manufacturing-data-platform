"""Standalone web entry point. Never mounts the legacy local-path ingestion API."""
import json
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from manufacturing_data_platform import __version__

from .explanation import explain
from .model import CONTRACT, MAX_ROWS, UPLOAD_BYTES, ReviewError, digest
from .query import export_zip, query
from .store import EXPIRY_SECONDS, MAX_DATASETS, Store

ROOT = Path(__file__).parent
COOKIE = "review_workspace"
LOG = logging.getLogger(__name__)
TEMPLATE = ("timestamp,equipment,tag,value,unit,quality\n"
            "2026-09-01T09:00:00,Pump-1,temperature,24.5,°C,\n"
            "2026-09-01T09:00:10,Pump-1,temperature,24.8,°C,\n"
            "2026-09-01T09:00:20,Pump-1,temperature,24.6,°C,\n")


def create_app(storage_path=None, mode=None, release=None, revision=None):
    path = storage_path or os.environ.get("MFG_REVIEW_DB", ".cache/file-review/review.sqlite3")
    mode = mode or os.environ.get("MFG_REVIEW_MODE", "full")
    if mode not in {"full", "sample"}:
        raise ValueError("MFG_REVIEW_MODE must be 'full' or 'sample'")
    release = release or os.environ.get("MFG_REVIEW_RELEASE", f"{__version__}-dev")
    revision = revision or os.environ.get("MFG_REVIEW_REVISION", "unknown")

    @asynccontextmanager
    async def lifespan(application):
        application.state.store = Store(path)
        yield

    app = FastAPI(title="Telemetry Review", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    hosts = os.environ.get("MFG_REVIEW_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.exception_handler(ReviewError)
    async def review_error(request, error):
        return JSONResponse({"error": {"code": error.code, "message": error.message}}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({"error": {"code": "REQUEST", "message": "요청 값의 형식을 확인해 주세요."}}, status_code=422)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, error):
        # Server-side exception details never become a response or include uploaded values.
        LOG.error("Review storage operation failed: %s", type(error).__name__)
        return JSONResponse({"error": {"code": "STORAGE", "message": "저장소가 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."}}, status_code=503)

    @app.middleware("http")
    async def browser_boundary(request, call_next):
        origin = request.headers.get("origin")
        same_site = request.headers.get("sec-fetch-site")
        if request.url.path.startswith("/api/") and (same_site == "cross-site" or
                (origin and origin != f"{request.url.scheme}://{request.headers.get('host', '')}")):
            response = JSONResponse({"error": {"code": "ORIGIN", "message": "같은 사이트에서 요청해 주세요."}}, status_code=403)
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    def store(request):
        return request.app.state.store

    def workspace(request, mutate=False):
        return store(request).authorize(request.cookies.get(COOKIE), request.headers.get("X-Review-CSRF"), mutate)

    def require_uploads():
        if mode != "full":
            raise ReviewError("UPLOADS_DISABLED", "공개 체험에서는 준비된 샘플만 사용할 수 있습니다.", 403)

    async def upload(request):
        size, chunks = 0, []
        async for chunk in request.stream():
            size += len(chunk)
            if size > UPLOAD_BYTES:
                raise ReviewError("UPLOAD_LIMIT", "CSV는 8 MiB 이하로 올려 주세요.", 413)
            chunks.append(chunk)
        return b"".join(chunks)

    @app.get("/healthz")
    def health(request: Request):
        with store(request).connection() as db:
            db.execute("SELECT 1 FROM workspaces LIMIT 1").fetchone()
        return {"status": "ok", "contract": CONTRACT, "release": release,
                "revision": revision, "mode": mode}

    @app.get("/api/session")
    def session(request: Request):
        token, csrf = store(request).session(request.cookies.get(COOKIE))
        response = JSONResponse({"csrf_token": csrf,
                                 "capabilities": {"uploads": mode == "full", "sample": True, "accounts": False},
                                 "release": release,
                                 "limits": {"upload_bytes": UPLOAD_BYTES, "rows": MAX_ROWS, "datasets": MAX_DATASETS},
                                 "expires_hours": 24})
        response.set_cookie(COOKIE, token, max_age=EXPIRY_SECONDS, httponly=True, samesite="strict",
                            secure=os.environ.get("MFG_REVIEW_SECURE_COOKIE") == "1")
        return response

    @app.get("/api/template.csv")
    def template():
        return Response(TEMPLATE.encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="telemetry-template.csv"'})

    @app.get("/api/datasets")
    def list_datasets(request: Request):
        return {"datasets": store(request).list(workspace(request))}

    @app.post("/api/datasets")
    async def create_dataset(request: Request, name: str = "observations.csv"):
        require_uploads()
        owner = await run_in_threadpool(workspace, request, True)
        raw = await upload(request)
        result = await run_in_threadpool(store(request).submit, owner, raw=raw, name=name)
        return {"dataset": result}

    @app.post("/api/datasets/sample")
    def sample(request: Request):
        owner = workspace(request, True)
        raw = (ROOT / "sample" / "metropt3-day.csv").read_bytes()
        metadata = json.loads((ROOT / "sample" / "provenance.json").read_text())
        if digest(raw) != metadata["sample_sha256"]:
            raise ReviewError("SAMPLE_INTEGRITY", "공개 샘플의 무결성을 확인할 수 없습니다.", 503)
        return {"dataset": store(request).submit(owner, raw=raw, name="MetroPT-3 · 2020-02-01", source_kind="sample")}

    @app.get("/api/datasets/{dataset}")
    def get_dataset(dataset: str, request: Request):
        return {"dataset": store(request).get(workspace(request), dataset)}

    @app.post("/api/datasets/{dataset}/replace")
    async def replace(dataset: str, request: Request, name: str = "observations.csv"):
        require_uploads()
        owner = await run_in_threadpool(workspace, request, True)
        # Reject a foreign dataset before accepting its upload body.
        await run_in_threadpool(store(request).check_owner, owner, dataset)
        raw = await upload(request)
        return {"dataset": await run_in_threadpool(store(request).submit, owner, raw=raw, name=name, dataset=dataset, kind="replace")}

    @app.post("/api/datasets/{dataset}/retry")
    def retry(dataset: str, request: Request):
        return {"dataset": store(request).submit(workspace(request, True), dataset=dataset, kind="retry")}

    @app.post("/api/datasets/{dataset}/delivery-check")
    def delivery_check(dataset: str, request: Request):
        return {"dataset": store(request).submit(workspace(request, True), dataset=dataset, kind="delivery-check")}

    @app.delete("/api/datasets/{dataset}")
    def delete(dataset: str, request: Request):
        store(request).delete(workspace(request, True), dataset)
        return {"deleted": True}

    def selected(request, dataset, equipment, tag, start, end, version):
        payload, stored, latest = store(request).snapshot(workspace(request), dataset, version)
        result, rows = query(payload, stored, latest, equipment, tag, start, end)
        return result, rows, stored

    @app.get("/api/datasets/{dataset}/query")
    def analyze(dataset: str, request: Request, equipment: str = None, tag: str = None,
                start: str = None, end: str = None, version: str = None):
        result, _, _ = selected(request, dataset, equipment, tag, start, end, version)
        return result

    @app.get("/api/datasets/{dataset}/explanation")
    def explanation(dataset: str, request: Request,
                    question: Literal["previous_result", "handoff_limits", "gap_limits"] = Query(...),
                    latest_attempt_id: int = Query(..., gt=0), version: str = Query(...),
                    equipment: str = None, tag: str = None, start: str = None, end: str = None):
        if not version.strip():
            raise ReviewError("VERSION_REQUIRED", "설명할 결과 버전을 지정해 주세요.")
        payload, stored, latest = store(request).snapshot(workspace(request), dataset, version)
        if latest["id"] != latest_attempt_id:
            raise ReviewError("CONTEXT_CHANGED", "최근 검사 상태가 바뀌었습니다. 파일 결과를 다시 확인해 주세요.", 409)
        result, _ = query(payload, stored, latest, equipment, tag, start, end)
        return explain(dataset, question, result, stored, latest)

    @app.get("/api/datasets/{dataset}/export")
    def download(dataset: str, request: Request, version: str, equipment: str = None, tag: str = None,
                 start: str = None, end: str = None):
        if not version.strip():
            raise ReviewError("VERSION_REQUIRED", "내려받을 결과 버전을 지정해 주세요.")
        result, rows, stored = selected(request, dataset, equipment, tag, start, end, version)
        return Response(export_zip(result, rows, stored), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="telemetry-review-{result["version"][:12]}.zip"'})

    app.mount("/", StaticFiles(directory=ROOT / "static", html=True, check_dir=False), name="client")
    return app
