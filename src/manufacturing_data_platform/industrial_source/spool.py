"""Telemetry-specific immutable local collection evidence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from manufacturing_data_platform.industrial_source.contracts import (
    canonical_telemetry_bytes,
    validate_telemetry,
)


class TelemetrySpoolError(RuntimeError):
    """Base error for telemetry spool persistence."""


class TelemetrySpoolConflictError(TelemetrySpoolError):
    """A stable event identity already exists with different canonical bytes."""


@dataclass(frozen=True)
class AppendResult:
    status: str
    event_id: str
    fingerprint: str
    path: Path


class TelemetrySpool:
    """One bounded replay session with immutable event files."""

    def __init__(self, root: str | Path, replay_session_id: str):
        if not replay_session_id or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for char in replay_session_id
        ):
            raise TelemetrySpoolError("replay_session_id must be path-safe")
        self.root = Path(root)
        self.session_dir = self.root / f"replay_session_id={replay_session_id}"
        self.events_dir = self.session_dir / "events"
        self.duplicate_count = 0
        self.conflict_count = 0

    def append(self, event: Mapping[str, Any]) -> AppendResult:
        normalized = validate_telemetry(event)
        payload = canonical_telemetry_bytes(normalized)
        event_id = normalized["event_id"]
        target = self.events_dir / f"{event_id}.json"
        fingerprint = sha256(payload).hexdigest()

        if target.exists():
            if target.read_bytes() == payload:
                self.duplicate_count += 1
                return AppendResult("reused", event_id, fingerprint, target)
            self.conflict_count += 1
            raise TelemetrySpoolConflictError(
                f"event_id={event_id} exists with different canonical bytes"
            )

        _atomic_write_bytes(target, payload)
        return AppendResult("appended", event_id, fingerprint, target)

    def load_events(self) -> tuple[dict[str, Any], ...]:
        events = []
        for path in sorted(self.events_dir.glob("*.json")):
            events.append(validate_telemetry(json.loads(path.read_text(encoding="utf-8"))))
        return tuple(events)

    def write_seal(
        self,
        *,
        expected_event_ids: tuple[str, ...],
        source_file_sha256: str,
        mapping_version: str,
    ) -> Path:
        seal = {
            "format_version": 1,
            "expected_event_ids": sorted(expected_event_ids),
            "expected_count": len(expected_event_ids),
            "source_file_sha256": source_file_sha256,
            "mapping_version": mapping_version,
        }
        if len(set(expected_event_ids)) != len(expected_event_ids):
            raise TelemetrySpoolError("expected_event_ids must be unique")
        path = self.session_dir / "collection_seal.json"
        payload = _canonical_json_bytes(seal)
        if path.exists() and path.read_bytes() != payload:
            raise TelemetrySpoolConflictError(
                "collection seal already exists with different bytes"
            )
        if not path.exists():
            _atomic_write_bytes(path, payload)
        return path


def write_json_atomic(path: str | Path, value: Mapping[str, Any]) -> Path:
    target = Path(path)
    _atomic_write_bytes(target, _canonical_json_bytes(value))
    return target


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with staging.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, path)
        _fsync_directory(path.parent)
    finally:
        staging.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
