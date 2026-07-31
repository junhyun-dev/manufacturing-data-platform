"""Bounded industrial-record replay and collection contracts.

The package is deliberately separate from ``machine_event_v1``.  A telemetry
observation and a production event have different grains and quality semantics.
"""

from manufacturing_data_platform.industrial_source.contracts import (
    TelemetryContractError,
    canonical_telemetry_bytes,
    make_event_id,
    validate_telemetry,
)
from manufacturing_data_platform.industrial_source.source import (
    METROPT3_TAGS,
    MetroPTSourceError,
    load_metropt_rows,
)

__all__ = [
    "METROPT3_TAGS",
    "MetroPTSourceError",
    "TelemetryContractError",
    "canonical_telemetry_bytes",
    "load_metropt_rows",
    "make_event_id",
    "validate_telemetry",
]
