#!/usr/bin/env bash
# One retained local replay; existing verifiers own every data/trust decision.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PYTHON_BIN" -c 'import asyncua' 2>/dev/null; then
  echo 'Missing OPC UA environment. Run make setup (or install requirements-dev.lock).' >&2
  exit 2
fi

# Every run gets a new directory: replay timestamps are new observations and an
# existing sealed spool must never be silently reused or deleted by this command.
mkdir -p .cache/telemetry-runs
OUTPUT_ROOT="$(mktemp -d "$PROJECT_ROOT/.cache/telemetry-runs/run-XXXXXXXX")"
echo "Retained local evidence: $OUTPUT_ROOT"

"$PYTHON_BIN" - "$OUTPUT_ROOT" <<'PY'
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

def git(*args):
    return subprocess.check_output(["git", *args])

paths = sorted(set(git("ls-files", "-c", "-o", "--exclude-standard", "-z").split(b"\0")) - {b""})
digest = hashlib.sha256()
for raw in paths:
    path = Path(raw.decode())
    if path.is_file() and (
        path.parts[0] in {"src", "scripts", "tests"}
        or path.name in {"Makefile", "pyproject.toml", "requirements-dev.lock"}
    ):
        digest.update(raw + b"\0" + hashlib.sha256(path.read_bytes()).digest())
receipt = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "source_revision": git("rev-parse", "HEAD").decode().strip(),
    "worktree_dirty": bool(git("status", "--porcelain=v1")),
    "source_and_test_tree_sha256": digest.hexdigest(),
    "python": platform.python_version(),
    "packages": dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())),
    "scope": "local three-row OPC UA replay and Python trust decisions; no Spark or production claim",
}
Path(sys.argv[1], "runtime_identity.json").write_text(json.dumps(receipt, indent=2) + "\n")
PY

FIXTURE="$PROJECT_ROOT/tests/fixtures/metropt3/MetroPT3_first_3_rows.csv"
FIXTURE_SHA256="9863d4cdb7fe84bc74458a90e306fb384d9741be389329ddc434a3eacde5e21a"
"$PYTHON_BIN" scripts/event_time_trust_verification.py \
  --source-csv "$FIXTURE" --expected-sha256 "$FIXTURE_SHA256" \
  --output-root "$OUTPUT_ROOT"

"$PYTHON_BIN" scripts/verify_retained_event_time_evidence.py \
  --source-csv "$FIXTURE" --expected-sha256 "$FIXTURE_SHA256" \
  --output-root "$OUTPUT_ROOT" --without-spark > "$OUTPUT_ROOT/readback.json"

echo 'PASS: five trust decisions and retained current -> manifest -> data digest chain'
echo "Read-back: $OUTPUT_ROOT/readback.json"
