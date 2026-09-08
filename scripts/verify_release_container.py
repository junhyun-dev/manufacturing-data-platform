#!/usr/bin/env python3
"""Build and read back the bounded public-preview container on loopback."""
import http.cookiejar
import http.client
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "0.1.0-rc.1"


def command(*args, output=None, check=True):
    return subprocess.run(args, cwd=ROOT, text=True, stdout=output or subprocess.PIPE,
                          stderr=subprocess.STDOUT, check=check)


def main():
    suffix = uuid.uuid4().hex[:12]
    revision = command("git", "rev-parse", "HEAD").stdout.strip()
    dirty = bool(command("git", "status", "--porcelain").stdout.strip())
    image = f"telemetry-review-verify:{suffix}"
    volume = f"telemetry-review-verify-{suffix}"
    container = f"telemetry-review-verify-{suffix}"
    run = ROOT / ".cache" / "release-container" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True)
    log = (run / "docker.log").open("w")
    active = None
    started_at = time.monotonic()
    receipt = {"status": "FAIL", "release": RELEASE, "revision": revision,
               "source_dirty": dirty, "checks": []}

    def start(name):
        command("docker", "run", "--detach", "--name", name, "--read-only",
                "--tmpfs", "/tmp:size=16m,mode=1777", "--mount",
                f"type=volume,source={volume},target=/var/lib/telemetry-review",
                "--env", "MFG_REVIEW_MODE=sample", "--env",
                "MFG_REVIEW_HOSTS=127.0.0.1,localhost", "--publish", "127.0.0.1::8000", image,
                output=log)
        binding = None
        for _ in range(50):
            published = command("docker", "port", name, "8000/tcp", check=False).stdout.strip()
            if published:
                binding = published.rsplit(":", 1)[1]
                break
            state = json.loads(command("docker", "inspect", "--format", "{{json .State}}", name).stdout)
            if not state["Running"]:
                command("docker", "logs", name, output=log, check=False)
                raise RuntimeError(f"container exited during startup with code {state['ExitCode']}; "
                                   f"see {run / 'docker.log'}")
            time.sleep(.1)
        if binding is None:
            command("docker", "logs", name, output=log, check=False)
            raise RuntimeError(f"container port was not published; see {run / 'docker.log'}")
        base = f"http://127.0.0.1:{binding}"
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=1) as response:
                    health = json.load(response)
                return base, health
            except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError):
                time.sleep(.1)
        command("docker", "logs", name, output=log, check=False)
        raise RuntimeError(f"container did not become healthy; see {run / 'docker.log'}")

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf = None

    def request(base, path, data=None):
        headers = {"X-Review-CSRF": csrf} if csrf else {}
        with opener.open(urllib.request.Request(base + path, data=data, headers=headers), timeout=30) as response:
            return json.load(response)

    try:
        command("docker", "build", "--tag", image, "--build-arg", f"RELEASE_VERSION={RELEASE}",
                "--build-arg", f"VCS_REF={revision}", ".", output=log)
        command("docker", "volume", "create", volume, output=log)
        active = container
        base, health = start(active)
        assert health == {"status": "ok", "contract": "telemetry_file_review_v1",
                          "release": RELEASE, "revision": revision, "mode": "sample"}
        receipt["checks"].append("release identity read-back")
        session = request(base, "/api/session")
        csrf = session["csrf_token"]
        assert session["capabilities"] == {"uploads": False, "sample": True, "accounts": False}
        try:
            request(base, "/api/datasets", b"timestamp,equipment,tag,value,unit\n")
            raise AssertionError("sample-only container accepted an arbitrary upload")
        except urllib.error.HTTPError as error:
            assert error.code == 403
            assert json.load(error)["error"]["code"] == "UPLOADS_DISABLED"
        receipt["checks"].append("arbitrary upload refused")
        sample = request(base, "/api/datasets/sample", b"")["dataset"]
        selected = request(base, f"/api/datasets/{sample['id']}/query?tag=Oil_temperature")
        assert selected["summary"]["count"] == 7144
        assert abs(selected["summary"]["mean"] - 55.74811730123181) < 1e-12
        receipt["checks"].append("public sample analysis")
        inspect = json.loads(command("docker", "inspect", active).stdout)[0]
        assert inspect["Config"]["User"] == "10001:10001"
        assert inspect["HostConfig"]["ReadonlyRootfs"] is True
        receipt["container_user"] = inspect["Config"]["User"]
        receipt["read_only_root"] = inspect["HostConfig"]["ReadonlyRootfs"]
        receipt["checks"].append("non-root read-only runtime")
        receipt["runtime_stats"] = command(
            "docker", "stats", "--no-stream", "--format", "{{json .}}", active
        ).stdout.strip()
        command("docker", "rm", "--force", active, output=log)
        active = container + "-restart"
        base, restarted_health = start(active)
        assert restarted_health == health
        restored = request(base, f"/api/datasets/{sample['id']}")["dataset"]
        assert restored["current"]["version"] == sample["current"]["version"]
        receipt["checks"].append("persistent volume restart")
        image_details = json.loads(command("docker", "image", "inspect", image).stdout)[0]
        labels = image_details["Config"]["Labels"]
        assert labels["org.opencontainers.image.licenses"] == "Apache-2.0"
        assert labels["org.opencontainers.image.version"] == RELEASE
        assert labels["org.opencontainers.image.revision"] == revision
        receipt["checks"].append("OCI license and release labels")
        receipt.update(status="PASS", image_id=image_details["Id"], image_bytes=image_details["Size"],
                       sample_version=sample["current"]["version"], sample_rows=sample["current"]["rows"],
                       oil_temperature_rows=selected["summary"]["count"],
                       oil_temperature_mean=selected["summary"]["mean"],
                       elapsed_seconds=round(time.monotonic() - started_at, 3))
    except BaseException as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if active:
            command("docker", "rm", "--force", active, output=log, check=False)
        command("docker", "volume", "rm", "--force", volume, output=log, check=False)
        command("docker", "image", "rm", "--force", image, output=log, check=False)
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        (run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        log.close()
    print(json.dumps({"status": receipt["status"], "receipt": str(run / "receipt.json"),
                      "image_bytes": receipt.get("image_bytes"), "checks": receipt["checks"]}, indent=2))


if __name__ == "__main__":
    main()
