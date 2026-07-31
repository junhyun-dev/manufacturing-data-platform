"""Bounded executable verification for the industrial source contract."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from manufacturing_data_platform.industrial_source.opcua_runtime import (
    run_collection_scenario,
)
from manufacturing_data_platform.industrial_source.source import load_metropt_rows


def verify_three_scenarios(
    *, source_csv: str | Path, expected_sha256: str, output_root: str | Path
) -> dict:
    selection = load_metropt_rows(
        source_csv,
        expected_sha256=expected_sha256,
        start_physical_row=1,
        row_count=3,
    )

    async def run_all() -> dict:
        results = {}
        for scenario in ("normal", "quality", "interrupted"):
            results[scenario] = await run_collection_scenario(
                selection=selection,
                scenario=scenario,
                output_root=output_root,
            )
        return results

    results = asyncio.run(run_all())
    _assert_expected_results(results)
    return {
        "verification_version": 1,
        "source_file_sha256": selection.source_file_sha256,
        "scenarios": results,
    }


def _assert_expected_results(results: dict) -> None:
    normal = results["normal"]
    assert (
        normal["status"],
        normal["expected_count"],
        normal["observed_count"],
        normal["good_count"],
        normal["uncertain_count"],
        normal["bad_count"],
    ) == ("complete", 9, 9, 9, 0, 0)

    quality = results["quality"]
    assert (
        quality["status"],
        quality["expected_count"],
        quality["observed_count"],
        quality["good_count"],
        quality["uncertain_count"],
        quality["bad_count"],
    ) == ("blocked_quality", 9, 9, 7, 1, 1)

    interrupted = results["interrupted"]
    assert (
        interrupted["status"],
        interrupted["expected_count"],
        interrupted["observed_count"],
        len(interrupted["missing_event_ids"]),
    ) == ("incomplete", 9, 3, 6)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-root", required=True)
    arguments = parser.parse_args()

    evidence = verify_three_scenarios(
        source_csv=arguments.source_csv,
        expected_sha256=arguments.expected_sha256,
        output_root=arguments.output_root,
    )
    for name, report in evidence["scenarios"].items():
        print(
            f"{name}: status={report['status']} "
            f"expected={report['expected_count']} observed={report['observed_count']} "
            f"good={report['good_count']} uncertain={report['uncertain_count']} "
            f"bad={report['bad_count']} missing={len(report['missing_event_ids'])}"
        )
    print(f"source_file_sha256={evidence['source_file_sha256']}")
    print("reports_written=normal,quality,interrupted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
