from __future__ import annotations

import json
from datetime import timezone
from hashlib import sha256
from pathlib import Path

import pytest

# OPC UA is an explicitly optional runtime.  The base CI installs only
# requirements.txt, so this module must skip cleanly instead of failing during
# collection when the local replay dependency is absent.
pytest.importorskip("asyncua")

from manufacturing_data_platform.industrial_source.contracts import (
    REPLAY_MODE,
    SCHEMA_VERSION,
    SOURCE_TIME_ASSUMPTION,
    TelemetryContractError,
    make_event_id,
    validate_telemetry,
)
from manufacturing_data_platform.industrial_source.report import (
    build_collection_report,
    persist_report,
)
from manufacturing_data_platform.industrial_source.opcua_runtime import (
    IndustrialSourceRuntimeError,
    validate_engineering_unit,
)
from manufacturing_data_platform.industrial_source.source import (
    DATASET_DOI,
    DATASET_ID,
    EQUIPMENT_ID,
    MAPPING_VERSION,
    METROPT3_TAGS,
    OPCUA_NAMESPACE_URI,
    MetroPTSourceError,
    load_metropt_rows,
    sha256_file,
)
from manufacturing_data_platform.industrial_source.spool import (
    TelemetrySpool,
    TelemetrySpoolConflictError,
)
from manufacturing_data_platform.industrial_source.verification import (
    verify_three_scenarios,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "metropt3"
    / "MetroPT3_first_3_rows.csv"
)
FIXTURE_SHA256 = "9863d4cdb7fe84bc74458a90e306fb384d9741be389329ddc434a3eacde5e21a"


@pytest.fixture
def selection():
    return load_metropt_rows(FIXTURE, expected_sha256=FIXTURE_SHA256)


def _event(selection, row_index=0, tag_index=0, **overrides):
    row = selection.rows[row_index]
    tag = selection.tags[tag_index]
    timestamp = row.replay_timestamp.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": make_event_id(
            selection.source_file_sha256, row.physical_row_number, tag.tag_id
        ),
        "equipment_id": EQUIPMENT_ID,
        "tag_id": tag.tag_id,
        "opcua_namespace_uri": OPCUA_NAMESPACE_URI,
        "opcua_identifier": tag.opcua_identifier,
        "opcua_runtime_node_id": f"ns=2;s={tag.opcua_identifier}",
        "value": row.values[tag.tag_id],
        "value_type": "Double",
        "engineering_unit": tag.engineering_unit.as_dict(),
        "status_code": 0,
        "status_name": "Good",
        "status_severity": "good",
        "historical_timestamp_raw": row.historical_timestamp_raw,
        "historical_timezone": None,
        "source_timestamp": timestamp,
        "source_time_assumption": SOURCE_TIME_ASSUMPTION,
        "server_timestamp": "2026-07-29T00:00:00Z",
        "collected_at": "2026-07-29T00:00:01Z",
        "source_dataset_id": DATASET_ID,
        "source_dataset_doi": DATASET_DOI,
        "source_file_sha256": selection.source_file_sha256,
        "source_physical_row_number": row.physical_row_number,
        "source_index": row.source_index,
        "mapping_version": MAPPING_VERSION,
        "replay_session_id": "test-session",
        "replay_mode": REPLAY_MODE,
        "fault_injected": False,
    }
    event.update(overrides)
    return event


def test_fixture_identity_header_rows_tags_and_cadence_are_explicit(selection):
    assert sha256_file(FIXTURE) == FIXTURE_SHA256
    assert [row.physical_row_number for row in selection.rows] == [1, 2, 3]
    assert [row.source_index for row in selection.rows] == [0, 10, 20]
    assert [tag.tag_id for tag in selection.tags] == [
        "TP2",
        "Oil_temperature",
        "Motor_current",
    ]
    assert len(selection.expected_event_ids) == 9
    assert len(set(selection.expected_event_ids)) == 9
    assert [
        int(
            (
                selection.rows[index].replay_timestamp
                - selection.rows[index - 1].replay_timestamp
            ).total_seconds()
        )
        for index in (1, 2)
    ] == [10, 9]


def test_wrong_checksum_fails_before_source_rows_are_accepted():
    with pytest.raises(MetroPTSourceError, match="checksum mismatch"):
        load_metropt_rows(FIXTURE, expected_sha256="0" * 64)


def test_wrong_checksum_starts_no_runtime_and_creates_no_output(tmp_path):
    output_root = tmp_path / "must-not-exist"
    with pytest.raises(MetroPTSourceError, match="checksum mismatch"):
        verify_three_scenarios(
            source_csv=FIXTURE,
            expected_sha256="0" * 64,
            output_root=output_root,
        )
    assert not output_root.exists()


def test_missing_or_unknown_source_column_and_empty_range_are_rejected(tmp_path):
    bad_source = tmp_path / "bad.csv"
    bad_source.write_text("timestamp,TP2\n2020-02-01 00:00:00,1.0\n", encoding="utf-8")
    with pytest.raises(MetroPTSourceError, match="exact distributed CSV schema"):
        load_metropt_rows(
            bad_source,
            expected_sha256=sha256_file(bad_source),
            row_count=1,
        )
    with pytest.raises(MetroPTSourceError, match="row_count must be >= 1"):
        load_metropt_rows(FIXTURE, expected_sha256=FIXTURE_SHA256, row_count=0)


def test_telemetry_contract_keeps_time_identity_unit_and_quality_strict(selection):
    event = validate_telemetry(_event(selection))
    assert event["historical_timezone"] is None
    assert event["source_time_assumption"] == SOURCE_TIME_ASSUMPTION
    assert event["engineering_unit"]["unit_code"] == "BAR"

    with pytest.raises(TelemetryContractError, match="event_id"):
        validate_telemetry(_event(selection, event_id="wrong"))
    with pytest.raises(TelemetryContractError, match="historical_timezone"):
        validate_telemetry(_event(selection, historical_timezone="UTC"))
    with pytest.raises(TelemetryContractError, match="unknown fields"):
        validate_telemetry(_event(selection, invented=True))
    with pytest.raises(TelemetryContractError, match="schema_version"):
        validate_telemetry(_event(selection, schema_version=True))
    with pytest.raises(TelemetryContractError, match="status_severity"):
        validate_telemetry(_event(selection, status_severity="bad", value=None))
    with pytest.raises(TelemetryContractError, match="replay-only"):
        validate_telemetry(
            _event(selection, source_timestamp="2020-02-01T00:00:01Z")
        )
    with pytest.raises(TelemetryContractError, match="must not precede"):
        validate_telemetry(
            _event(
                selection,
                server_timestamp="2026-07-29T00:00:02Z",
                collected_at="2026-07-29T00:00:01Z",
            )
        )

    bad = _event(
        selection,
        status_code=2_157_641_728,
        status_name="BadNoData",
        status_severity="bad",
        value=None,
        fault_injected=True,
    )
    assert validate_telemetry(bad)["value"] is None
    with pytest.raises(TelemetryContractError, match="Bad status requires"):
        validate_telemetry({**bad, "value": 1.0})


def test_engineering_unit_mismatch_is_rejected_before_subscription_acceptance():
    from asyncua import ua

    tag = METROPT3_TAGS[0]
    wrong = ua.EUInformation(
        NamespaceUri=tag.engineering_unit.namespace_uri,
        UnitId=999,
        DisplayName=ua.LocalizedText(tag.engineering_unit.display_name),
        Description=ua.LocalizedText(tag.engineering_unit.unit_code),
    )
    with pytest.raises(IndustrialSourceRuntimeError, match="EngineeringUnits mismatch"):
        validate_engineering_unit(wrong, tag)


def test_spool_reuses_identical_bytes_and_rejects_conflicting_identity(
    selection, tmp_path
):
    spool = TelemetrySpool(tmp_path, "test-session")
    event = _event(selection)
    first = spool.append(event)
    second = spool.append(event)
    assert first.status == "appended"
    assert second.status == "reused"
    assert first.fingerprint == second.fingerprint
    assert spool.duplicate_count == 1
    assert len(spool.load_events()) == 1

    conflict = dict(event)
    conflict["collected_at"] = "2026-07-29T00:00:02Z"
    with pytest.raises(TelemetrySpoolConflictError, match="different canonical bytes"):
        spool.append(conflict)
    assert spool.conflict_count == 1
    assert spool.load_events()[0]["collected_at"] == event["collected_at"]


def test_append_failure_leaves_no_final_or_staging_file(selection, tmp_path, monkeypatch):
    from manufacturing_data_platform.industrial_source import spool as spool_module

    def fail_replace(source, destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(spool_module.os, "replace", fail_replace)
    spool = TelemetrySpool(tmp_path, "test-session")
    with pytest.raises(OSError, match="injected replace failure"):
        spool.append(_event(selection))

    assert list(tmp_path.rglob("*.json")) == []
    assert list(tmp_path.rglob("*.tmp")) == []


def test_report_uses_exact_identity_not_cadence_and_blocks_false_complete(
    selection,
):
    events = [
        _event(selection, row_index=row_index, tag_index=tag_index)
        for row_index in range(3)
        for tag_index in range(3)
    ]
    complete = build_collection_report(
        scenario="normal",
        selection=selection,
        events=events,
        waiting_notification_count=3,
    )
    assert complete["status"] == "complete"
    assert complete["historical_source_gap_summary"]["selected_deltas_seconds"] == [
        10,
        9,
    ]
    assert (
        complete["historical_source_gap_summary"]["used_for_collection_completeness"]
        is False
    )

    missing = build_collection_report(
        scenario="interrupted",
        selection=selection,
        events=events[:-1],
        waiting_notification_count=3,
    )
    assert missing["status"] == "incomplete"
    assert missing["observed_count"] == 8
    assert len(missing["missing_event_ids"]) == 1

    unknown = build_collection_report(
        scenario="unknown-mapping",
        selection=selection,
        events=events,
        waiting_notification_count=3,
        unknown_mapping_count=1,
    )
    assert unknown["status"] == "incomplete"


def test_local_opcua_three_scenarios_preserve_semantics_and_last_good(
    selection, tmp_path
):
    evidence = verify_three_scenarios(
        source_csv=FIXTURE,
        expected_sha256=FIXTURE_SHA256,
        output_root=tmp_path,
    )
    normal = evidence["scenarios"]["normal"]
    quality = evidence["scenarios"]["quality"]
    interrupted = evidence["scenarios"]["interrupted"]

    assert (
        normal["status"],
        normal["expected_count"],
        normal["observed_count"],
        normal["good_count"],
    ) == ("complete", 9, 9, 9)
    assert (
        quality["status"],
        quality["good_count"],
        quality["uncertain_count"],
        quality["bad_count"],
    ) == ("blocked_quality", 7, 1, 1)
    assert (
        interrupted["status"],
        interrupted["observed_count"],
        len(interrupted["missing_event_ids"]),
    ) == ("incomplete", 3, 6)

    assert normal["waiting_notification_count"] == 3
    assert quality["waiting_notification_count"] == 3
    assert interrupted["waiting_notification_count"] == 3

    normal_events = TelemetrySpool(tmp_path / "spool", "fixture-normal").load_events()
    assert len(normal_events) == 9
    # Motor_current row 1 and 2 have the same value. StatusValueTimestamp must
    # still deliver both observations because their source timestamps differ.
    repeated_value_events = [
        event
        for event in normal_events
        if event["tag_id"] == "Motor_current"
        and event["source_physical_row_number"] in {1, 2}
    ]
    assert len(repeated_value_events) == 2
    assert len({event["value"] for event in repeated_value_events}) == 1
    assert len({event["source_timestamp"] for event in repeated_value_events}) == 2

    quality_events = TelemetrySpool(tmp_path / "spool", "fixture-quality").load_events()
    bad_events = [event for event in quality_events if event["status_severity"] == "bad"]
    assert len(bad_events) == 1
    assert bad_events[0]["value"] is None
    assert bad_events[0]["fault_injected"] is True
    assert all(
        event["engineering_unit"]
        == next(
            tag.engineering_unit.as_dict()
            for tag in METROPT3_TAGS
            if tag.tag_id == event["tag_id"]
        )
        for event in normal_events
    )

    last_good_path = tmp_path / "last_good.json"
    last_good = json.loads(last_good_path.read_text(encoding="utf-8"))
    normal_report_path = tmp_path / last_good["report_path"]
    assert last_good["scenario"] == "normal"
    assert last_good["report_sha256"] == sha256(
        normal_report_path.read_bytes()
    ).hexdigest()
    assert normal_report_path.exists()
    assert not quality["last_good_path"]
    assert not interrupted["last_good_path"]

    accepted_bytes = normal_report_path.read_bytes()
    failed_same_scenario = build_collection_report(
        scenario="normal",
        selection=selection,
        events=normal_events[:-1],
        waiting_notification_count=3,
    )
    failed_path, pointer = persist_report(tmp_path, failed_same_scenario)
    assert pointer is None
    assert failed_path != normal_report_path
    assert normal_report_path.read_bytes() == accepted_bytes
    assert json.loads(last_good_path.read_text(encoding="utf-8")) == last_good
