"""Bounded event-time classification and immutable trusted dataset evidence."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from manufacturing_data_platform.industrial_source.contracts import (
    canonical_telemetry_bytes,
    validate_telemetry,
)
from manufacturing_data_platform.industrial_source.source import MetroPTSelection


ARRIVAL_SCHEMA_VERSION = 1
DEFAULT_POLICY_VERSION = "bounded-event-time-v1"
DEFAULT_ALLOWED_LATENESS_SECONDS = 15
ARRIVAL_FIELDS = {"schema_version", "arrival_sequence", "received_at", "event"}
CURRENT_POINTER_FIELDS = {
    "format_version",
    "dataset_version",
    "manifest_path",
    "manifest_sha256",
    "source_file_sha256",
    "policy_version",
}
CLAIM_BOUNDARY = {
    "proves": [
        "bounded source-time and arrival-order classification over canonical telemetry",
        "exact-set, quality, duplicate, conflict, and too-late publication decisions",
        "content-addressed local trusted dataset versions with an atomic current pointer",
    ],
    "does_not_prove": [
        "a production lateness SLA or the actual MetroPT sampling contract",
        "Kafka partition, rebalance, distributed state-store, or cluster Spark correctness",
        "an Iceberg streaming sink, automatic historical correction, or end-to-end exactly-once",
    ],
}


class EventTimeTrustError(RuntimeError):
    """The event-time run cannot safely advance trusted state."""


class CurrentIntegrityError(EventTimeTrustError):
    """The existing trusted-current chain cannot be verified."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class ArrivalContractError(ValueError):
    """An arrival envelope is invalid."""


@dataclass(frozen=True)
class EventTimePolicy:
    """A versioned bounded-demo policy, not a production source assertion."""

    version: str = DEFAULT_POLICY_VERSION
    allowed_lateness_seconds: int = DEFAULT_ALLOWED_LATENESS_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("policy version must be a non-empty string")
        if (
            isinstance(self.allowed_lateness_seconds, bool)
            or not isinstance(self.allowed_lateness_seconds, int)
            or self.allowed_lateness_seconds < 0
        ):
            raise ValueError("allowed_lateness_seconds must be a non-negative integer")


@dataclass(frozen=True)
class EventTimeEvaluation:
    """A deterministic decision plus the exact events eligible for a dataset version."""

    report: dict[str, Any]
    accepted_events: tuple[dict[str, Any], ...]


def make_arrival(
    event: Mapping[str, Any],
    *,
    arrival_sequence: int,
    received_at: str,
) -> dict[str, Any]:
    """Build and validate one ``telemetry_arrival_v1`` envelope."""
    return validate_arrival(
        {
            "schema_version": ARRIVAL_SCHEMA_VERSION,
            "arrival_sequence": arrival_sequence,
            "received_at": received_at,
            "event": dict(event),
        }
    )


def validate_arrival(value: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(ARRIVAL_FIELDS - set(value))
    unknown = sorted(set(value) - ARRIVAL_FIELDS)
    if missing or unknown:
        raise ArrivalContractError(
            f"arrival fields invalid: missing={missing}, unknown={unknown}"
        )
    if (
        isinstance(value["schema_version"], bool)
        or value["schema_version"] != ARRIVAL_SCHEMA_VERSION
    ):
        raise ArrivalContractError(
            f"arrival schema_version must be {ARRIVAL_SCHEMA_VERSION}"
        )
    sequence = value["arrival_sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise ArrivalContractError("arrival_sequence must be a positive integer")
    if not isinstance(value["received_at"], str) or not value["received_at"]:
        raise ArrivalContractError("received_at must be a non-empty string")
    received_at = _parse_aware_iso(value["received_at"], "received_at")
    event = validate_telemetry(value["event"])
    collected_at = _parse_aware_iso(event["collected_at"], "event.collected_at")
    if received_at < collected_at:
        raise ArrivalContractError("received_at must not precede event.collected_at")
    return {
        "schema_version": ARRIVAL_SCHEMA_VERSION,
        "arrival_sequence": sequence,
        "received_at": _iso_utc(received_at),
        "event": event,
    }


def evaluate_arrivals(
    *,
    scenario: str,
    selection: MetroPTSelection,
    arrivals: Iterable[Mapping[str, Any]],
    policy: EventTimePolicy = EventTimePolicy(),
) -> EventTimeEvaluation:
    """Classify arrivals without allowing watermark state to imply completeness."""
    if not isinstance(scenario, str) or not scenario:
        raise ValueError("scenario must be a non-empty string")

    normalized = [validate_arrival(arrival) for arrival in arrivals]
    sequences = [arrival["arrival_sequence"] for arrival in normalized]
    if len(sequences) != len(set(sequences)):
        raise ArrivalContractError("arrival_sequence values must be unique")
    normalized.sort(key=lambda arrival: arrival["arrival_sequence"])

    expected = set(selection.expected_event_ids)
    seen_payloads: dict[str, bytes] = {}
    observed_ids: set[str] = set()
    accepted: dict[str, dict[str, Any]] = {}
    classifications: list[dict[str, Any]] = []
    duplicate_count = 0
    conflict_count = 0
    out_of_order_count = 0
    late_within_policy_count = 0
    too_late_event_ids: list[str] = []
    unexpected_event_ids: list[str] = []
    max_event_time: datetime | None = None
    delay = timedelta(seconds=policy.allowed_lateness_seconds)

    for arrival in normalized:
        event = arrival["event"]
        event_id = event["event_id"]
        payload = canonical_telemetry_bytes(event)
        event_time = _parse_aware_iso(event["source_timestamp"], "source_timestamp")
        prior_watermark = max_event_time - delay if max_event_time else None
        base_classification = {
            "arrival_sequence": arrival["arrival_sequence"],
            "received_at": arrival["received_at"],
            "event_id": event_id,
            "tag_id": event["tag_id"],
            "source_timestamp": event["source_timestamp"],
            "watermark_before": (
                _iso_utc(prior_watermark) if prior_watermark is not None else None
            ),
        }

        if event_id in seen_payloads:
            if seen_payloads[event_id] == payload:
                duplicate_count += 1
                classifications.append(
                    {**base_classification, "classification": "duplicate"}
                )
            else:
                conflict_count += 1
                classifications.append(
                    {**base_classification, "classification": "conflict"}
                )
            continue

        seen_payloads[event_id] = payload
        observed_ids.add(event_id)
        if event_id not in expected:
            unexpected_event_ids.append(event_id)
            classifications.append(
                {**base_classification, "classification": "unexpected"}
            )
            continue

        is_out_of_order = max_event_time is not None and event_time < max_event_time
        if is_out_of_order:
            out_of_order_count += 1

        if prior_watermark is not None and event_time < prior_watermark:
            too_late_event_ids.append(event_id)
            classifications.append(
                {**base_classification, "classification": "too_late"}
            )
        else:
            if is_out_of_order:
                late_within_policy_count += 1
            accepted[event_id] = event
            classifications.append(
                {
                    **base_classification,
                    "classification": (
                        "late_within_policy" if is_out_of_order else "accepted"
                    ),
                }
            )

        if max_event_time is None or event_time > max_event_time:
            max_event_time = event_time

    missing = sorted(expected - set(accepted))
    unexpected = sorted(set(unexpected_event_ids))
    too_late = sorted(set(too_late_event_ids))
    counts = {"good": 0, "uncertain": 0, "bad": 0}
    for event in accepted.values():
        counts[event["status_severity"]] += 1

    if conflict_count or unexpected or too_late:
        status = "reprocess_required"
        action = "reprocess"
    elif missing:
        status = "incomplete"
        action = "incomplete"
    elif counts["uncertain"] or counts["bad"]:
        status = "blocked_quality"
        action = "block"
    else:
        status = "publishable"
        action = "publish"

    accepted_events = tuple(
        sorted(
            accepted.values(),
            key=lambda event: (
                event["source_timestamp"],
                event["equipment_id"],
                event["tag_id"],
                event["event_id"],
            ),
        )
    )
    report = {
        "report_version": 1,
        "scenario": scenario,
        "status": status,
        "recommended_action": action,
        "policy": {
            "version": policy.version,
            "allowed_lateness_seconds": policy.allowed_lateness_seconds,
            "meaning": "bounded demo policy; not an asserted source sampling SLA",
        },
        "source": {
            "dataset_id": "uci-791-metropt3",
            "source_file_sha256": selection.source_file_sha256,
            "selected_physical_rows": [
                row.physical_row_number for row in selection.rows
            ],
            "selected_tags": [tag.tag_id for tag in selection.tags],
        },
        "expected_count": len(expected),
        "transport_record_count": len(normalized),
        "observed_unique_count": len(observed_ids),
        "accepted_count": len(accepted),
        "missing_event_ids": missing,
        "unexpected_event_ids": unexpected,
        "too_late_event_ids": too_late,
        "duplicate_count": duplicate_count,
        "conflict_count": conflict_count,
        "out_of_order_count": out_of_order_count,
        "late_within_policy_count": late_within_policy_count,
        "good_count": counts["good"],
        "uncertain_count": counts["uncertain"],
        "bad_count": counts["bad"],
        "maximum_event_time": (
            _iso_utc(max_event_time) if max_event_time is not None else None
        ),
        "final_watermark": (
            _iso_utc(max_event_time - delay) if max_event_time is not None else None
        ),
        "classifications": classifications,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return EventTimeEvaluation(report=report, accepted_events=accepted_events)


def persist_evaluation(
    output_root: str | Path,
    evaluation: EventTimeEvaluation,
) -> dict[str, Any]:
    """Persist decision evidence and advance current only for publishable results."""
    root = Path(output_root)
    report = json.loads(json.dumps(evaluation.report))
    current_path = root / "current_trusted.json"
    trusted: dict[str, Any] | None = None
    if report["status"] == "publishable":
        try:
            _verify_existing_current(root, current_path)
        except CurrentIntegrityError as exc:
            evidence_path = _write_current_integrity_failure(
                root=root,
                report=report,
                current_path=current_path,
                error=exc,
            )
            raise EventTimeTrustError(
                f"existing trusted current failed integrity: {exc}; "
                f"failure_evidence={evidence_path.relative_to(root)}"
            ) from exc
        trusted = _publish_trusted_version(root, evaluation.accepted_events, report)
    report["trusted_dataset"] = trusted
    report["publication_state"] = (
        "eligible_manifest_written" if trusted is not None else "not_eligible"
    )

    report_payload = _canonical_json_bytes(report)
    report_digest = sha256(report_payload).hexdigest()
    report_path = (
        root
        / "reports"
        / f"{_safe_component(report['scenario'])}-{report_digest[:16]}.json"
    )
    _write_immutable(report_path, report_payload)

    returned_current_path: Path | None = None
    current_advanced = False
    if trusted is not None:
        pointer = {
            "format_version": 1,
            "dataset_version": trusted["dataset_version"],
            "manifest_path": trusted["manifest_path"],
            "manifest_sha256": trusted["manifest_sha256"],
            "source_file_sha256": report["source"]["source_file_sha256"],
            "policy_version": report["policy"]["version"],
        }
        _write_current_pointer(current_path, _canonical_json_bytes(pointer))
        returned_current_path = current_path
        current_advanced = True

    returned = json.loads(json.dumps(report))
    returned["report_path"] = str(report_path)
    returned["report_sha256"] = report_digest
    returned["current_path"] = (
        str(returned_current_path) if returned_current_path else None
    )
    returned["current_advanced"] = current_advanced
    return returned


def verify_trusted_current(output_root: str | Path) -> dict[str, Any]:
    """Recompute the local current→manifest→data trust chain without mutating it."""
    root = Path(output_root)
    summary = _verify_existing_current(root, root / "current_trusted.json")
    if summary is None:
        raise CurrentIntegrityError(
            "CURRENT_POINTER_MISSING",
            "current_trusted.json does not exist",
        )
    return summary


def _publish_trusted_version(
    root: Path,
    events: tuple[dict[str, Any], ...],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    if not events:
        raise EventTimeTrustError("publishable evaluation must contain events")
    data_payload = b"".join(canonical_telemetry_bytes(event) + b"\n" for event in events)
    content_sha256 = sha256(data_payload).hexdigest()
    mapping_versions = sorted({event["mapping_version"] for event in events})
    version_basis = {
        "format_version": 1,
        "content_sha256": content_sha256,
        "event_count": len(events),
        "event_ids": sorted(event["event_id"] for event in events),
        "source_file_sha256": report["source"]["source_file_sha256"],
        "mapping_versions": mapping_versions,
        "policy_version": report["policy"]["version"],
    }
    dataset_version = sha256(_canonical_json_bytes(version_basis)).hexdigest()
    version_dir = root / "trusted_versions" / f"dataset_version={dataset_version}"
    data_path = version_dir / "trusted_telemetry.jsonl"
    manifest_path = version_dir / "manifest.json"
    manifest = {
        **version_basis,
        "dataset_version": dataset_version,
        "data_file": data_path.name,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    manifest_payload = _canonical_json_bytes(manifest)
    data_created = _write_immutable(data_path, data_payload)
    manifest_created = _write_immutable(manifest_path, manifest_payload)
    return {
        "dataset_version": dataset_version,
        "content_sha256": content_sha256,
        "event_count": len(events),
        "manifest_path": str(manifest_path.relative_to(root)),
        "manifest_sha256": sha256(manifest_payload).hexdigest(),
        "write_status": (
            "created" if data_created and manifest_created else "reused"
        ),
    }


def _write_current_pointer(path: Path, payload: bytes) -> None:
    _write_atomic(path, payload)


def _verify_existing_current(
    root: Path, current_path: Path
) -> dict[str, Any] | None:
    """Refuse to replace a current pointer whose complete local trust chain is broken."""
    if current_path.is_symlink():
        raise CurrentIntegrityError(
            "CURRENT_POINTER_TYPE",
            "current_trusted.json must be a regular file",
        )
    if not current_path.exists():
        return None
    if not current_path.is_file():
        raise CurrentIntegrityError(
            "CURRENT_POINTER_TYPE",
            "current_trusted.json must be a regular file",
        )

    current_payload = current_path.read_bytes()
    pointer = _parse_json_object(current_payload, "current_trusted.json")
    missing = sorted(CURRENT_POINTER_FIELDS - set(pointer))
    unknown = sorted(set(pointer) - CURRENT_POINTER_FIELDS)
    if missing or unknown:
        raise CurrentIntegrityError(
            "CURRENT_POINTER_FIELDS",
            f"missing={missing}, unknown={unknown}",
        )
    if (
        isinstance(pointer["format_version"], bool)
        or pointer["format_version"] != 1
    ):
        raise CurrentIntegrityError(
            "CURRENT_POINTER_VERSION",
            "format_version must be 1",
        )
    for field in (
        "dataset_version",
        "manifest_path",
        "manifest_sha256",
        "source_file_sha256",
        "policy_version",
    ):
        if not isinstance(pointer[field], str) or not pointer[field]:
            raise CurrentIntegrityError(
                "CURRENT_POINTER_VALUE",
                f"{field} must be a non-empty string",
            )
    for field in ("dataset_version", "manifest_sha256", "source_file_sha256"):
        _require_sha256(pointer[field], field)

    expected_manifest_parts = (
        "trusted_versions",
        f"dataset_version={pointer['dataset_version']}",
        "manifest.json",
    )
    manifest_parts = Path(pointer["manifest_path"]).parts
    if manifest_parts != expected_manifest_parts:
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_PATH",
            "manifest_path must be the current dataset's canonical relative path",
        )

    trusted_root = (root / "trusted_versions").resolve()
    manifest_path = root.joinpath(*manifest_parts)
    manifest_resolved = manifest_path.resolve(strict=False)
    try:
        manifest_resolved.relative_to(trusted_root)
    except ValueError as exc:
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_ESCAPE",
            "manifest_path escapes trusted_versions",
        ) from exc
    if any(
        candidate.is_symlink()
        for candidate in (
            root / "trusted_versions",
            manifest_path.parent,
            manifest_path,
        )
    ):
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_SYMLINK",
            "manifest trust chain must not contain symlinks",
        )
    if not manifest_path.is_file():
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_MISSING",
            "referenced manifest does not exist",
        )

    manifest_payload = manifest_path.read_bytes()
    actual_manifest_sha256 = sha256(manifest_payload).hexdigest()
    if actual_manifest_sha256 != pointer["manifest_sha256"]:
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_DIGEST",
            "referenced manifest digest does not match current pointer",
        )
    manifest = _parse_json_object(manifest_payload, "trusted manifest")
    for field in (
        "format_version",
        "dataset_version",
        "content_sha256",
        "event_count",
        "event_ids",
        "source_file_sha256",
        "mapping_versions",
        "policy_version",
        "data_file",
    ):
        if field not in manifest:
            raise CurrentIntegrityError(
                "CURRENT_MANIFEST_FIELDS",
                f"manifest is missing {field}",
            )
    if manifest["format_version"] != 1:
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_VERSION",
            "manifest format_version must be 1",
        )
    for field in ("dataset_version", "content_sha256", "source_file_sha256"):
        if not isinstance(manifest[field], str):
            raise CurrentIntegrityError(
                "CURRENT_MANIFEST_VALUE",
                f"{field} must be a string",
            )
        _require_sha256(manifest[field], field)
    for field in ("dataset_version", "source_file_sha256", "policy_version"):
        if manifest[field] != pointer[field]:
            raise CurrentIntegrityError(
                "CURRENT_MANIFEST_BINDING",
                f"manifest {field} does not match current pointer",
            )
    if (
        isinstance(manifest["event_count"], bool)
        or not isinstance(manifest["event_count"], int)
        or manifest["event_count"] < 1
    ):
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_VALUE",
            "event_count must be a positive integer",
        )
    if not isinstance(manifest["event_ids"], list) or not all(
        isinstance(event_id, str) and event_id for event_id in manifest["event_ids"]
    ):
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_VALUE",
            "event_ids must be a list of non-empty strings",
        )
    if not isinstance(manifest["mapping_versions"], list) or not all(
        isinstance(version, str) and version
        for version in manifest["mapping_versions"]
    ):
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_VALUE",
            "mapping_versions must be a list of non-empty strings",
        )
    if (
        not isinstance(manifest["policy_version"], str)
        or not manifest["policy_version"]
        or manifest["data_file"] != "trusted_telemetry.jsonl"
    ):
        raise CurrentIntegrityError(
            "CURRENT_MANIFEST_VALUE",
            "policy_version or data_file is invalid",
        )

    version_basis = {
        "format_version": manifest["format_version"],
        "content_sha256": manifest["content_sha256"],
        "event_count": manifest["event_count"],
        "event_ids": manifest["event_ids"],
        "source_file_sha256": manifest["source_file_sha256"],
        "mapping_versions": manifest["mapping_versions"],
        "policy_version": manifest["policy_version"],
    }
    expected_dataset_version = sha256(
        _canonical_json_bytes(version_basis)
    ).hexdigest()
    if expected_dataset_version != manifest["dataset_version"]:
        raise CurrentIntegrityError(
            "CURRENT_DATASET_VERSION",
            "manifest fields do not reproduce dataset_version",
        )

    data_path = manifest_path.parent / manifest["data_file"]
    if data_path.is_symlink() or not data_path.is_file():
        raise CurrentIntegrityError(
            "CURRENT_DATA_MISSING",
            "trusted data file is missing or not a regular file",
        )
    data_payload = data_path.read_bytes()
    if sha256(data_payload).hexdigest() != manifest["content_sha256"]:
        raise CurrentIntegrityError(
            "CURRENT_DATA_DIGEST",
            "trusted data digest does not match manifest",
        )
    if len(data_payload.splitlines()) != manifest["event_count"]:
        raise CurrentIntegrityError(
            "CURRENT_DATA_COUNT",
            "trusted data line count does not match manifest",
        )
    data_event_ids: list[str] = []
    data_mapping_versions: set[str] = set()
    for line in data_payload.splitlines():
        event = _parse_json_object(line, "trusted telemetry line")
        try:
            canonical_line = canonical_telemetry_bytes(event)
        except (TypeError, ValueError) as exc:
            raise CurrentIntegrityError(
                "CURRENT_DATA_CONTRACT",
                "trusted data contains an invalid telemetry event",
            ) from exc
        if canonical_line != line:
            raise CurrentIntegrityError(
                "CURRENT_DATA_CANONICAL",
                "trusted data line is not canonical telemetry JSON",
            )
        data_event_ids.append(event["event_id"])
        data_mapping_versions.add(event["mapping_version"])
    if sorted(data_event_ids) != manifest["event_ids"]:
        raise CurrentIntegrityError(
            "CURRENT_DATA_EVENT_IDS",
            "trusted data event IDs do not match manifest",
        )
    if sorted(data_mapping_versions) != manifest["mapping_versions"]:
        raise CurrentIntegrityError(
            "CURRENT_DATA_MAPPING_VERSIONS",
            "trusted data mapping versions do not match manifest",
        )
    return {
        "dataset_version": pointer["dataset_version"],
        "event_count": manifest["event_count"],
        "current_pointer_path": str(current_path),
        "current_pointer_sha256": sha256(current_payload).hexdigest(),
        "manifest_path": str(manifest_path),
        "manifest_sha256": actual_manifest_sha256,
        "data_path": str(data_path),
        "data_sha256": sha256(data_payload).hexdigest(),
    }


def _write_current_integrity_failure(
    *,
    root: Path,
    report: Mapping[str, Any],
    current_path: Path,
    error: CurrentIntegrityError,
) -> Path:
    if current_path.is_symlink():
        symlink_target = os.readlink(current_path)
        current_payload = os.fsencode(symlink_target)
        entry_type = "symlink"
        fingerprint_basis = "symlink_target"
    elif current_path.is_file():
        symlink_target = None
        current_payload = current_path.read_bytes()
        entry_type = "regular_file"
        fingerprint_basis = "file_bytes"
    else:
        symlink_target = None
        current_payload = b""
        entry_type = "missing_or_non_regular"
        fingerprint_basis = "empty"
    evidence = {
        "evidence_version": 1,
        "status": "blocked_current_integrity",
        "recommended_action": "restore_or_repair_last_good_before_publish",
        "scenario": report["scenario"],
        "error_code": error.code,
        "error_detail": error.detail,
        "current_pointer_path": "current_trusted.json",
        "current_pointer_entry_type": entry_type,
        "current_pointer_fingerprint_basis": fingerprint_basis,
        "current_pointer_sha256": sha256(current_payload).hexdigest(),
        "current_pointer_size_bytes": len(current_payload),
        "current_pointer_symlink_target": symlink_target,
        "claim_boundary": {
            "proves": [
                "the existing current pointer was not replaced after integrity failure"
            ],
            "does_not_prove": [
                "automatic repair, remote catalog recovery, or distributed transaction safety"
            ],
        },
    }
    payload = _canonical_json_bytes(evidence)
    digest = sha256(payload).hexdigest()
    path = (
        root
        / "integrity_failures"
        / f"{_safe_component(report['scenario'])}-{digest[:16]}.json"
    )
    _write_immutable(path, payload)
    return path


def _write_immutable(path: Path, payload: bytes) -> bool:
    if path.exists():
        if path.read_bytes() != payload:
            raise EventTimeTrustError(f"immutable evidence conflicts at {path}")
        return False
    _write_atomic(path, payload)
    return True


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with staging.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        staging.unlink(missing_ok=True)


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _parse_json_object(payload: bytes, label: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CurrentIntegrityError(
                    "CURRENT_JSON_DUPLICATE_KEY",
                    f"{label} contains duplicate key {key!r}",
                )
            result[key] = value
        return result

    try:
        value = json.loads(payload, object_pairs_hook=reject_duplicate_keys)
    except CurrentIntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentIntegrityError(
            "CURRENT_JSON_INVALID",
            f"{label} must contain valid UTF-8 JSON",
        ) from exc
    if not isinstance(value, dict):
        raise CurrentIntegrityError(
            "CURRENT_JSON_TYPE",
            f"{label} must contain a JSON object",
        )
    return value


def _require_sha256(value: str, field: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise CurrentIntegrityError(
            "CURRENT_SHA256_VALUE",
            f"{field} must be lowercase SHA-256",
        )


def _safe_component(value: str) -> str:
    if not value or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for char in value
    ):
        raise ValueError("scenario must be a path-safe identifier")
    return value


def _parse_aware_iso(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ArrivalContractError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ArrivalContractError(f"{field} must include a timezone")
    if not math.isfinite(parsed.timestamp()):
        raise ArrivalContractError(f"{field} must be finite")
    return parsed


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
