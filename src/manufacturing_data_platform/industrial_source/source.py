"""Strict MetroPT-3 source identity, row, and tag mapping contracts."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable


DATASET_ID = "uci-791-metropt3"
DATASET_DOI = "10.24432/C5VW3R"
MAPPING_VERSION = "metropt3-opcua-v1"
EQUIPMENT_ID = "simulated.metropt3.apu-1"
OPCUA_NAMESPACE_URI = "urn:junhyun:manufacturing-data-platform:metropt3:v1"
UN_CEFACT_UNIT_NAMESPACE = "http://www.opcfoundation.org/UA/units/un/cefact"

METROPT3_COLUMNS = (
    "",
    "timestamp",
    "TP2",
    "TP3",
    "H1",
    "DV_pressure",
    "Reservoirs",
    "Oil_temperature",
    "Motor_current",
    "COMP",
    "DV_eletric",
    "Towers",
    "MPG",
    "LPS",
    "Pressure_switch",
    "Oil_level",
    "Caudal_impulses",
)


class MetroPTSourceError(ValueError):
    """The selected source artifact cannot satisfy the source contract."""


@dataclass(frozen=True)
class EngineeringUnit:
    namespace_uri: str
    unit_code: str
    unit_id: int
    display_name: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "namespace_uri": self.namespace_uri,
            "unit_code": self.unit_code,
            "unit_id": self.unit_id,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class TagMapping:
    source_column: str
    tag_id: str
    opcua_identifier: str
    value_type: str
    engineering_unit: EngineeringUnit


METROPT3_TAGS = (
    TagMapping(
        source_column="TP2",
        tag_id="TP2",
        opcua_identifier="MetroPT3.APU.TP2",
        value_type="Double",
        engineering_unit=EngineeringUnit(
            UN_CEFACT_UNIT_NAMESPACE, "BAR", 4_342_098, "bar"
        ),
    ),
    TagMapping(
        source_column="Oil_temperature",
        tag_id="Oil_temperature",
        opcua_identifier="MetroPT3.APU.OilTemperature",
        value_type="Double",
        engineering_unit=EngineeringUnit(
            UN_CEFACT_UNIT_NAMESPACE, "CEL", 4_408_652, "°C"
        ),
    ),
    TagMapping(
        source_column="Motor_current",
        tag_id="Motor_current",
        opcua_identifier="MetroPT3.APU.MotorCurrent",
        value_type="Double",
        engineering_unit=EngineeringUnit(
            UN_CEFACT_UNIT_NAMESPACE, "AMP", 4_279_632, "A"
        ),
    ),
)


@dataclass(frozen=True)
class MetroPTSourceRow:
    physical_row_number: int
    source_index: int
    historical_timestamp_raw: str
    values: dict[str, float]

    @property
    def replay_timestamp(self) -> datetime:
        """Encode timezone-unknown wall time as UTC for replay transport only."""
        return datetime.strptime(
            self.historical_timestamp_raw, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class MetroPTSelection:
    source_path: Path
    source_file_sha256: str
    rows: tuple[MetroPTSourceRow, ...]
    tags: tuple[TagMapping, ...]

    @property
    def expected_event_ids(self) -> tuple[str, ...]:
        from manufacturing_data_platform.industrial_source.contracts import make_event_id

        return tuple(
            make_event_id(
                self.source_file_sha256, row.physical_row_number, tag.tag_id
            )
            for row in self.rows
            for tag in self.tags
        )


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_metropt_rows(
    source_path: str | Path,
    *,
    expected_sha256: str,
    start_physical_row: int = 1,
    row_count: int = 3,
    tags: Iterable[TagMapping] = METROPT3_TAGS,
) -> MetroPTSelection:
    """Load an exact, bounded row range after verifying artifact identity."""
    path = Path(source_path)
    if start_physical_row < 1:
        raise MetroPTSourceError("start_physical_row must be >= 1")
    if row_count < 1:
        raise MetroPTSourceError("row_count must be >= 1")

    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise MetroPTSourceError(
            f"source checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    selected_tags = tuple(tags)
    if not selected_tags:
        raise MetroPTSourceError("at least one selected tag is required")
    if len({tag.tag_id for tag in selected_tags}) != len(selected_tags):
        raise MetroPTSourceError("selected tag_id values must be unique")

    selected_rows: list[MetroPTSourceRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != METROPT3_COLUMNS:
            raise MetroPTSourceError(
                "MetroPT source header does not match the exact distributed CSV schema"
            )
        missing_columns = sorted(
            {tag.source_column for tag in selected_tags} - set(reader.fieldnames or ())
        )
        if missing_columns:
            raise MetroPTSourceError(
                f"selected source columns are absent: {', '.join(missing_columns)}"
            )

        stop = start_physical_row + row_count
        for physical_row_number, raw in enumerate(reader, start=1):
            if physical_row_number < start_physical_row:
                continue
            if physical_row_number >= stop:
                break
            selected_rows.append(
                _parse_source_row(physical_row_number, raw, selected_tags)
            )

    if len(selected_rows) != row_count:
        raise MetroPTSourceError(
            f"selected range expected {row_count} rows, found {len(selected_rows)}"
        )
    timestamps = [row.historical_timestamp_raw for row in selected_rows]
    if len(set(timestamps)) != len(timestamps):
        raise MetroPTSourceError("selected historical timestamps must be unique")

    return MetroPTSelection(
        source_path=path,
        source_file_sha256=actual_sha256,
        rows=tuple(selected_rows),
        tags=selected_tags,
    )


def _parse_source_row(
    physical_row_number: int,
    raw: dict[str, str],
    tags: tuple[TagMapping, ...],
) -> MetroPTSourceRow:
    try:
        source_index = int(raw[""])
    except (TypeError, ValueError) as exc:
        raise MetroPTSourceError(
            f"row {physical_row_number}: source index must be an integer"
        ) from exc

    historical_timestamp_raw = raw["timestamp"]
    try:
        datetime.strptime(historical_timestamp_raw, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError) as exc:
        raise MetroPTSourceError(
            f"row {physical_row_number}: invalid timestamp {historical_timestamp_raw!r}"
        ) from exc

    values: dict[str, float] = {}
    for tag in tags:
        try:
            value = float(raw[tag.source_column])
        except (TypeError, ValueError) as exc:
            raise MetroPTSourceError(
                f"row {physical_row_number}: {tag.source_column} must be numeric"
            ) from exc
        if not math.isfinite(value):
            raise MetroPTSourceError(
                f"row {physical_row_number}: {tag.source_column} must be finite"
            )
        values[tag.tag_id] = value

    return MetroPTSourceRow(
        physical_row_number=physical_row_number,
        source_index=source_index,
        historical_timestamp_raw=historical_timestamp_raw,
        values=values,
    )
