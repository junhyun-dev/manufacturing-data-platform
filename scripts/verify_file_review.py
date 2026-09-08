#!/usr/bin/env python3
"""Exercise the real HTTP server in an isolated retained workspace, without browser extras."""
import csv
import hashlib
import http.cookiejar
import io
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = b"timestamp,equipment,tag,value,unit\n2020-01-01T00:00:00,Pump,pressure,10,bar\n2020-01-01T00:00:10,Pump,pressure,20,bar\n"


def main():
    run = ROOT / ".cache" / "file-review-verification" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), MFG_REVIEW_DB=str(run / "review.sqlite3"))
    env.pop("MFG_REVIEW_SECURE_COOKIE", None)
    env["MFG_REVIEW_HOSTS"] = "127.0.0.1,localhost"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log = (run / "server.log").open("w")
    process = None

    def start():
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "manufacturing_data_platform.file_review.app:create_app",
                                 "--factory", "--host", "127.0.0.1", "--port", str(port), "--limit-concurrency", "16"],
                                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if proc.poll() is not None:
                raise RuntimeError(f"Server exited; see {run / 'server.log'}")
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=1) as response:
                    assert json.load(response)["status"] == "ok"
                    return proc
            except (urllib.error.URLError, TimeoutError):
                time.sleep(.1)
        proc.terminate()
        proc.wait(timeout=10)
        raise RuntimeError("Server startup timed out")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf = None

    def request(path, data=None, method=None, binary=False):
        headers = {"X-Review-CSRF": csrf} if csrf else {}
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        with opener.open(req, timeout=30) as response:
            raw = response.read()
            return raw if binary else json.loads(raw)

    try:
        process = start()
        assert b"Telemetry Review" in request("/", binary=True)
        assert len(request("/app.js", binary=True)) > 1000
        assert len(request("/styles.css", binary=True)) > 1000
        csrf = request("/api/session")["csrf_token"]
        first = request("/api/datasets?name=pressure.csv", RAW)["dataset"]
        route = "/api/datasets/" + first["id"]
        original = request(route + "/query")
        assert original["summary"]["mean"] == 15
        bad = request(route + "/replace?name=broken.csv", RAW.replace(b",20,", b",NaN,"))["dataset"]
        assert bad["latest"]["status"] == "blocked" and bad["current"] == first["current"]
        assert request(route + "/query")["previous_result"] is True
        fixed = request(route + "/replace?name=corrected.csv", RAW.replace(b",20,", b",30,"))["dataset"]
        assert fixed["current"]["version"] != first["current"]["version"]
        assert request(route + "/query")["summary"]["mean"] == 20
        sample = request("/api/datasets/sample", b"")["dataset"]
        sample_route = "/api/datasets/" + sample["id"]
        selected = request(sample_route + "/query?tag=Oil_temperature")
        source = ROOT / "src/manufacturing_data_platform/file_review/sample/metropt3-day.csv"
        with source.open() as handle:
            values = [float(row["value"]) for row in csv.DictReader(handle) if row["tag"] == "Oil_temperature"]
        assert selected["summary"]["count"] == len(values) == 7144
        assert abs(selected["summary"]["mean"] - statistics.fmean(values)) < 1e-10
        failed = request(sample_route + "/delivery-check", b"")["dataset"]
        assert failed["latest"]["status"] == "incomplete" and failed["latest"]["missing_rows"] > 0
        assert failed["current"] == sample["current"]
        for _ in range(2):
            recovered = request(sample_route + "/retry", b"")["dataset"]
            assert recovered["latest"]["status"] == "ready"
            assert recovered["current"]["version"] == sample["current"]["version"]
            assert recovered["latest"]["version_changed"] is False
        params = urllib.parse.urlencode({"tag": "Oil_temperature", "version": selected["version"]})
        exported = request(sample_route + "/export?" + params, binary=True)
        (run / "checked-result.zip").write_bytes(exported)
        with zipfile.ZipFile(io.BytesIO(exported)) as archive:
            raw = archive.read("observations.csv")
            manifest = json.loads(archive.read("manifest.json"))
            observations = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        assert len(observations) == 7144
        assert manifest["observations_sha256"] == hashlib.sha256(raw).hexdigest()
        assert manifest["version"] == sample["current"]["version"]
        try:
            urllib.request.urlopen(base + sample_route, timeout=5)
            raise AssertionError("Anonymous request unexpectedly read a dataset")
        except urllib.error.HTTPError as error:
            assert error.code == 401
        process.terminate()
        process.wait(timeout=10)
        process = start()
        restored = request(sample_route)["dataset"]
        assert restored["current"] == sample["current"]
        assert len(restored["history"]) == 4
        receipt = {"status": "PASS", "at": datetime.now(timezone.utc).isoformat(),
                   "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                   "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
                   "sample_observations": sample["current"]["rows"], "selected_rows": len(observations),
                   "independent_mean": statistics.fmean(values), "api_mean": selected["summary"]["mean"],
                   "withheld_rows": failed["latest"]["missing_rows"], "stable_recovery": True,
                   "restart_persistence": True, "version": sample["current"]["version"],
                   "source_sha256": sample["current"]["source_sha256"],
                   "checks": ["real HTTP", "upload", "blocked replacement", "corrected result", "independent sample mean",
                              "incomplete delivery", "repeat recovery", "export read-back", "anonymous refusal", "restart"],
                   "source_files": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted((ROOT / "src/manufacturing_data_platform/file_review").rglob("*"))
                                    if p.is_file() and "__pycache__" not in str(p)}}
        (run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"status": "PASS", "receipt": str(run / "receipt.json"),
                          "selected_rows": len(observations), "mean": selected["summary"]["mean"]}, indent=2))
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    main()
