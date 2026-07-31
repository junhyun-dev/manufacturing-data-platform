#!/usr/bin/env python3
"""Build a public-safe Industrial Telemetry Trust Report from accepted runtime JSON.

The report is intentionally one-way:

    accepted local runtime tree
    -> strict, public-safe projection
    -> evidence/runtime-evidence.json
    -> report.html embedding that exact JSON document

The builder never fills a missing observed value with a guessed default. Projection and
rendering finish in memory before either output file is atomically replaced.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_ROOT = REPO_ROOT / ".cache" / "evidence" / "mfg-s11-r2-full-source"
DEFAULT_SOURCE_CSV = (
    REPO_ROOT / ".cache" / "sources" / "metropt3" / "MetroPT3(AirCompressor).csv"
)
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "portfolio" / "industrial-telemetry-trust"

EVIDENCE_VERSION = 1
POLICY_VERSION = "trust-report-policy-v1"
FULL_METROPT_SHA256 = (
    "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24"
)
COLLECTION_EXPECTATIONS = {
    "normal": ("complete", "PUBLISH"),
    "quality": ("blocked_quality", "BLOCKED"),
    "interrupted": ("incomplete", "REPROCESS REQUIRED"),
}
EVENT_TIME_EXPECTATIONS = {
    "in_order": ("publishable", "publish", True),
    "duplicate_out_of_order": ("publishable", "publish", True),
    "too_late": ("reprocess_required", "reprocess", False),
    "missing": ("incomplete", "incomplete", False),
    "quality": ("blocked_quality", "block", False),
}
CLAIM_TRANSLATIONS = {
    "actual public MetroPT values were replayed through a local OPC UA subscription":
        "실제 공개 MetroPT 관측값을 로컬 OPC UA subscription으로 replay했다.",
    "tag, unit, time, quality, mapping, and source identity were preserved":
        "tag·단위·시간·품질·mapping·source identity를 보존했다.",
    "exact bounded expected-versus-observed collection coverage was evaluated":
        "bounded source 범위의 expected/observed 관측 집합을 정확히 비교했다.",
    "bounded source-time and arrival-order classification over canonical telemetry":
        "canonical telemetry의 source time과 arrival order를 bounded 정책으로 분류했다.",
    "exact-set, quality, duplicate, conflict, and too-late publication decisions":
        "exact set·품질·중복·충돌·too-late를 근거로 발행 여부를 판정했다.",
    "content-addressed local trusted dataset versions with an atomic current pointer":
        "content-addressed 로컬 trusted dataset version과 atomic current pointer를 만들었다.",
    "local Spark file micro-batches used event-time watermark state":
        "로컬 Spark file micro-batch에서 event-time watermark state를 사용했다.",
    "Spark accepted event identities matched the engine-independent contract":
        "Spark가 수락한 event identity가 engine-independent 계약과 일치했다.",
    "the selected scenario resumed from a local checkpoint when restart_count=1":
        "restart_count=1 시나리오가 로컬 checkpoint에서 재개됐다.",
    "a physical PLC, sensor, plant network, or production OPC UA server":
        "physical PLC·sensor·plant network·production OPC UA server 연결",
    "automatic reconnect without loss, durable subscriptions, HA, or throughput":
        "무손실 자동 reconnect·durable subscription·HA·throughput",
    "Kafka/Spark streaming, an Iceberg telemetry table, or an AI model":
        "Kafka/Spark streaming·Iceberg telemetry table·AI model",
    "a production lateness SLA or the actual MetroPT sampling contract":
        "production lateness SLA와 실제 MetroPT sampling contract",
    "Kafka partition, rebalance, distributed state-store, or cluster Spark correctness":
        "Kafka partition/rebalance·distributed state-store·cluster Spark correctness",
    "an Iceberg streaming sink, automatic historical correction, or end-to-end exactly-once":
        "Iceberg streaming sink·자동 historical correction·end-to-end exactly-once",
    "Kafka source, Iceberg sink, cluster execution, or production checkpoint storage":
        "Kafka source·Iceberg sink·cluster execution·production checkpoint storage",
    "automatic correction or end-to-end exactly-once across external systems":
        "외부 시스템 전체의 automatic correction 또는 end-to-end exactly-once",
}


class EvidenceBuildError(RuntimeError):
    """Runtime evidence cannot safely support the public report."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise EvidenceBuildError(f"{label} must be a regular non-symlink JSON file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceBuildError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceBuildError(f"{label} must be a JSON object")
    return value


def _single_match(parent: Path, pattern: str, label: str) -> Path:
    matches = sorted(parent.glob(pattern))
    if len(matches) != 1:
        raise EvidenceBuildError(
            f"{label} requires exactly one {pattern!r}; found {len(matches)}"
        )
    path = matches[0]
    if path.is_symlink() or not path.is_file():
        raise EvidenceBuildError(f"{label} must be one regular non-symlink file")
    return path


def _required(value: dict[str, Any], key: str, label: str) -> Any:
    if key not in value:
        raise EvidenceBuildError(f"missing {key!r} in {label}")
    return value[key]


def _int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceBuildError(f"{label} must be a non-negative integer")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceBuildError(f"{label} must be a non-empty string")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise EvidenceBuildError(f"{label} must be a list of non-empty strings")
    return list(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_csv_identity(path: Path) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise EvidenceBuildError("source CSV must be a regular non-symlink file")
    digest = _sha256_file(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            next(reader)
        except StopIteration as exc:
            raise EvidenceBuildError("source CSV has no header") from exc
        rows = sum(1 for _ in reader)
    return digest, rows


def _translate_claims(claims: list[str]) -> list[str]:
    unknown = [claim for claim in claims if claim not in CLAIM_TRANSLATIONS]
    if unknown:
        raise EvidenceBuildError(f"claim translation is missing for {unknown}")
    return [CLAIM_TRANSLATIONS[claim] for claim in claims]


def _claim_list(container: dict[str, Any], key: str, label: str) -> list[str]:
    boundary = container.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise EvidenceBuildError(f"{label}.claim_boundary must be an object")
    return _string_list(boundary.get(key), f"{label}.claim_boundary.{key}")


def _source_identity(report: dict[str, Any], label: str) -> dict[str, Any]:
    source = _required(report, "source", label)
    if not isinstance(source, dict):
        raise EvidenceBuildError(f"{label}.source must be an object")
    identity = {
        "dataset_id": _string(source.get("dataset_id"), f"{label}.dataset_id"),
        "dataset_doi": _string(source.get("dataset_doi"), f"{label}.dataset_doi"),
        "source_file_sha256": _string(
            source.get("source_file_sha256"), f"{label}.source_file_sha256"
        ),
        "selected_physical_rows": [
            _int(item, f"{label}.selected_physical_rows")
            for item in _required(source, "selected_physical_rows", label)
        ],
        "selected_tags": _string_list(
            _required(source, "selected_tags", label), f"{label}.selected_tags"
        ),
    }
    if len(set(identity["selected_physical_rows"])) != len(
        identity["selected_physical_rows"]
    ):
        raise EvidenceBuildError(f"{label}.selected_physical_rows contains duplicates")
    if len(set(identity["selected_tags"])) != len(identity["selected_tags"]):
        raise EvidenceBuildError(f"{label}.selected_tags contains duplicates")
    return identity


def _validate_collection_report(
    scenario: str, report: dict[str, Any]
) -> dict[str, Any]:
    expected_status, action = COLLECTION_EXPECTATIONS[scenario]
    if report.get("report_version") != 1:
        raise EvidenceBuildError(f"{scenario} collection report_version must be 1")
    if report.get("scenario") != scenario or report.get("status") != expected_status:
        raise EvidenceBuildError(
            f"{scenario} collection status must be {expected_status!r}"
        )

    expected = _int(report.get("expected_count"), f"{scenario}.expected_count")
    observed = _int(report.get("observed_count"), f"{scenario}.observed_count")
    missing = _string_list(report.get("missing_event_ids"), f"{scenario}.missing")
    good = _int(report.get("good_count"), f"{scenario}.good_count")
    uncertain = _int(report.get("uncertain_count"), f"{scenario}.uncertain_count")
    bad = _int(report.get("bad_count"), f"{scenario}.bad_count")
    duplicate = _int(report.get("duplicate_count"), f"{scenario}.duplicate_count")
    conflict = _int(report.get("conflict_count"), f"{scenario}.conflict_count")
    unknown = _int(
        report.get("unknown_mapping_count"), f"{scenario}.unknown_mapping_count"
    )
    source = _source_identity(report, f"{scenario} report")
    bounded_expected = len(source["selected_physical_rows"]) * len(
        source["selected_tags"]
    )

    if observed + len(missing) != expected:
        raise EvidenceBuildError(
            f"{scenario} observed + missing must equal expected"
        )
    if expected != bounded_expected:
        raise EvidenceBuildError(
            f"{scenario} expected_count must equal selected rows × tags "
            f"({bounded_expected})"
        )
    if good + uncertain + bad != observed:
        raise EvidenceBuildError(
            f"{scenario} Good + Uncertain + Bad must equal observed"
        )
    if scenario == "normal" and (observed != expected or uncertain or bad):
        raise EvidenceBuildError("normal must be complete and Good-only")
    if scenario == "quality" and not (
        observed == expected and uncertain == 1 and bad == 1
    ):
        raise EvidenceBuildError(
            "quality must be complete and contain exactly one Uncertain and one Bad "
            "observation"
        )
    if scenario == "interrupted" and not (
        observed == len(source["selected_tags"])
        and len(missing) == expected - len(source["selected_tags"])
    ):
        raise EvidenceBuildError(
            "interrupted must retain exactly one selected row across every tag and "
            "mark the remaining sealed identities missing"
        )
    if duplicate or conflict or unknown:
        raise EvidenceBuildError(
            f"{scenario} unexpected duplicate/conflict/unknown mapping count"
        )

    return {
        "scenario": scenario,
        "collection_status": expected_status,
        "operator_action": action,
        "expected_count": expected,
        "observed_count": observed,
        "missing_count": len(missing),
        "missing_event_ids": missing,
        "duplicate_count": duplicate,
        "conflict_count": conflict,
        "unknown_mapping_count": unknown,
        "quality": {"good": good, "uncertain": uncertain, "bad": bad},
        "waiting_notification_count": _int(
            report.get("waiting_notification_count"),
            f"{scenario}.waiting_notification_count",
        ),
    }


def _load_session(
    source_root: Path, scenario: str, report: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    session = source_root / "spool" / f"replay_session_id=fixture-{scenario}"
    seal_path = session / "collection_seal.json"
    seal = _load_json(seal_path, f"{scenario} collection seal")
    event_paths = sorted((session / "events").glob("*.json"))
    if not event_paths or any(path.is_symlink() for path in event_paths):
        raise EvidenceBuildError(f"{scenario} event spool is absent or unsafe")
    events = [_load_json(path, f"{scenario} event") for path in event_paths]

    expected_ids = set(
        _string_list(seal.get("expected_event_ids"), f"{scenario}.expected_event_ids")
    )
    observed_ids = {
        _string(event.get("event_id"), f"{scenario}.event_id") for event in events
    }
    missing_ids = set(
        _string_list(report.get("missing_event_ids"), f"{scenario}.missing_event_ids")
    )
    if len(observed_ids) != len(events):
        raise EvidenceBuildError(f"{scenario} spool contains duplicate event identities")
    if observed_ids | missing_ids != expected_ids or observed_ids & missing_ids:
        raise EvidenceBuildError(
            f"{scenario} spool and report do not exactly cover the sealed set"
        )
    if len(events) != report["observed_count"]:
        raise EvidenceBuildError(f"{scenario} spool count differs from report")
    if seal.get("expected_count") != report["expected_count"]:
        raise EvidenceBuildError(f"{scenario} seal count differs from report")
    return events, seal, f"fixture-{scenario}"


def _validate_event(
    event: dict[str, Any], source_sha256: str, mapping_version: str, label: str
) -> None:
    if event.get("schema_version") != 1:
        raise EvidenceBuildError(f"{label}.schema_version must be 1")
    if event.get("source_file_sha256") != source_sha256:
        raise EvidenceBuildError(f"{label} source checksum differs")
    if event.get("mapping_version") != mapping_version:
        raise EvidenceBuildError(f"{label} mapping version differs")
    for field in (
        "equipment_id",
        "tag_id",
        "source_timestamp",
        "server_timestamp",
        "collected_at",
        "status_name",
        "status_severity",
        "replay_mode",
        "replay_session_id",
    ):
        _string(event.get(field), f"{label}.{field}")
    unit = event.get("engineering_unit")
    if not isinstance(unit, dict):
        raise EvidenceBuildError(f"{label}.engineering_unit must be an object")
    _string(unit.get("display_name"), f"{label}.engineering_unit.display_name")


def _event_time_projection(runtime: dict[str, Any]) -> tuple[list[dict[str, Any]], dict]:
    scenarios = _required(runtime, "scenarios", "event-time verification")
    spark = _required(runtime, "spark_parity", "event-time verification")
    if not isinstance(scenarios, dict) or set(scenarios) != set(EVENT_TIME_EXPECTATIONS):
        raise EvidenceBuildError("event-time verification must contain the five scenarios")
    if not isinstance(spark, dict) or set(spark) != set(EVENT_TIME_EXPECTATIONS):
        raise EvidenceBuildError("Spark parity must contain the five scenarios")

    projected: list[dict[str, Any]] = []
    versions: dict[str, str] = {}
    for name in EVENT_TIME_EXPECTATIONS:
        expected_status, expected_action, should_advance = EVENT_TIME_EXPECTATIONS[name]
        scenario = scenarios[name]
        if (
            scenario.get("scenario") != name
            or scenario.get("status") != expected_status
            or scenario.get("recommended_action") != expected_action
            or scenario.get("current_advanced") is not should_advance
        ):
            raise EvidenceBuildError(f"{name} event-time decision is not accepted")
        accepted = _int(scenario.get("accepted_count"), f"{name}.accepted_count")
        spark_accepted = _int(spark[name].get("accepted_count"), f"{name}.spark accepted")
        if accepted != spark_accepted:
            raise EvidenceBuildError(f"{name} core/Spark accepted count differs")
        trusted = scenario.get("trusted_dataset")
        dataset_version = None
        if should_advance:
            if not isinstance(trusted, dict):
                raise EvidenceBuildError(f"{name} must carry a trusted dataset")
            dataset_version = _string(
                trusted.get("dataset_version"), f"{name}.dataset_version"
            )
            versions[name] = dataset_version
        elif trusted is not None:
            raise EvidenceBuildError(f"{name} must not carry a trusted dataset")
        projected.append(
            {
                "scenario": name,
                "status": expected_status,
                "operator_action": expected_action.upper(),
                "input_count": _int(
                    scenario.get("transport_record_count"), f"{name}.input_count"
                ),
                "accepted_count": accepted,
                "duplicate_count": _int(
                    scenario.get("duplicate_count"), f"{name}.duplicate_count"
                ),
                "out_of_order_count": _int(
                    scenario.get("out_of_order_count"),
                    f"{name}.out_of_order_count",
                ),
                "late_within_policy_count": _int(
                    scenario.get("late_within_policy_count"),
                    f"{name}.late_within_policy_count",
                ),
                "too_late_count": len(
                    _string_list(
                        scenario.get("too_late_event_ids"),
                        f"{name}.too_late_event_ids",
                    )
                ),
                "missing_count": len(
                    _string_list(
                        scenario.get("missing_event_ids"), f"{name}.missing_event_ids"
                    )
                ),
                "conflict_count": _int(
                    scenario.get("conflict_count"), f"{name}.conflict_count"
                ),
                "current_advanced": should_advance,
                "dataset_version": dataset_version,
                "spark": {
                    "version": _string(
                        spark[name].get("spark_version"), f"{name}.spark_version"
                    ),
                    "accepted_count": spark_accepted,
                    "checkpoint_restart_count": _int(
                        spark[name].get("checkpoint_restart_count"),
                        f"{name}.checkpoint_restart_count",
                    ),
                },
            }
        )
    if versions["in_order"] != versions["duplicate_out_of_order"]:
        raise EvidenceBuildError(
            "in-order and duplicate/out-of-order must converge to one dataset version"
        )
    return projected, scenarios["in_order"]["trusted_dataset"]


def _decision_reason(projection: dict[str, Any]) -> str:
    scenario = projection["scenario"]
    if scenario == "normal":
        return (
            f"{projection['observed_count']}개 관측이 모두 존재하고 전부 Good이며 "
            "event-time 입력도 발행 가능하다."
        )
    if scenario == "quality":
        return (
            "관측 집합은 완전하지만 fault injection으로 "
            f"Uncertain {projection['quality']['uncertain']}개와 "
            f"Bad {projection['quality']['bad']}개가 포함됐다."
        )
    if scenario == "interrupted":
        return (
            "Collector 중단으로 sealed identity "
            f"{projection['missing_count']}개가 누락돼 이전 last-good을 유지해야 한다."
        )
    raise EvidenceBuildError(f"no decision reason policy for scenario {scenario!r}")


def build_evidence_document(
    runtime_root: Path,
    source_csv: Path,
    *,
    baseline_commit: str,
    verified_on: str,
) -> dict[str, Any]:
    source_root = runtime_root / "source_collection"
    event_root = runtime_root / "event_time"
    collection_reports: dict[str, dict[str, Any]] = {}
    collection_paths: dict[str, Path] = {}
    projections: dict[str, dict[str, Any]] = {}
    events_by_scenario: dict[str, list[dict[str, Any]]] = {}
    sessions: dict[str, str] = {}

    identities: list[dict[str, Any]] = []
    for scenario in COLLECTION_EXPECTATIONS:
        report_path = _single_match(
            source_root / "reports", f"{scenario}-*.json", f"{scenario} report"
        )
        report = _load_json(report_path, f"{scenario} report")
        collection_reports[scenario] = report
        collection_paths[scenario] = report_path
        projections[scenario] = _validate_collection_report(scenario, report)
        identities.append(_source_identity(report, f"{scenario} report"))
        events, seal, session_id = _load_session(source_root, scenario, report)
        events_by_scenario[scenario] = events
        sessions[scenario] = session_id
        if seal.get("source_file_sha256") != identities[-1]["source_file_sha256"]:
            raise EvidenceBuildError(f"{scenario} seal source checksum differs")

    if any(identity != identities[0] for identity in identities[1:]):
        raise EvidenceBuildError("collection reports do not use one exact source range")
    source = identities[0]
    source_digest, source_rows = _source_csv_identity(source_csv)
    if source_digest != FULL_METROPT_SHA256 or source_digest != source["source_file_sha256"]:
        raise EvidenceBuildError("source CSV identity differs from accepted MetroPT artifact")

    mapping_versions = {
        _string(event.get("mapping_version"), "event.mapping_version")
        for events in events_by_scenario.values()
        for event in events
    }
    if len(mapping_versions) != 1:
        raise EvidenceBuildError("runtime events contain multiple mapping versions")
    mapping_version = mapping_versions.pop()
    for scenario, events in events_by_scenario.items():
        for index, event in enumerate(events):
            _validate_event(
                event,
                source_digest,
                mapping_version,
                f"{scenario}.event[{index}]",
            )

    normal_events = events_by_scenario["normal"]
    equipment_ids = {event["equipment_id"] for event in normal_events}
    replay_modes = {event["replay_mode"] for event in normal_events}
    if len(equipment_ids) != 1 or replay_modes != {"historical_record_replay"}:
        raise EvidenceBuildError("normal event equipment/replay provenance is ambiguous")
    representative: list[dict[str, Any]] = []
    for tag in source["selected_tags"]:
        candidates = [event for event in normal_events if event["tag_id"] == tag]
        if not candidates:
            raise EvidenceBuildError(f"normal spool has no observation for tag {tag}")
        event = min(candidates, key=lambda item: item["source_index"])
        representative.append(
            {
                "tag_id": tag,
                "opcua_node_id": event["opcua_runtime_node_id"],
                "value": event["value"],
                "unit": event["engineering_unit"]["display_name"],
                "source_timestamp": event["source_timestamp"],
                "server_timestamp": event["server_timestamp"],
                "collected_at": event["collected_at"],
                "status": event["status_name"],
            }
        )

    fault_observations = [
        {
            "tag_id": event["tag_id"],
            "source_timestamp": event["source_timestamp"],
            "status": event["status_name"],
            "severity": event["status_severity"],
            "value": event["value"],
            "fault_injected": event["fault_injected"],
        }
        for event in events_by_scenario["quality"]
        if event.get("fault_injected") is True
    ]
    if {item["severity"] for item in fault_observations} != {"uncertain", "bad"}:
        raise EvidenceBuildError("quality scenario must expose injected Uncertain and Bad")

    last_good_path = source_root / "last_good.json"
    last_good = _load_json(last_good_path, "collection last-good")
    normal_sha = _sha256_file(collection_paths["normal"])
    if (
        last_good.get("scenario") != "normal"
        or last_good.get("source_file_sha256") != source_digest
        or last_good.get("report_sha256") != normal_sha
    ):
        raise EvidenceBuildError("collection last-good does not point to normal report")

    event_time_path = runtime_root / "event_time_verification.json"
    event_time = _load_json(event_time_path, "event-time verification")
    if event_time.get("verification_version") != 1:
        raise EvidenceBuildError("event-time verification_version must be 1")
    event_rows, trusted = _event_time_projection(event_time)
    event_source = event_time["scenarios"]["in_order"].get("source")
    if not isinstance(event_source, dict) or any(
        event_source.get(key) != source[key]
        for key in (
            "dataset_id",
            "source_file_sha256",
            "selected_physical_rows",
            "selected_tags",
        )
    ):
        raise EvidenceBuildError("event-time source range differs from collection source")

    current_path = event_root / "current_trusted.json"
    current = _load_json(current_path, "trusted current")
    if (
        current.get("dataset_version") != trusted["dataset_version"]
        or current.get("source_file_sha256") != source_digest
    ):
        raise EvidenceBuildError("trusted current differs from publishable dataset")
    manifest_rel = Path(_string(current.get("manifest_path"), "current.manifest_path"))
    if manifest_rel.is_absolute() or ".." in manifest_rel.parts:
        raise EvidenceBuildError("trusted manifest path is unsafe")
    manifest_path = event_root / manifest_rel
    manifest = _load_json(manifest_path, "trusted manifest")
    manifest_sha = _sha256_file(manifest_path)
    if (
        manifest_sha != current.get("manifest_sha256")
        or manifest.get("dataset_version") != current.get("dataset_version")
        or manifest.get("source_file_sha256") != source_digest
        or manifest.get("mapping_versions") != [mapping_version]
    ):
        raise EvidenceBuildError("trusted current→manifest chain is inconsistent")
    data_path = manifest_path.parent / _string(manifest.get("data_file"), "manifest.data")
    if data_path.is_symlink() or not data_path.is_file():
        raise EvidenceBuildError("trusted data file is absent or unsafe")
    data_sha = _sha256_file(data_path)
    if data_sha != manifest.get("content_sha256"):
        raise EvidenceBuildError("trusted data digest differs from manifest")

    for scenario, projection in projections.items():
        projection["replay_session_id"] = sessions[scenario]
        projection["collection_report_sha256"] = _sha256_file(
            collection_paths[scenario]
        )
        projection["decision_reason"] = _decision_reason(projection)

    verified_claims = list(
        dict.fromkeys(
            _claim_list(collection_reports["normal"], "proves", "normal collection")
            + _claim_list(
                event_time["scenarios"]["in_order"], "proves", "in-order event-time"
            )
            + _claim_list(
                event_time["spark_parity"]["in_order"], "proves", "in-order Spark"
            )
        )
    )
    not_verified_claims = list(
        dict.fromkeys(
            _claim_list(
                collection_reports["normal"], "does_not_prove", "normal collection"
            )
            + _claim_list(
                event_time["scenarios"]["in_order"],
                "does_not_prove",
                "in-order event-time",
            )
            + _claim_list(
                event_time["spark_parity"]["in_order"],
                "does_not_prove",
                "in-order Spark",
            )
        )
    )

    return {
        "evidence_version": EVIDENCE_VERSION,
        "report_contract": "industrial_trust_report_v1",
        "policy_version": POLICY_VERSION,
        "verified_on": verified_on,
        "verification_baseline_commit": baseline_commit,
        "generated_by": "scripts/build_industrial_trust_report.py",
        "source": {
            **source,
            "source_file_rows": source_rows,
            "source_kind": "actual_historical_public_record",
            "live_source": False,
            "historical_time_assumption": normal_events[0][
                "source_time_assumption"
            ],
        },
        "equipment": {
            "equipment_id": equipment_ids.pop(),
            "mapping_version": mapping_version,
            "replay_mode": "historical_record_replay",
            "transport": "local OPC UA subscription",
            "tags": representative,
        },
        "provenance": {
            "actual_record": (
                "값은 checksum을 다시 검증한 공개 MetroPT-3 historical CSV에서 왔다."
            ),
            "replay": (
                "로컬 OPC UA 서버가 historical row를 replay했다. live plant 연결은 아니다."
            ),
            "fault_injection": (
                "품질 이상 시나리오에만 Uncertain 1개와 Bad 1개 StatusCode를 주입했다."
            ),
            "fault_observations": fault_observations,
        },
        "collection_scenarios": [
            projections[name] for name in ("normal", "quality", "interrupted")
        ],
        "event_time_scenarios": event_rows,
        "collection_last_good": {
            "scenario": "normal",
            "report_sha256": normal_sha,
            "preserved_when_blocked_or_incomplete": True,
        },
        "trusted_dataset": {
            "dataset_version": current["dataset_version"],
            "policy_version": current["policy_version"],
            "event_count": _int(manifest.get("event_count"), "manifest.event_count"),
            "mapping_versions": manifest["mapping_versions"],
            "manifest_sha256": manifest_sha,
            "content_sha256": data_sha,
            "current_verified": True,
            "normal_and_disorder_converged": True,
        },
        "input_evidence": {
            "source_collection_reports": {
                name: projections[name]["collection_report_sha256"]
                for name in COLLECTION_EXPECTATIONS
            },
            "collection_last_good": _sha256_file(last_good_path),
            "event_time_verification": _sha256_file(event_time_path),
            "trusted_current": _sha256_file(current_path),
            "trusted_manifest": manifest_sha,
            "trusted_data": data_sha,
        },
        "claim_boundary": {
            "verified": verified_claims,
            "verified_ko": _translate_claims(verified_claims),
            "not_verified": not_verified_claims,
            "not_verified_ko": _translate_claims(not_verified_claims),
        },
    }


REPORT_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Industrial Telemetry Trust Report</title>
<style>
:root {
  color-scheme: light;
  --night:#0b1720; --night-2:#122733; --paper:#f4f1ea; --card:#fffdf8;
  --ink:#17242a; --muted:#68777c; --line:#d8d4ca; --teal:#087f73;
  --teal-soft:#dff4ee; --red:#b5413d; --red-soft:#fde8e5;
  --amber:#a86212; --amber-soft:#fff0d6; --blue:#286c8e; --blue-soft:#e4f1f6;
}
* { box-sizing:border-box; }
html,body { margin:0; background:var(--paper); color:var(--ink);
  font-family:Pretendard,Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }
body { min-width:320px; }
.hero { background:linear-gradient(135deg,var(--night),var(--night-2)); color:white; }
.wrap { width:min(1420px,100%); margin:0 auto; padding:28px 34px 36px; }
.eyebrow { color:#6ee7d3; font-size:12px; font-weight:800; letter-spacing:1.4px;
  text-transform:uppercase; margin:0 0 10px; }
h1 { font-size:clamp(28px,3vw,44px); letter-spacing:-1.2px; line-height:1.08; margin:0; }
h2 { font-size:18px; margin:0 0 14px; letter-spacing:-.2px; }
h3 { font-size:16px; margin:0 0 8px; }
p { line-height:1.58; }
.lead { color:#bed0d7; max-width:880px; margin:14px 0 22px; font-size:15px; }
.meta { display:flex; gap:8px; flex-wrap:wrap; }
.tag { border:1px solid #35515e; background:#12232d; border-radius:999px;
  padding:6px 11px; font:12px ui-monospace,SFMono-Regular,Menlo,monospace; color:#dce8ec; }
.main { width:min(1420px,100%); margin:0 auto; padding:24px 34px 50px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:20px; box-shadow:0 5px 18px rgba(18,31,36,.045); }
.section { margin-bottom:20px; }
.section-head { display:flex; justify-content:space-between; align-items:end; gap:16px;
  margin:0 0 12px; }
.section-head p { margin:0; color:var(--muted); font-size:13px; }
.scenario-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.scenario { border-top:5px solid var(--teal); min-height:294px; }
.scenario.blocked { border-top-color:var(--red); }
.scenario.reprocess { border-top-color:var(--amber); }
.status-line { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.pill { display:inline-flex; align-items:center; border-radius:999px; padding:4px 9px;
  font-size:11px; font-weight:800; letter-spacing:.35px; white-space:nowrap; }
.ok { color:var(--teal); background:var(--teal-soft); }
.bad { color:var(--red); background:var(--red-soft); }
.warn { color:var(--amber); background:var(--amber-soft); }
.info { color:var(--blue); background:var(--blue-soft); }
.action { font-size:21px; font-weight:850; letter-spacing:-.5px; margin:16px 0 4px; }
.reason { color:var(--muted); font-size:13px; min-height:42px; margin:0 0 15px; }
.metrics { display:grid; grid-template-columns:repeat(3,1fr); gap:7px; }
.metric { background:#f4f2ec; padding:9px; border-radius:9px; }
.metric b { display:block; font-size:18px; }
.metric span { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.5px; }
.quality { display:flex; gap:6px; flex-wrap:wrap; margin-top:12px; }
.quality span { font-size:11px; background:#f1eee7; padding:4px 7px; border-radius:6px; }
.provenance { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
.prov { background:#132630; color:white; border-radius:12px; padding:15px; min-height:120px; }
.prov b { color:#6ee7d3; font-size:11px; letter-spacing:.8px; text-transform:uppercase; }
.prov p { color:#c7d7dc; font-size:13px; margin:7px 0 0; }
.two { display:grid; grid-template-columns:1.08fr .92fr; gap:14px; }
table { width:100%; border-collapse:collapse; font-size:12.5px; }
th,td { text-align:left; padding:9px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); text-transform:uppercase; font-size:10px; letter-spacing:.6px; }
tr:last-child td { border-bottom:none; }
code,.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11.5px; }
.hash { display:block; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.trust { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
.trust div { background:#f4f2ec; border-radius:10px; padding:12px; }
.trust b { display:block; font-size:11px; color:var(--muted); margin-bottom:5px; }
.trust code { word-break:break-all; }
.boundary { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.boundary ul { padding-left:18px; margin:6px 0 0; font-size:13px; line-height:1.55; }
.foot { color:var(--muted); font-size:11px; margin-top:14px; }
@media (max-width:1000px) {
  .scenario-grid,.provenance { grid-template-columns:1fr; }
  .two,.boundary { grid-template-columns:1fr; }
  .scenario { min-height:0; }
}
@media (max-width:620px) {
  .wrap,.main { padding-left:16px; padding-right:16px; }
  .metrics,.trust { grid-template-columns:repeat(2,1fr); }
}
</style>
</head>
<body>
<script id="evidence" type="application/json">__EVIDENCE_JSON__</script>
<header class="hero">
  <div class="wrap">
    <p class="eyebrow">Manufacturing Industrial Data Platform</p>
    <h1>Industrial Telemetry<br>Trust Report</h1>
    <p class="lead">실제 산업 기록을 로컬 OPC UA로 재생한 뒤, 의미·품질·완전성·event-time
      evidence를 검토해 trusted dataset을 발행할지 결정하는 읽기 전용 운영 보고서입니다.</p>
    <div class="meta" id="hero-meta"></div>
  </div>
</header>
<main class="main" id="root"></main>
<script>
const E = JSON.parse(document.getElementById('evidence').textContent);
const esc = value => String(value).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const short = value => esc(String(value).slice(0,12) + '…');
const pillClass = action => action === 'PUBLISH' ? 'ok' : action === 'BLOCKED' ? 'bad' : 'warn';
const labels = {normal:'정상 수집',quality:'품질 이상',interrupted:'Collector 중단',
  in_order:'정상 순서',duplicate_out_of_order:'중복·역순',too_late:'Too late',
  missing:'누락',quality_event:'품질 이상'};

document.getElementById('hero-meta').innerHTML = `
  <span class="tag">${esc(E.source.dataset_id)}</span>
  <span class="tag">${esc(E.equipment.equipment_id)}</span>
  <span class="tag">${esc(E.equipment.mapping_version)}</span>
  <span class="tag">evidence v${esc(E.evidence_version)}</span>
  <span class="tag">verified ${esc(E.verified_on)}</span>`;

const scenarioCards = E.collection_scenarios.map(s => {
  const css = s.operator_action === 'BLOCKED' ? 'blocked' :
    s.operator_action === 'REPROCESS REQUIRED' ? 'reprocess' : '';
  return `<article class="card scenario ${css}">
    <div class="status-line"><h3>${esc(labels[s.scenario])}</h3>
      <span class="pill ${pillClass(s.operator_action)}">${esc(s.collection_status)}</span></div>
    <div class="action">${esc(s.operator_action)}</div>
    <p class="reason">${esc(s.decision_reason)}</p>
    <div class="metrics">
      <div class="metric"><b>${s.expected_count}</b><span>Expected</span></div>
      <div class="metric"><b>${s.observed_count}</b><span>Observed</span></div>
      <div class="metric"><b>${s.missing_count}</b><span>Missing</span></div>
    </div>
    <div class="quality">
      <span>Good ${s.quality.good}</span><span>Uncertain ${s.quality.uncertain}</span>
      <span>Bad ${s.quality.bad}</span><span>Unknown mapping ${s.unknown_mapping_count}</span>
    </div>
    <p class="foot">session <code>${esc(s.replay_session_id)}</code><br>
      report <code>${short(s.collection_report_sha256)}</code></p>
  </article>`;
}).join('');

const tagRows = E.equipment.tags.map(t => `<tr><td><b>${esc(t.tag_id)}</b><br>
  <code>${esc(t.opcua_node_id)}</code></td><td>${esc(t.value)} ${esc(t.unit)}</td>
  <td><span class="pill ok">${esc(t.status)}</span></td>
  <td><code>${esc(t.source_timestamp)}</code><br><span class="foot">server ${esc(t.server_timestamp)}
  <br>collected ${esc(t.collected_at)}</span></td></tr>`).join('');

const eventRows = E.event_time_scenarios.map(s => `<tr>
  <td><b>${esc(labels[s.scenario] || s.scenario)}</b></td>
  <td><span class="pill ${pillClass(s.operator_action === 'BLOCK' ? 'BLOCKED' :
    s.operator_action === 'REPROCESS' || s.operator_action === 'INCOMPLETE' ?
    'REPROCESS REQUIRED' : 'PUBLISH')}">${esc(s.status)}</span></td>
  <td>${s.input_count} / ${s.accepted_count}</td><td>${s.duplicate_count}</td>
  <td>${s.out_of_order_count}</td><td>${s.too_late_count}</td><td>${s.missing_count}</td>
  <td>${s.current_advanced ? '<span class="pill ok">advanced</span>' :
    '<span class="pill info">preserved</span>'}</td></tr>`).join('');

document.getElementById('root').innerHTML = `
  <section class="section" id="screen-summary">
    <div class="section-head"><div><h2>Industrial Telemetry Trust Report · 운영 판정</h2>
      <p>동일 source checksum·rows·tags, 서로 다른 수집 결과와 다음 행동</p></div>
      <span class="pill info">READ ONLY · LOCAL EVIDENCE</span></div>
    <div class="scenario-grid">${scenarioCards}</div>
  </section>

  <section class="section" id="screen-source">
    <div class="provenance">
      <div class="prov"><b>01 · Actual record</b><p>${esc(E.provenance.actual_record)}</p></div>
      <div class="prov"><b>02 · Replay</b><p>${esc(E.provenance.replay)}</p></div>
      <div class="prov"><b>03 · Fault injection</b><p>${esc(E.provenance.fault_injection)}</p></div>
    </div>
    <div class="two" style="margin-top:14px">
      <div class="card"><h2>원천 계약과 관측값</h2>
        <table><thead><tr><th>Tag / NodeId</th><th>Value / Unit</th><th>Quality</th>
        <th>Source · Server · Collection time</th></tr></thead><tbody>${tagRows}</tbody></table></div>
      <div class="card"><h2>원천 식별</h2>
        <table><tbody>
          <tr><td>Dataset</td><td><b>${esc(E.source.dataset_id)}</b><br>DOI ${esc(E.source.dataset_doi)}</td></tr>
          <tr><td>Full artifact</td><td>${E.source.source_file_rows.toLocaleString()} rows<br>
            <code class="hash">${esc(E.source.source_file_sha256)}</code></td></tr>
          <tr><td>Bounded range</td><td>rows ${esc(E.source.selected_physical_rows.join(', '))}<br>
            tags ${esc(E.source.selected_tags.join(', '))}</td></tr>
          <tr><td>Time assumption</td><td><code>${esc(E.source.historical_time_assumption)}</code></td></tr>
          <tr><td>Live source</td><td><span class="pill warn">NO · historical replay</span></td></tr>
        </tbody></table>
        <h2 style="margin-top:18px">주입된 품질 이상 관측값</h2>
        <table><tbody>${E.provenance.fault_observations.map(f => `<tr><td>${esc(f.tag_id)}</td>
          <td>${esc(f.source_timestamp)}</td><td><span class="pill ${f.severity === 'bad' ? 'bad':'warn'}">
          ${esc(f.status)}</span></td><td>${f.value === null ? 'null' : esc(f.value)}</td></tr>`).join('')}
        </tbody></table>
      </div>
    </div>
  </section>

  <section class="section" id="screen-event-time">
    <div class="card"><div class="section-head"><div><h2>이벤트 시간 신뢰와 현재 버전</h2>
      <p>Engine-independent decision과 local Spark 3.5.8 accepted identity parity</p></div></div>
      <table><thead><tr><th>Scenario</th><th>Decision</th><th>Input / Accepted</th>
        <th>Duplicate</th><th>Out of order</th><th>Too late</th><th>Missing</th>
        <th>Current</th></tr></thead><tbody>${eventRows}</tbody></table>
      <div class="trust" style="margin-top:16px">
        <div><b>Dataset version</b><code>${short(E.trusted_dataset.dataset_version)}</code></div>
        <div><b>Policy</b><code>${esc(E.trusted_dataset.policy_version)}</code></div>
        <div><b>Trusted events</b><code>${E.trusted_dataset.event_count}</code></div>
        <div><b>Last-good</b><span class="pill ok">verified & preserved</span></div>
      </div>
    </div>
    <div class="card" style="margin-top:14px"><h2>주장 경계</h2>
      <div class="boundary"><div><h3>이 evidence가 증명하는 것</h3>
        <ul>${E.claim_boundary.verified_ko.map(v => `<li>${esc(v)}</li>`).join('')}</ul></div>
        <div><h3>아직 주장하지 않는 것</h3>
        <ul>${E.claim_boundary.not_verified_ko.map(v => `<li>${esc(v)}</li>`).join('')}</ul></div></div>
      <p class="foot">모든 수치와 identity는 embedded <code>industrial_trust_report_v1</code>
        JSON에서 렌더링됩니다. 화면의 행동 표시는 외부 시스템을 변경하지 않는 권고입니다.</p>
    </div>
  </section>`;
</script>
</body>
</html>
"""


def render_report(evidence: dict[str, Any]) -> str:
    embedded = json.dumps(evidence, indent=2, sort_keys=True).replace("</", "<\\/")
    return REPORT_TEMPLATE.replace("__EVIDENCE_JSON__", embedded)


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT))
    parser.add_argument("--source-csv", default=str(DEFAULT_SOURCE_CSV))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--verified-on", required=True)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    evidence = build_evidence_document(
        Path(args.runtime_root),
        Path(args.source_csv),
        baseline_commit=args.baseline_commit,
        verified_on=args.verified_on,
    )
    rendered = render_report(evidence)
    evidence_payload = json.dumps(evidence, indent=2, sort_keys=True) + "\n"

    out_dir = Path(args.out_dir)
    evidence_path = out_dir / "evidence" / "runtime-evidence.json"
    report_path = out_dir / "report.html"
    _atomic_write(evidence_path, evidence_payload)
    _atomic_write(report_path, rendered)

    actions = ", ".join(
        f"{item['scenario']}={item['operator_action']}"
        for item in evidence["collection_scenarios"]
    )
    print(f"evidence: {evidence_path}")
    print(f"report:   {report_path}")
    print(f"actions:  {actions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
