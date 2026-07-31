from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

# These scenarios start from the OPC UA collection verifier.  Keep that runtime
# optional in the requirements-only base CI job.
pytest.importorskip("asyncua")

from manufacturing_data_platform.event_time_trust import core
from manufacturing_data_platform.event_time_trust.core import (
    ArrivalContractError,
    EventTimePolicy,
    EventTimeTrustError,
    evaluate_arrivals,
    make_arrival,
    persist_evaluation,
    verify_trusted_current,
)
from manufacturing_data_platform.event_time_trust.verification import (
    verify_event_time_scenarios,
    verify_retained_event_time_evidence,
)
from manufacturing_data_platform.industrial_source.source import load_metropt_rows
from manufacturing_data_platform.industrial_source.spool import TelemetrySpool
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


@pytest.fixture(scope="module")
def collected(tmp_path_factory):
    root = tmp_path_factory.mktemp("s11-collected")
    verify_three_scenarios(
        source_csv=FIXTURE,
        expected_sha256=FIXTURE_SHA256,
        output_root=root,
    )
    selection = load_metropt_rows(FIXTURE, expected_sha256=FIXTURE_SHA256)
    normal = _source_order(
        TelemetrySpool(root / "spool", "fixture-normal").load_events()
    )
    quality = _source_order(
        TelemetrySpool(root / "spool", "fixture-quality").load_events()
    )
    return selection, normal, quality


def _source_order(events):
    return tuple(
        sorted(
            events,
            key=lambda event: (
                event["source_physical_row_number"],
                event["tag_id"],
            ),
        )
    )


def _arrivals(events):
    values = tuple(events)
    base = max(
        datetime.fromisoformat(event["collected_at"].replace("Z", "+00:00"))
        for event in values
    ) + timedelta(seconds=1)
    return tuple(
        make_arrival(
            event,
            arrival_sequence=index,
            received_at=(base + timedelta(seconds=index))
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        )
        for index, event in enumerate(values, start=1)
    )


def _group_rows(events):
    grouped = {}
    for event in events:
        grouped.setdefault(event["source_physical_row_number"], []).append(event)
    return grouped


def test_arrival_contract_separates_arrival_from_source_time(collected):
    _, normal, _ = collected
    arrival = _arrivals(normal[:1])[0]
    assert arrival["arrival_sequence"] == 1
    assert arrival["received_at"] != arrival["event"]["source_timestamp"]

    with pytest.raises(ArrivalContractError, match="positive integer"):
        make_arrival(normal[0], arrival_sequence=0, received_at=arrival["received_at"])
    with pytest.raises(ArrivalContractError, match="timezone"):
        make_arrival(normal[0], arrival_sequence=1, received_at="2026-07-30T00:00:00")


def test_arrival_sequences_must_be_unique(collected):
    selection, normal, _ = collected
    arrivals = list(_arrivals(normal[:2]))
    arrivals[1]["arrival_sequence"] = arrivals[0]["arrival_sequence"]
    with pytest.raises(ArrivalContractError, match="must be unique"):
        evaluate_arrivals(
            scenario="duplicate-sequence",
            selection=selection,
            arrivals=arrivals,
        )


def test_in_order_and_duplicate_out_of_order_converge_to_same_version(
    collected, tmp_path
):
    selection, normal, _ = collected
    rows = _group_rows(normal)
    in_order = evaluate_arrivals(
        scenario="in-order",
        selection=selection,
        arrivals=_arrivals(normal),
    )
    disordered_events = tuple(rows[1] + rows[3] + rows[2]) + (rows[2][0],)
    disordered = evaluate_arrivals(
        scenario="disordered",
        selection=selection,
        arrivals=_arrivals(disordered_events),
    )
    first = persist_evaluation(tmp_path, in_order)
    second = persist_evaluation(tmp_path, disordered)

    assert first["status"] == "publishable"
    assert second["status"] == "publishable"
    assert second["duplicate_count"] == 1
    assert second["late_within_policy_count"] == 3
    assert (
        first["trusted_dataset"]["dataset_version"]
        == second["trusted_dataset"]["dataset_version"]
    )
    assert second["trusted_dataset"]["write_status"] == "reused"


def test_too_late_missing_and_quality_do_not_advance_current(collected, tmp_path):
    selection, normal, quality = collected
    rows = _group_rows(normal)
    good = persist_evaluation(
        tmp_path,
        evaluate_arrivals(
            scenario="good",
            selection=selection,
            arrivals=_arrivals(normal),
        ),
    )
    current_path = Path(good["current_path"])
    before = current_path.read_bytes()

    too_late = persist_evaluation(
        tmp_path,
        evaluate_arrivals(
            scenario="too-late",
            selection=selection,
            arrivals=_arrivals(tuple(rows[2] + rows[3] + rows[1])),
        ),
    )
    missing = persist_evaluation(
        tmp_path,
        evaluate_arrivals(
            scenario="missing",
            selection=selection,
            arrivals=_arrivals(normal[:-1]),
        ),
    )
    blocked = persist_evaluation(
        tmp_path,
        evaluate_arrivals(
            scenario="quality",
            selection=selection,
            arrivals=_arrivals(quality),
        ),
    )

    assert too_late["status"] == "reprocess_required"
    assert len(too_late["too_late_event_ids"]) == 3
    assert missing["status"] == "incomplete"
    assert len(missing["missing_event_ids"]) == 1
    assert blocked["status"] == "blocked_quality"
    assert (blocked["good_count"], blocked["uncertain_count"], blocked["bad_count"]) == (
        7,
        1,
        1,
    )
    assert current_path.read_bytes() == before


def test_exact_watermark_boundary_is_accepted(collected):
    selection, normal, _ = collected
    rows = _group_rows(normal)
    evaluation = evaluate_arrivals(
        scenario="boundary",
        selection=selection,
        arrivals=_arrivals(tuple(rows[2] + rows[3] + rows[1])),
        policy=EventTimePolicy(
            version="boundary-19-seconds", allowed_lateness_seconds=19
        ),
    )
    assert evaluation.report["status"] == "publishable"
    assert evaluation.report["too_late_event_ids"] == []
    assert evaluation.report["late_within_policy_count"] == 3


def test_first_representable_second_before_watermark_is_too_late(collected):
    selection, normal, _ = collected
    rows = _group_rows(normal)
    evaluation = evaluate_arrivals(
        scenario="one-second-before-boundary",
        selection=selection,
        arrivals=_arrivals(tuple(rows[2] + rows[3] + rows[1])),
        policy=EventTimePolicy(
            version="boundary-18-seconds", allowed_lateness_seconds=18
        ),
    )
    assert evaluation.report["status"] == "reprocess_required"
    assert len(evaluation.report["too_late_event_ids"]) == 3


def test_same_identity_different_canonical_bytes_is_conflict(collected):
    selection, normal, _ = collected
    changed = dict(normal[0])
    collected_at = datetime.fromisoformat(
        changed["collected_at"].replace("Z", "+00:00")
    ) + timedelta(seconds=1)
    changed["collected_at"] = collected_at.isoformat().replace("+00:00", "Z")
    evaluation = evaluate_arrivals(
        scenario="conflict",
        selection=selection,
        arrivals=_arrivals((normal[0], changed) + normal[1:]),
    )
    assert evaluation.report["status"] == "reprocess_required"
    assert evaluation.report["conflict_count"] == 1


@pytest.mark.parametrize(
    ("corruption", "expected_code"),
    [
        ("missing_manifest", "CURRENT_MANIFEST_MISSING"),
        ("changed_manifest", "CURRENT_MANIFEST_DIGEST"),
        ("pointer_digest", "CURRENT_MANIFEST_DIGEST"),
        ("escaping_path", "CURRENT_MANIFEST_PATH"),
        ("missing_data", "CURRENT_DATA_MISSING"),
        ("changed_data", "CURRENT_DATA_DIGEST"),
    ],
)
def test_invalid_existing_current_blocks_replacement_with_failure_evidence(
    collected, tmp_path, corruption, expected_code
):
    selection, normal, _ = collected
    root = tmp_path / corruption
    first = persist_evaluation(
        root,
        evaluate_arrivals(
            scenario="first",
            selection=selection,
            arrivals=_arrivals(normal),
        ),
    )
    current_path = Path(first["current_path"])
    pointer = json.loads(current_path.read_text(encoding="utf-8"))
    manifest_path = root / pointer["manifest_path"]
    if corruption == "missing_manifest":
        manifest_path.unlink()
    elif corruption == "changed_manifest":
        manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")
    elif corruption == "pointer_digest":
        pointer["manifest_sha256"] = "0" * 64
        current_path.write_text(
            json.dumps(pointer, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    elif corruption == "escaping_path":
        pointer["manifest_path"] = "../outside/manifest.json"
        current_path.write_text(
            json.dumps(pointer, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    elif corruption == "missing_data":
        (manifest_path.parent / "trusted_telemetry.jsonl").unlink()
    else:
        data_path = manifest_path.parent / "trusted_telemetry.jsonl"
        data_path.write_bytes(data_path.read_bytes() + b"\n")

    before = current_path.read_bytes()
    version_count = len(list((root / "trusted_versions").iterdir()))
    with pytest.raises(EventTimeTrustError, match=expected_code):
        persist_evaluation(
            root,
            evaluate_arrivals(
                scenario="replacement",
                selection=selection,
                arrivals=_arrivals(normal),
                policy=EventTimePolicy(
                    version="bounded-event-time-v2", allowed_lateness_seconds=20
                ),
            ),
        )

    assert current_path.read_bytes() == before
    assert len(list((root / "trusted_versions").iterdir())) == version_count
    failures = list((root / "integrity_failures").glob("replacement-*.json"))
    assert len(failures) == 1
    evidence = json.loads(failures[0].read_text(encoding="utf-8"))
    assert evidence["status"] == "blocked_current_integrity"
    assert evidence["error_code"] == expected_code
    assert evidence["current_pointer_sha256"] == sha256(before).hexdigest()


def test_manifest_write_failure_preserves_previous_current(
    collected, tmp_path, monkeypatch
):
    selection, normal, _ = collected
    first = persist_evaluation(
        tmp_path,
        evaluate_arrivals(
            scenario="first",
            selection=selection,
            arrivals=_arrivals(normal),
        ),
    )
    current_path = Path(first["current_path"])
    before = current_path.read_bytes()
    original_write_immutable = core._write_immutable

    def fail_manifest(path, payload):
        if path.name == "manifest.json":
            raise OSError("injected manifest write failure")
        return original_write_immutable(path, payload)

    monkeypatch.setattr(core, "_write_immutable", fail_manifest)
    with pytest.raises(OSError, match="injected manifest write failure"):
        persist_evaluation(
            tmp_path,
            evaluate_arrivals(
                scenario="new-policy",
                selection=selection,
                arrivals=_arrivals(normal),
                policy=EventTimePolicy(
                    version="bounded-event-time-v2", allowed_lateness_seconds=20
                ),
            ),
        )
    assert current_path.read_bytes() == before


@pytest.mark.parametrize("target_exists", [False, True])
def test_current_pointer_symlink_blocks_publish_and_direct_verification(
    collected, tmp_path, target_exists
):
    selection, normal, _ = collected
    root = tmp_path / ("existing-target" if target_exists else "dangling-target")
    first = persist_evaluation(
        root,
        evaluate_arrivals(
            scenario="first",
            selection=selection,
            arrivals=_arrivals(normal),
        ),
    )
    current_path = Path(first["current_path"])
    target_path = root / (
        "preserved-current.json" if target_exists else "missing-current-target.json"
    )
    if target_exists:
        current_path.rename(target_path)
        target_before = target_path.read_bytes()
    else:
        current_path.unlink()
        target_before = None
    current_path.symlink_to(target_path.name)
    link_before = os.readlink(current_path)
    version_count = len(list((root / "trusted_versions").iterdir()))

    with pytest.raises(EventTimeTrustError, match="CURRENT_POINTER_TYPE"):
        verify_trusted_current(root)
    with pytest.raises(EventTimeTrustError, match="CURRENT_POINTER_TYPE"):
        persist_evaluation(
            root,
            evaluate_arrivals(
                scenario="symlink-replacement",
                selection=selection,
                arrivals=_arrivals(normal),
                policy=EventTimePolicy(
                    version="bounded-event-time-v2", allowed_lateness_seconds=20
                ),
            ),
        )

    assert current_path.is_symlink()
    assert os.readlink(current_path) == link_before
    if target_exists:
        assert target_path.read_bytes() == target_before
    else:
        assert not target_path.exists()
    assert len(list((root / "trusted_versions").iterdir())) == version_count
    failures = list(
        (root / "integrity_failures").glob("symlink-replacement-*.json")
    )
    assert len(failures) == 1
    evidence = json.loads(failures[0].read_text(encoding="utf-8"))
    assert evidence["error_code"] == "CURRENT_POINTER_TYPE"
    assert evidence["current_pointer_entry_type"] == "symlink"
    assert evidence["current_pointer_fingerprint_basis"] == "symlink_target"
    assert evidence["current_pointer_symlink_target"] == link_before
    assert evidence["current_pointer_sha256"] == sha256(
        os.fsencode(link_before)
    ).hexdigest()


def test_pointer_failure_preserves_previous_current(collected, tmp_path, monkeypatch):
    selection, normal, _ = collected
    first = persist_evaluation(
        tmp_path,
        evaluate_arrivals(
            scenario="first",
            selection=selection,
            arrivals=_arrivals(normal),
        ),
    )
    current_path = Path(first["current_path"])
    before = current_path.read_bytes()

    def fail_pointer(path, payload):
        raise OSError("injected current pointer failure")

    monkeypatch.setattr(core, "_write_current_pointer", fail_pointer)
    with pytest.raises(OSError, match="injected current pointer failure"):
        persist_evaluation(
            tmp_path,
            evaluate_arrivals(
                scenario="new-policy",
                selection=selection,
                arrivals=_arrivals(normal),
                policy=EventTimePolicy(
                    version="bounded-event-time-v2", allowed_lateness_seconds=20
                ),
            ),
        )
    assert current_path.read_bytes() == before


def test_representative_verification_reports_five_operator_decisions(tmp_path):
    evidence = verify_event_time_scenarios(
        source_csv=FIXTURE,
        expected_sha256=FIXTURE_SHA256,
        output_root=tmp_path,
    )
    scenarios = evidence["scenarios"]
    assert scenarios["in_order"]["status"] == "publishable"
    assert scenarios["duplicate_out_of_order"]["status"] == "publishable"
    assert scenarios["too_late"]["status"] == "reprocess_required"
    assert scenarios["missing"]["status"] == "incomplete"
    assert scenarios["quality"]["status"] == "blocked_quality"
    assert (
        evidence["current"]["dataset_version"]
        == scenarios["in_order"]["trusted_dataset"]["dataset_version"]
    )
    json.loads(
        (tmp_path / "event_time/current_trusted.json").read_text(encoding="utf-8")
    )
    retained = verify_retained_event_time_evidence(
        source_csv=FIXTURE,
        expected_sha256=FIXTURE_SHA256,
        output_root=tmp_path,
        require_spark_parity=False,
    )
    assert retained["source_data_row_count"] == 3
    assert (
        retained["trusted_current"]["dataset_version"]
        == evidence["current"]["dataset_version"]
    )
