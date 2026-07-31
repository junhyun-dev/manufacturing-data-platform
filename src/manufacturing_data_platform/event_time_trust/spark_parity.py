"""Local PySpark 3.5 event-time/dedup parity over arrival projections."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from manufacturing_data_platform.event_time_trust.core import (
    EventTimePolicy,
    validate_arrival,
)


class SparkParityError(RuntimeError):
    """Local Structured Streaming output differs from the contract seam."""


class SparkEventTimeParityRunner:
    """Run bounded file micro-batches through the actual Spark state store."""

    def __init__(self, *, spark, output_root: str | Path, policy: EventTimePolicy):
        self.spark = spark
        self.output_root = Path(output_root)
        self.policy = policy

    def run(
        self,
        *,
        scenario: str,
        arrivals: Iterable[Mapping[str, Any]],
        expected_accepted_event_ids: Iterable[str],
        restart_after: int | None = None,
    ) -> dict[str, Any]:
        normalized = sorted(
            (validate_arrival(arrival) for arrival in arrivals),
            key=lambda arrival: arrival["arrival_sequence"],
        )
        if restart_after is not None and not 0 < restart_after < len(normalized):
            raise ValueError("restart_after must split the arrival sequence")

        scenario_root = self.output_root / _safe_component(scenario)
        incoming = scenario_root / "incoming"
        checkpoint = scenario_root / "checkpoint"
        output = scenario_root / "accepted"
        incoming.mkdir(parents=True, exist_ok=True)
        progress: list[dict[str, Any]] = []
        restart_count = 0
        query = self._start_query(incoming, checkpoint, output)
        try:
            for position, arrival in enumerate(normalized, start=1):
                _write_arrival_projection(incoming, arrival)
                query.processAllAvailable()
                if query.lastProgress:
                    progress.append(_progress_summary(query.lastProgress))
                if restart_after == position:
                    query.stop()
                    restart_count += 1
                    query = self._start_query(incoming, checkpoint, output)
        finally:
            if query.isActive:
                query.stop()

        accepted = sorted(
            row["event_id"]
            for row in self.spark.read.parquet(str(output))
            .select("event_id")
            .collect()
        )
        expected = sorted(set(expected_accepted_event_ids))
        if accepted != expected:
            raise SparkParityError(
                f"scenario={scenario} Spark accepted IDs differ: "
                f"expected={expected}, actual={accepted}"
            )
        return {
            "spark_version": self.spark.version,
            "scenario": scenario,
            "policy_version": self.policy.version,
            "allowed_lateness_seconds": self.policy.allowed_lateness_seconds,
            "input_count": len(normalized),
            "accepted_count": len(accepted),
            "accepted_event_ids": accepted,
            "checkpoint_restart_count": restart_count,
            "progress": progress,
            "claim_boundary": {
                "proves": [
                    "local Spark file micro-batches used event-time watermark state",
                    "Spark accepted event identities matched the engine-independent contract",
                    "the selected scenario resumed from a local checkpoint when restart_count=1",
                ],
                "does_not_prove": [
                    "Kafka source, Iceberg sink, cluster execution, or production checkpoint storage",
                    "automatic correction or end-to-end exactly-once across external systems",
                ],
            },
        }

    def _start_query(self, incoming: Path, checkpoint: Path, output: Path):
        from pyspark.sql import types as T

        schema = T.StructType(
            [
                T.StructField("arrival_sequence", T.LongType(), False),
                T.StructField("event_id", T.StringType(), False),
                T.StructField("source_timestamp", T.TimestampType(), False),
                T.StructField("status_severity", T.StringType(), False),
                T.StructField("source_file_sha256", T.StringType(), False),
                T.StructField("mapping_version", T.StringType(), False),
            ]
        )
        source = (
            self.spark.readStream.schema(schema)
            .option("maxFilesPerTrigger", 1)
            .json(str(incoming))
        )
        trusted = source.withWatermark(
            "source_timestamp",
            f"{self.policy.allowed_lateness_seconds} seconds",
        ).dropDuplicatesWithinWatermark(["event_id"])
        return (
            trusted.writeStream.format("parquet")
            .outputMode("append")
            .option("path", str(output))
            .option("checkpointLocation", str(checkpoint))
            .start()
        )


def create_local_spark_session():
    """Create the pinned local session without claiming cluster execution."""
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.master("local[2]")
        .appName("manufacturing-s11-event-time-parity")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def _write_arrival_projection(path: Path, arrival: Mapping[str, Any]) -> None:
    event = arrival["event"]
    projection = {
        "arrival_sequence": arrival["arrival_sequence"],
        "event_id": event["event_id"],
        "source_timestamp": event["source_timestamp"],
        "status_severity": event["status_severity"],
        "source_file_sha256": event["source_file_sha256"],
        "mapping_version": event["mapping_version"],
    }
    payload = json.dumps(
        projection,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    target = path / f"{arrival['arrival_sequence']:06d}.json"
    staging = path / f".{target.name}.{uuid4().hex}.tmp"
    try:
        with staging.open("xb") as handle:
            handle.write(payload)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)


def _progress_summary(progress: Mapping[str, Any]) -> dict[str, Any]:
    state_operators = []
    for operator in progress.get("stateOperators", []):
        state_operators.append(
            {
                "numRowsTotal": operator.get("numRowsTotal"),
                "numRowsUpdated": operator.get("numRowsUpdated"),
                "numRowsRemoved": operator.get("numRowsRemoved"),
                "numRowsDroppedByWatermark": operator.get(
                    "numRowsDroppedByWatermark"
                ),
                "customMetrics": {
                    key: value
                    for key, value in (operator.get("customMetrics") or {}).items()
                    if key
                    in {
                        "numDroppedDuplicateRows",
                        "stateOnCurrentVersionSizeBytes",
                    }
                },
            }
        )
    return {
        "batchId": progress.get("batchId"),
        "numInputRows": progress.get("numInputRows"),
        "eventTime": progress.get("eventTime"),
        "stateOperators": state_operators,
    }


def _safe_component(value: str) -> str:
    if not value or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for char in value
    ):
        raise ValueError("scenario must be a path-safe identifier")
    return value
