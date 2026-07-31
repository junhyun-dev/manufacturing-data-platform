#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FIXTURE="$PROJECT_ROOT/tests/fixtures/metropt3/MetroPT3_first_3_rows.csv"
FIXTURE_SHA256="9863d4cdb7fe84bc74458a90e306fb384d9741be389329ddc434a3eacde5e21a"
OUTPUT_ROOT="$(mktemp -d /tmp/mfg-s10-verification-XXXXXX)"

cleanup() {
  case "$OUTPUT_ROOT" in
    /tmp/mfg-s10-verification-*) rm -rf -- "$OUTPUT_ROOT" ;;
    *) echo "refusing unsafe cleanup target: $OUTPUT_ROOT" >&2; return 1 ;;
  esac
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

PYTHONPATH=src "$PYTHON_BIN" -m pytest -q \
  tests/test_industrial_source_contract.py \
  tests/test_edge_recovery.py

PYTHONPATH=src "$PYTHON_BIN" scripts/industrial_source_contract_verification.py \
  --source-csv "$FIXTURE" \
  --expected-sha256 "$FIXTURE_SHA256" \
  --output-root "$OUTPUT_ROOT"

test -f "$OUTPUT_ROOT/last_good.json"
echo "cleanup: generated output is isolated under $OUTPUT_ROOT and removed on exit"
