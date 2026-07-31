#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
PROJECT_PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
FIXTURE="$PROJECT_ROOT/tests/fixtures/metropt3/MetroPT3_first_3_rows.csv"
FIXTURE_SHA256="9863d4cdb7fe84bc74458a90e306fb384d9741be389329ddc434a3eacde5e21a"
OUTPUT_ROOT="$(mktemp -d /tmp/mfg-s11-verification-XXXXXX)"

cleanup() {
  case "$OUTPUT_ROOT" in
    /tmp/mfg-s11-verification-*) rm -r -- "$OUTPUT_ROOT" ;;
    *) echo "refusing unsafe cleanup target: $OUTPUT_ROOT" >&2; return 1 ;;
  esac
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing Python runtime: $PYTHON_BIN" >&2
  echo "create it with: uv venv .venv && uv pip install --python .venv/bin/python -r requirements-event-time.txt" >&2
  exit 2
fi

if ! "$PYTHON_BIN" -c 'import asyncua, pyspark, pytest' 2>/dev/null; then
  echo "event-time dependencies are missing from: $PYTHON_BIN" >&2
  echo "install them with: uv pip install --python .venv/bin/python -r requirements-event-time.txt" >&2
  exit 2
fi

PYTHONPATH="$PROJECT_PYTHONPATH" "$PYTHON_BIN" -m pytest -q \
  tests/test_event_time_trust.py \
  tests/test_industrial_source_contract.py \
  tests/test_edge_recovery.py

SPARK_LOCAL_IP=127.0.0.1 PYTHONPATH="$PROJECT_PYTHONPATH" \
  "$PYTHON_BIN" scripts/event_time_trust_verification.py \
  --source-csv "$FIXTURE" \
  --expected-sha256 "$FIXTURE_SHA256" \
  --output-root "$OUTPUT_ROOT" \
  --spark-parity

test -f "$OUTPUT_ROOT/event_time/current_trusted.json"
test -f "$OUTPUT_ROOT/event_time_verification.json"
echo "cleanup: generated output is isolated under $OUTPUT_ROOT and removed on exit"
