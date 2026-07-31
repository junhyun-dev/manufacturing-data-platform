"""Strict ``industrial_telemetry_v1`` validation and canonical serialization."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping


SCHEMA_VERSION = 1
SOURCE_TIME_ASSUMPTION = (
    "timezone-unknown-wall-clock-encoded-as-utc-for-replay-only"
)
REPLAY_MODE = "historical_record_replay"

REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "equipment_id",
    "tag_id",
    "opcua_namespace_uri",
    "opcua_identifier",
    "opcua_runtime_node_id",
    "value",
    "value_type",
    "engineering_unit",
    "status_code",
    "status_name",
    "status_severity",
    "historical_timestamp_raw",
    "historical_timezone",
    "source_timestamp",
    "source_time_assumption",
    "server_timestamp",
    "collected_at",
    "source_dataset_id",
    "source_dataset_doi",
    "source_file_sha256",
    "source_physical_row_number",
    "source_index",
    "mapping_version",
    "replay_session_id",
    "replay_mode",
    "fault_injected",
}
UNIT_FIELDS = {"namespace_uri", "unit_code", "unit_id", "display_name"}


class TelemetryContractError(ValueError):
    """A value cannot enter the accepted telemetry collection."""


def make_event_id(source_file_sha256: str, physical_row_number: int, tag_id: str) -> str:
    raw = f"{source_file_sha256}:{physical_row_number}:{tag_id}".encode("utf-8")
    return sha256(raw).hexdigest()


def validate_telemetry(event: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - set(event))
    unknown = sorted(set(event) - REQUIRED_FIELDS)
    if missing:
        raise TelemetryContractError(f"missing required fields: {', '.join(missing)}")
    if unknown:
        raise TelemetryContractError(f"unknown fields for schema v1: {', '.join(unknown)}")

    result = dict(event)
    if (
        isinstance(result["schema_version"], bool)
        or result["schema_version"] != SCHEMA_VERSION
    ):
        raise TelemetryContractError(f"schema_version must be {SCHEMA_VERSION}")

    for field in (
        "event_id",
        "equipment_id",
        "tag_id",
        "opcua_namespace_uri",
        "opcua_identifier",
        "opcua_runtime_node_id",
        "value_type",
        "status_name",
        "status_severity",
        "historical_timestamp_raw",
        "source_timestamp",
        "source_time_assumption",
        "server_timestamp",
        "collected_at",
        "source_dataset_id",
        "source_dataset_doi",
        "source_file_sha256",
        "mapping_version",
        "replay_session_id",
        "replay_mode",
    ):
        if not isinstance(result[field], str) or not result[field]:
            raise TelemetryContractError(f"{field} must be a non-empty string")

    if result["historical_timezone"] is not None:
        raise TelemetryContractError("historical_timezone must remain null")
    if result["source_time_assumption"] != SOURCE_TIME_ASSUMPTION:
        raise TelemetryContractError("unexpected source_time_assumption")
    if result["replay_mode"] != REPLAY_MODE:
        raise TelemetryContractError("unexpected replay_mode")
    if result["value_type"] != "Double":
        raise TelemetryContractError("value_type must be Double")
    if result["status_severity"] not in {"good", "uncertain", "bad"}:
        raise TelemetryContractError("status_severity must be good, uncertain, or bad")
    if not isinstance(result["status_code"], int) or isinstance(result["status_code"], bool):
        raise TelemetryContractError("status_code must be an integer")
    if not 0 <= result["status_code"] <= 0xFFFFFFFF:
        raise TelemetryContractError("status_code must be an unsigned 32-bit integer")
    expected_severity = _status_severity(result["status_code"])
    if result["status_severity"] != expected_severity:
        raise TelemetryContractError(
            f"status_severity must match status_code ({expected_severity})"
        )
    if not isinstance(result["fault_injected"], bool):
        raise TelemetryContractError("fault_injected must be boolean")
    for field in ("source_physical_row_number", "source_index"):
        if not isinstance(result[field], int) or isinstance(result[field], bool):
            raise TelemetryContractError(f"{field} must be an integer")
    if result["source_physical_row_number"] < 1 or result["source_index"] < 0:
        raise TelemetryContractError("source row identities are out of range")

    unit = result["engineering_unit"]
    if not isinstance(unit, Mapping):
        raise TelemetryContractError("engineering_unit must be an object")
    unit_missing = sorted(UNIT_FIELDS - set(unit))
    unit_unknown = sorted(set(unit) - UNIT_FIELDS)
    if unit_missing or unit_unknown:
        raise TelemetryContractError(
            f"engineering_unit fields invalid: missing={unit_missing}, unknown={unit_unknown}"
        )
    if (
        not isinstance(unit["namespace_uri"], str)
        or not unit["namespace_uri"]
        or not isinstance(unit["unit_code"], str)
        or not unit["unit_code"]
        or not isinstance(unit["display_name"], str)
        or not unit["display_name"]
        or not isinstance(unit["unit_id"], int)
        or isinstance(unit["unit_id"], bool)
    ):
        raise TelemetryContractError("engineering_unit contains an invalid value")
    result["engineering_unit"] = dict(unit)

    value = result["value"]
    if result["status_severity"] == "bad":
        if value is not None:
            raise TelemetryContractError("Bad status requires value=null")
    elif (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise TelemetryContractError("Good/Uncertain value must be a finite number")
    else:
        result["value"] = float(value)

    parsed_source = _parse_aware_iso(result["source_timestamp"], "source_timestamp")
    parsed_server = _parse_aware_iso(result["server_timestamp"], "server_timestamp")
    parsed_collected = _parse_aware_iso(result["collected_at"], "collected_at")
    try:
        historical_replay_encoding = datetime.strptime(
            result["historical_timestamp_raw"], "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise TelemetryContractError(
            "historical_timestamp_raw must preserve the CSV wall-clock format"
        ) from exc
    if parsed_source.astimezone(timezone.utc) != historical_replay_encoding:
        raise TelemetryContractError(
            "source_timestamp must match the declared replay-only wall-clock encoding"
        )
    if parsed_collected < parsed_server:
        raise TelemetryContractError("collected_at must not precede server_timestamp")

    source_sha = result["source_file_sha256"]
    if len(source_sha) != 64 or any(char not in "0123456789abcdef" for char in source_sha):
        raise TelemetryContractError("source_file_sha256 must be lowercase SHA-256")
    expected_id = make_event_id(
        source_sha, result["source_physical_row_number"], result["tag_id"]
    )
    if result["event_id"] != expected_id:
        raise TelemetryContractError("event_id does not match source row/tag identity")

    return result


def canonical_telemetry_bytes(event: Mapping[str, Any]) -> bytes:
    return json.dumps(
        validate_telemetry(event),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _parse_aware_iso(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TelemetryContractError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise TelemetryContractError(f"{field} must include a timezone")
    return parsed


def _status_severity(status_code: int) -> str:
    severity_bits = status_code & 0xC0000000
    if severity_bits == 0:
        return "good"
    if severity_bits == 0x40000000:
        return "uncertain"
    return "bad"
