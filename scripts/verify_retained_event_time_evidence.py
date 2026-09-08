#!/usr/bin/env python3
"""Read-only digest and decision audit for one retained S-MFG-11 runtime."""

from __future__ import annotations

import argparse
import json

from manufacturing_data_platform.event_time_trust.verification import (
    verify_retained_event_time_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--without-spark", action="store_true",
        help="Verify Python trust evidence only; do not claim Spark parity.",
    )
    args = parser.parse_args()
    summary = verify_retained_event_time_evidence(
        source_csv=args.source_csv,
        expected_sha256=args.expected_sha256,
        output_root=args.output_root,
        require_spark_parity=not args.without_spark,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
