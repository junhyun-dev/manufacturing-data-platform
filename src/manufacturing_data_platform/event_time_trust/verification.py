"""Representative S-MFG-11 arrival-disorder verification."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from manufacturing_data_platform.event_time_trust.core import (
    EventTimePolicy,
    evaluate_arrivals,
    make_arrival,
    persist_evaluation,
    verify_trusted_current,
)
from manufacturing_data_platform.industrial_source.source import load_metropt_rows
from manufacturing_data_platform.industrial_source.spool import (
    TelemetrySpool,
    write_json_atomic,
)
from manufacturing_data_platform.industrial_source.verification import (
    verify_three_scenarios,
)


def verify_event_time_scenarios(
    *,
    source_csv: str | Path,
    expected_sha256: str,
    output_root: str | Path,
    policy: EventTimePolicy = EventTimePolicy(),
    spark_parity: bool = False,
) -> dict[str, Any]:
    root = Path(output_root)
    collection_root = root / "source_collection"
    verify_three_scenarios(
        source_csv=source_csv,
        expected_sha256=expected_sha256,
        output_root=collection_root,
    )
    selection = load_metropt_rows(source_csv, expected_sha256=expected_sha256)
    normal = _source_order(
        TelemetrySpool(
            collection_root / "spool", "fixture-normal"
        ).load_events()
    )
    quality = _source_order(
        TelemetrySpool(
            collection_root / "spool", "fixture-quality"
        ).load_events()
    )

    rows = _events_by_row(normal)
    scenario_events = {
        "in_order": normal,
        "duplicate_out_of_order": (
            tuple(rows[1] + rows[3] + rows[2]) + (rows[2][0],)
        ),
        "too_late": tuple(rows[2] + rows[3] + rows[1]),
        "missing": tuple(event for event in normal if event != rows[2][-1]),
        "quality": quality,
    }
    reports: dict[str, dict[str, Any]] = {}
    scenario_arrivals: dict[str, tuple[dict[str, Any], ...]] = {}
    evaluations = {}
    current_path = root / "event_time" / "current_trusted.json"
    initial_current: dict[str, Any] | None = None
    for scenario, events in scenario_events.items():
        arrivals = _arrivals(events)
        scenario_arrivals[scenario] = arrivals
        evaluation = evaluate_arrivals(
            scenario=scenario,
            selection=selection,
            arrivals=arrivals,
            policy=policy,
        )
        evaluations[scenario] = evaluation
        reports[scenario] = persist_evaluation(root / "event_time", evaluation)
        if scenario == "in_order":
            initial_current = json.loads(current_path.read_text(encoding="utf-8"))
        elif reports[scenario]["status"] != "publishable":
            assert json.loads(current_path.read_text(encoding="utf-8")) == initial_current

    assert reports["in_order"]["status"] == "publishable"
    assert reports["duplicate_out_of_order"]["status"] == "publishable"
    assert (
        reports["duplicate_out_of_order"]["trusted_dataset"]["dataset_version"]
        == reports["in_order"]["trusted_dataset"]["dataset_version"]
    )
    assert reports["too_late"]["status"] == "reprocess_required"
    assert reports["missing"]["status"] == "incomplete"
    assert reports["quality"]["status"] == "blocked_quality"
    spark_reports: dict[str, dict[str, Any]] = {}
    if spark_parity:
        from manufacturing_data_platform.event_time_trust.spark_parity import (
            SparkEventTimeParityRunner,
            create_local_spark_session,
        )

        spark = create_local_spark_session()
        try:
            runner = SparkEventTimeParityRunner(
                spark=spark,
                output_root=root / "spark_parity",
                policy=policy,
            )
            for scenario, arrivals in scenario_arrivals.items():
                spark_reports[scenario] = runner.run(
                    scenario=scenario,
                    arrivals=arrivals,
                    expected_accepted_event_ids=[
                        event["event_id"]
                        for event in evaluations[scenario].accepted_events
                    ],
                    restart_after=(
                        5 if scenario == "duplicate_out_of_order" else None
                    ),
                )
        finally:
            spark.stop()
    evidence = {
        "verification_version": 1,
        "policy": {
            "version": policy.version,
            "allowed_lateness_seconds": policy.allowed_lateness_seconds,
        },
        "source_file_sha256": selection.source_file_sha256,
        "scenarios": reports,
        "spark_parity": spark_reports,
        "current": json.loads(current_path.read_text(encoding="utf-8")),
    }
    evidence_path = root / "event_time_verification.json"
    write_json_atomic(evidence_path, evidence)
    evidence["evidence_path"] = str(evidence_path)
    return evidence


def verify_retained_event_time_evidence(
    *,
    source_csv: str | Path,
    expected_sha256: str,
    output_root: str | Path,
    require_spark_parity: bool = True,
) -> dict[str, Any]:
    """Read-only verification of retained source, reports, Spark metrics, and digests."""
    source_path = Path(source_csv)
    root = Path(output_root)
    actual_source_sha256 = _sha256_file(source_path)
    if actual_source_sha256 != expected_sha256:
        raise ValueError(
            f"source checksum mismatch: expected={expected_sha256}, "
            f"actual={actual_source_sha256}"
        )
    with source_path.open("rb") as handle:
        source_line_count = sum(1 for _ in handle)

    evidence_path = root / "event_time_verification.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence["source_file_sha256"] != expected_sha256:
        raise ValueError("verification source checksum does not match the source")
    expected_scenarios = {
        "in_order": ("publishable", 9, 0, 0, 0, 0),
        "duplicate_out_of_order": ("publishable", 9, 1, 3, 0, 0),
        "too_late": ("reprocess_required", 6, 0, 3, 3, 3),
        "missing": ("incomplete", 8, 0, 0, 0, 1),
        "quality": ("blocked_quality", 9, 0, 0, 0, 0),
    }
    if set(evidence["scenarios"]) != set(expected_scenarios):
        raise ValueError("verification scenarios do not match the S-MFG-11 contract")

    report_digests: dict[str, str] = {}
    for scenario, expected in expected_scenarios.items():
        report = evidence["scenarios"][scenario]
        actual = (
            report["status"],
            report["accepted_count"],
            report["duplicate_count"],
            report["out_of_order_count"],
            len(report["too_late_event_ids"]),
            len(report["missing_event_ids"]),
        )
        if actual != expected:
            raise ValueError(
                f"scenario={scenario} mismatch: expected={expected}, actual={actual}"
            )
        report_path = (
            root
            / "event_time"
            / "reports"
            / f"{scenario}-{report['report_sha256'][:16]}.json"
        )
        actual_report_sha256 = _sha256_file(report_path)
        if actual_report_sha256 != report["report_sha256"]:
            raise ValueError(f"scenario={scenario} report digest mismatch")
        report_digests[scenario] = actual_report_sha256

    in_order_version = evidence["scenarios"]["in_order"]["trusted_dataset"][
        "dataset_version"
    ]
    disordered_version = evidence["scenarios"]["duplicate_out_of_order"][
        "trusted_dataset"
    ]["dataset_version"]
    if in_order_version != disordered_version:
        raise ValueError("arrival-only disorder changed the trusted dataset version")

    current_path = root / "event_time" / "current_trusted.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if current != evidence["current"]:
        raise ValueError("retained current pointer differs from verification evidence")
    trust_chain = verify_trusted_current(root / "event_time")
    if trust_chain["dataset_version"] != in_order_version:
        raise ValueError("trusted current does not point to the publishable version")

    spark_summary: dict[str, Any] = {}
    spark_reports = evidence.get("spark_parity") or {}
    if require_spark_parity and set(spark_reports) != set(expected_scenarios):
        raise ValueError("retained Spark parity evidence is incomplete")
    for scenario, report in spark_reports.items():
        expected_accepted = expected_scenarios[scenario][1]
        if report["accepted_count"] != expected_accepted:
            raise ValueError(f"scenario={scenario} Spark accepted count mismatch")
        dropped_by_watermark = sum(
            operator.get("numRowsDroppedByWatermark") or 0
            for progress in report["progress"]
            for operator in progress["stateOperators"]
        )
        dropped_duplicates = sum(
            operator.get("customMetrics", {}).get("numDroppedDuplicateRows") or 0
            for progress in report["progress"]
            for operator in progress["stateOperators"]
        )
        spark_summary[scenario] = {
            "spark_version": report["spark_version"],
            "accepted_count": report["accepted_count"],
            "checkpoint_restart_count": report["checkpoint_restart_count"],
            "dropped_by_watermark": dropped_by_watermark,
            "dropped_duplicates": dropped_duplicates,
        }
    if spark_reports:
        if spark_summary["duplicate_out_of_order"] != {
            "spark_version": "3.5.8",
            "accepted_count": 9,
            "checkpoint_restart_count": 1,
            "dropped_by_watermark": 0,
            "dropped_duplicates": 1,
        }:
            raise ValueError("Spark checkpoint/dedup evidence mismatch")
        if spark_summary["too_late"]["dropped_by_watermark"] != 3:
            raise ValueError("Spark too-late watermark evidence mismatch")

    return {
        "verification_version": 1,
        "source_path": str(source_path),
        "source_file_sha256": actual_source_sha256,
        "source_data_row_count": source_line_count - 1,
        "evidence_path": str(evidence_path),
        "evidence_sha256": _sha256_file(evidence_path),
        "report_sha256": report_digests,
        "trusted_current": trust_chain,
        "spark_parity": spark_summary,
    }


def _source_order(events: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event["source_physical_row_number"],
                event["tag_id"],
            ),
        )
    )


def _events_by_row(
    events: tuple[dict[str, Any], ...],
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(event["source_physical_row_number"], []).append(event)
    return grouped


def _arrivals(events: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    values = tuple(events)
    collected_times = [
        datetime.fromisoformat(event["collected_at"].replace("Z", "+00:00"))
        for event in values
    ]
    base = max(collected_times, default=datetime.now(timezone.utc)) + timedelta(
        seconds=1
    )
    return tuple(
        make_arrival(
            event,
            arrival_sequence=position,
            received_at=(base + timedelta(seconds=position))
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        )
        for position, event in enumerate(values, start=1)
    )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--spark-parity", action="store_true")
    args = parser.parse_args(argv)
    evidence = verify_event_time_scenarios(
        source_csv=args.source_csv,
        expected_sha256=args.expected_sha256,
        output_root=args.output_root,
        spark_parity=args.spark_parity,
    )
    for name, report in evidence["scenarios"].items():
        version = (report.get("trusted_dataset") or {}).get("dataset_version", "-")
        print(
            f"{name}: status={report['status']} expected={report['expected_count']} "
            f"accepted={report['accepted_count']} duplicates={report['duplicate_count']} "
            f"out_of_order={report['out_of_order_count']} "
            f"too_late={len(report['too_late_event_ids'])} "
            f"missing={len(report['missing_event_ids'])} version={version[:16]}"
        )
    print(f"source_file_sha256={evidence['source_file_sha256']}")
    print(f"current_dataset_version={evidence['current']['dataset_version']}")
    if evidence["spark_parity"]:
        print(
            "spark_parity="
            + ",".join(
                f"{name}:{report['accepted_count']}"
                for name, report in evidence["spark_parity"].items()
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
