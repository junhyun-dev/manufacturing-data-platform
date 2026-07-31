"""Collection coverage, quality decision, and last-good evidence."""

from __future__ import annotations

import json
import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping

from manufacturing_data_platform.industrial_source.contracts import validate_telemetry
from manufacturing_data_platform.industrial_source.source import MetroPTSelection
from manufacturing_data_platform.industrial_source.spool import write_json_atomic


CLAIM_BOUNDARY = {
    "proves": [
        "actual public MetroPT values were replayed through a local OPC UA subscription",
        "tag, unit, time, quality, mapping, and source identity were preserved",
        "exact bounded expected-versus-observed collection coverage was evaluated",
    ],
    "does_not_prove": [
        "a physical PLC, sensor, plant network, or production OPC UA server",
        "automatic reconnect without loss, durable subscriptions, HA, or throughput",
        "Kafka/Spark streaming, an Iceberg telemetry table, or an AI model",
    ],
}
SAFE_SCENARIO_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def build_collection_report(
    *,
    scenario: str,
    selection: MetroPTSelection,
    events: Iterable[Mapping[str, Any]],
    waiting_notification_count: int,
    duplicate_count: int = 0,
    conflict_count: int = 0,
    overflow_detected: bool = False,
    unknown_mapping_count: int = 0,
) -> dict[str, Any]:
    normalized = [validate_telemetry(event) for event in events]
    expected = set(selection.expected_event_ids)
    observed_ids = [event["event_id"] for event in normalized]
    observed = set(observed_ids)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)

    counts = {"good": 0, "uncertain": 0, "bad": 0}
    for event in normalized:
        counts[event["status_severity"]] += 1

    collection_blockers = {
        "missing_event_ids": missing,
        "unexpected_event_ids": unexpected,
        "overflow_detected": overflow_detected,
        "unknown_mapping_count": unknown_mapping_count,
        "conflict_count": conflict_count,
    }
    if (
        missing
        or unexpected
        or overflow_detected
        or unknown_mapping_count
        or conflict_count
        or len(observed_ids) != len(observed)
    ):
        status = "incomplete"
    elif counts["uncertain"] or counts["bad"]:
        status = "blocked_quality"
    else:
        status = "complete"

    return {
        "report_version": 1,
        "scenario": scenario,
        "status": status,
        "source": {
            "dataset_id": "uci-791-metropt3",
            "dataset_doi": "10.24432/C5VW3R",
            "source_file_sha256": selection.source_file_sha256,
            "selected_physical_rows": [
                row.physical_row_number for row in selection.rows
            ],
            "selected_source_indexes": [row.source_index for row in selection.rows],
            "selected_tags": [tag.tag_id for tag in selection.tags],
        },
        "expected_count": len(expected),
        "observed_count": len(observed),
        "missing_event_ids": missing,
        "unexpected_event_ids": unexpected,
        "good_count": counts["good"],
        "uncertain_count": counts["uncertain"],
        "bad_count": counts["bad"],
        "waiting_notification_count": waiting_notification_count,
        "duplicate_count": duplicate_count,
        "conflict_count": conflict_count,
        "overflow_detected": overflow_detected,
        "unknown_mapping_count": unknown_mapping_count,
        "historical_source_gap_summary": _historical_gap_summary(selection),
        "collection_gap_summary": collection_blockers,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def persist_report(
    output_root: str | Path, report: Mapping[str, Any]
) -> tuple[Path, Path | None]:
    root = Path(output_root)
    scenario = report["scenario"]
    if not isinstance(scenario, str) or not SAFE_SCENARIO_RE.fullmatch(scenario):
        raise ValueError("report scenario must be a path-safe identifier")
    payload = json.dumps(
        report,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    report_digest = sha256(payload).hexdigest()
    report_path = root / "reports" / f"{scenario}-{report_digest[:16]}.json"
    write_json_atomic(report_path, report)

    pointer_path: Path | None = None
    if report["status"] == "complete":
        pointer_path = root / "last_good.json"
        pointer = {
            "report_path": str(report_path.relative_to(root)),
            "report_sha256": report_digest,
            "scenario": scenario,
            "source_file_sha256": report["source"]["source_file_sha256"],
        }
        write_json_atomic(pointer_path, pointer)
    return report_path, pointer_path


def _historical_gap_summary(selection: MetroPTSelection) -> dict[str, Any]:
    parsed = [
        datetime.strptime(row.historical_timestamp_raw, "%Y-%m-%d %H:%M:%S")
        for row in selection.rows
    ]
    deltas = [
        int((current - previous).total_seconds())
        for previous, current in zip(parsed, parsed[1:])
    ]
    return {
        "selected_deltas_seconds": deltas,
        "maximum_selected_delta_seconds": max(deltas, default=None),
        "used_for_collection_completeness": False,
        "reason": "exact selected row/tag identity, not assumed cadence, owns collection coverage",
    }
