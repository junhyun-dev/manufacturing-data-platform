from __future__ import annotations

import copy
import json
import re
import struct
from pathlib import Path

import pytest

from scripts.build_industrial_trust_report import (
    EvidenceBuildError,
    _decision_reason,
    _event_time_projection,
    _validate_collection_report,
    build_evidence_document,
    render_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO_ROOT / "docs" / "portfolio" / "industrial-telemetry-trust"
EVIDENCE_PATH = REPORT_DIR / "evidence" / "runtime-evidence.json"
REPORT_PATH = REPORT_DIR / "report.html"
SCREENSHOTS = (
    "01-operator-decisions.png",
    "02-source-provenance.png",
    "03-event-time-trust.png",
)


@pytest.fixture(scope="module")
def evidence():
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_public_evidence_has_three_distinct_operator_decisions(evidence):
    scenarios = {item["scenario"]: item for item in evidence["collection_scenarios"]}
    assert set(scenarios) == {"normal", "quality", "interrupted"}
    assert scenarios["normal"]["operator_action"] == "PUBLISH"
    assert scenarios["normal"]["quality"] == {"good": 9, "uncertain": 0, "bad": 0}
    assert scenarios["quality"]["operator_action"] == "BLOCKED"
    assert scenarios["quality"]["quality"] == {"good": 7, "uncertain": 1, "bad": 1}
    assert scenarios["interrupted"]["operator_action"] == "REPROCESS REQUIRED"
    assert (
        scenarios["interrupted"]["observed_count"],
        scenarios["interrupted"]["missing_count"],
    ) == (3, 6)


def test_public_evidence_preserves_source_and_provenance_boundary(evidence):
    source = evidence["source"]
    assert source["source_file_rows"] == 1_516_948
    assert source["source_kind"] == "actual_historical_public_record"
    assert source["live_source"] is False
    assert source["selected_physical_rows"] == [1, 2, 3]
    assert source["selected_tags"] == ["TP2", "Oil_temperature", "Motor_current"]
    assert evidence["equipment"]["mapping_version"] == "metropt3-opcua-v1"
    assert len(evidence["equipment"]["tags"]) == 3
    faults = evidence["provenance"]["fault_observations"]
    assert {item["severity"] for item in faults} == {"uncertain", "bad"}
    assert all(item["fault_injected"] is True for item in faults)


def test_event_time_decisions_preserve_current_on_non_publishable_inputs(evidence):
    scenarios = {item["scenario"]: item for item in evidence["event_time_scenarios"]}
    assert (
        scenarios["in_order"]["dataset_version"]
        == scenarios["duplicate_out_of_order"]["dataset_version"]
        == evidence["trusted_dataset"]["dataset_version"]
    )
    assert scenarios["duplicate_out_of_order"]["duplicate_count"] == 1
    assert scenarios["duplicate_out_of_order"]["out_of_order_count"] == 3
    assert scenarios["duplicate_out_of_order"]["spark"]["checkpoint_restart_count"] == 1
    for name in ("too_late", "missing", "quality"):
        assert scenarios[name]["current_advanced"] is False
        assert scenarios[name]["dataset_version"] is None


def test_report_embeds_exactly_the_committed_evidence(evidence):
    html = REPORT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="evidence" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match
    embedded = json.loads(match.group(1).replace("<\\/", "</"))
    assert embedded == evidence
    assert render_report(evidence) == html


def test_public_artifacts_do_not_expose_private_runtime_paths(evidence):
    payload = json.dumps(evidence, sort_keys=True)
    assert "/home/" not in payload
    assert ".cache/" not in payload
    assert "actual_historical_public_record" in payload
    assert "historical_record_replay" in payload


def test_collection_projection_rejects_unknown_status_and_impossible_counts(evidence):
    normal = copy.deepcopy(evidence["collection_scenarios"][0])
    source = evidence["source"]
    runtime_shape = {
        "report_version": 1,
        "scenario": "normal",
        "status": "complete",
        "expected_count": normal["expected_count"],
        "observed_count": normal["observed_count"],
        "missing_event_ids": normal["missing_event_ids"],
        "good_count": normal["quality"]["good"],
        "uncertain_count": normal["quality"]["uncertain"],
        "bad_count": normal["quality"]["bad"],
        "duplicate_count": normal["duplicate_count"],
        "conflict_count": normal["conflict_count"],
        "unknown_mapping_count": normal["unknown_mapping_count"],
        "waiting_notification_count": normal["waiting_notification_count"],
        "source": {
            "dataset_id": source["dataset_id"],
            "dataset_doi": source["dataset_doi"],
            "source_file_sha256": source["source_file_sha256"],
            "selected_physical_rows": source["selected_physical_rows"],
            "selected_tags": source["selected_tags"],
        },
    }
    unknown = dict(runtime_shape, status="complete-ish")
    with pytest.raises(EvidenceBuildError, match="status"):
        _validate_collection_report("normal", unknown)
    impossible = dict(runtime_shape, observed_count=10, good_count=10)
    with pytest.raises(EvidenceBuildError, match="observed \\+ missing"):
        _validate_collection_report("normal", impossible)


def test_representative_contract_rejects_consistent_count_drift(evidence):
    source = evidence["source"]

    def report(
        scenario,
        status,
        *,
        expected,
        observed,
        missing,
        good,
        uncertain,
        bad,
    ):
        return {
            "report_version": 1,
            "scenario": scenario,
            "status": status,
            "expected_count": expected,
            "observed_count": observed,
            "missing_event_ids": [f"missing-{index}" for index in range(missing)],
            "good_count": good,
            "uncertain_count": uncertain,
            "bad_count": bad,
            "duplicate_count": 0,
            "conflict_count": 0,
            "unknown_mapping_count": 0,
            "waiting_notification_count": 3,
            "source": {
                "dataset_id": source["dataset_id"],
                "dataset_doi": source["dataset_doi"],
                "source_file_sha256": source["source_file_sha256"],
                "selected_physical_rows": source["selected_physical_rows"],
                "selected_tags": source["selected_tags"],
            },
        }

    with pytest.raises(EvidenceBuildError, match="exactly one Uncertain"):
        _validate_collection_report(
            "quality",
            report(
                "quality",
                "blocked_quality",
                expected=9,
                observed=9,
                missing=0,
                good=6,
                uncertain=2,
                bad=1,
            ),
        )
    with pytest.raises(EvidenceBuildError, match="one selected row"):
        _validate_collection_report(
            "interrupted",
            report(
                "interrupted",
                "incomplete",
                expected=9,
                observed=6,
                missing=3,
                good=6,
                uncertain=0,
                bad=0,
            ),
        )
    with pytest.raises(EvidenceBuildError, match="rows × tags"):
        _validate_collection_report(
            "normal",
            report(
                "normal",
                "complete",
                expected=6,
                observed=6,
                missing=0,
                good=6,
                uncertain=0,
                bad=0,
            ),
        )


def test_decision_reason_uses_projection_counts():
    assert _decision_reason(
        {"scenario": "normal", "observed_count": 12}
    ).startswith("12개")
    assert "Uncertain 2개" in _decision_reason(
        {"scenario": "quality", "quality": {"uncertain": 2, "bad": 3}}
    )
    assert "Bad 3개" in _decision_reason(
        {"scenario": "quality", "quality": {"uncertain": 2, "bad": 3}}
    )
    assert "4개가 누락" in _decision_reason(
        {"scenario": "interrupted", "missing_count": 4}
    )


def test_event_time_projection_rejects_spark_parity_drift(evidence):
    scenarios = {}
    spark = {}
    for item in evidence["event_time_scenarios"]:
        scenarios[item["scenario"]] = {
            "scenario": item["scenario"],
            "status": item["status"],
            "recommended_action": item["operator_action"].lower(),
            "current_advanced": item["current_advanced"],
            "accepted_count": item["accepted_count"],
            "transport_record_count": item["input_count"],
            "duplicate_count": item["duplicate_count"],
            "out_of_order_count": item["out_of_order_count"],
            "late_within_policy_count": item["late_within_policy_count"],
            "too_late_event_ids": ["x"] * item["too_late_count"],
            "missing_event_ids": ["x"] * item["missing_count"],
            "conflict_count": item["conflict_count"],
            "trusted_dataset": (
                {"dataset_version": item["dataset_version"]}
                if item["dataset_version"]
                else None
            ),
        }
        if item["scenario"] == "quality":
            scenarios[item["scenario"]]["recommended_action"] = "block"
        elif item["scenario"] == "missing":
            scenarios[item["scenario"]]["recommended_action"] = "incomplete"
        spark[item["scenario"]] = {
            "accepted_count": item["accepted_count"],
            "spark_version": item["spark"]["version"],
            "checkpoint_restart_count": item["spark"]["checkpoint_restart_count"],
        }
    spark["too_late"]["accepted_count"] += 1
    with pytest.raises(EvidenceBuildError, match="core/Spark"):
        _event_time_projection({"scenarios": scenarios, "spark_parity": spark})


def test_missing_runtime_fails_before_a_caller_writes_outputs(tmp_path):
    existing_evidence = b"previous evidence"
    existing_report = b"previous report"
    output = tmp_path / "public"
    (output / "evidence").mkdir(parents=True)
    evidence_path = output / "evidence" / "runtime-evidence.json"
    report_path = output / "report.html"
    evidence_path.write_bytes(existing_evidence)
    report_path.write_bytes(existing_report)

    with pytest.raises(EvidenceBuildError, match="requires exactly one"):
        build_evidence_document(
            tmp_path / "missing-runtime",
            tmp_path / "missing.csv",
            baseline_commit="deadbeef",
            verified_on="2026-07-31",
        )
    assert evidence_path.read_bytes() == existing_evidence
    assert report_path.read_bytes() == existing_report


def test_three_browser_screenshots_are_non_trivial_pngs():
    for filename in SCREENSHOTS:
        path = REPORT_DIR / "assets" / filename
        assert path.exists(), filename
        raw = path.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", raw[16:24])
        assert width >= 900 and height >= 250
        assert len(raw) > 10_000


def test_reader_walkthrough_contains_problem_flow_evidence_and_limits():
    text = (REPORT_DIR / "README.md").read_text(encoding="utf-8")
    for heading in ("## 문제", "## 구현 흐름", "## 대표 판단", "## 재현", "## 한계"):
        assert heading in text
    for action in ("PUBLISH", "BLOCKED", "REPROCESS REQUIRED"):
        assert action in text
