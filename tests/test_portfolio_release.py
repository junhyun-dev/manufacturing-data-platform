"""Contract tests for the committed portfolio release package.

Scope, stated plainly: this validates the *committed evidence package* — that the JSON parses, says
what the reader-facing pages say, and that the pages link to files that exist. It does **not**
execute Kafka, Spark, Iceberg, or Airflow, and passing it is not evidence that any runtime ran.
That evidence comes from the scoped runtime runbooks and is summarized in
`docs/VERIFICATION.md`.

Standard library only, so this runs in the base CI job alongside the rest of the suite.
"""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW = REPO_ROOT / "docs" / "portfolio" / "platform-overview"
EVIDENCE_PATH = OVERVIEW / "evidence" / "runtime-evidence.json"
REPORT_PATH = OVERVIEW / "report.html"
SCREENSHOTS = (
    "01-platform-overview.png",
    "02-failure-recovery.png",
    "03-publish-retry-evidence.png",
)
ACCEPTED_SOURCE_COMMIT = "d8ec816"

ROOT_README = REPO_ROOT / "README.md"
WALKTHROUGHS = (OVERVIEW / "README.md", OVERVIEW / "README.ko.md")

# How far into a root README the release contract requires the key items to appear. The package
# allows a little slack for Mermaid syntax, so this is a ceiling, not an exact position.
FIRST_SCREEN_LIMIT = 75


def _load_builder():
    """Import the evidence builder from scripts/, which is not an importable package."""
    import importlib.util

    path = REPO_ROOT / "scripts" / "build_platform_portfolio_evidence.py"
    spec = importlib.util.spec_from_file_location("build_platform_portfolio_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def evidence() -> dict:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Runtime evidence document
# --------------------------------------------------------------------------- #
def test_evidence_json_parses_and_names_the_accepted_source_commit(evidence):
    assert evidence["source_commit"] == ACCEPTED_SOURCE_COMMIT
    assert evidence["evidence_version"] >= 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", evidence["verified_on"])
    assert evidence["scope"]


def test_representative_state_transition_is_blocked_then_complete_then_published_then_skipped(
    evidence,
):
    partial = evidence["partial_replay"]
    assert partial["recovery_complete"] is False
    assert partial["missing_sequences"], "a partial replay must be missing something"
    assert partial["publish_blocked"] is True
    # The refusal must have cost nothing downstream.
    assert partial["no_warehouse_created"] is True
    assert partial["no_adapter_created"] is True
    assert "RecoveryIncomplete" in partial["refusal_reason"]

    complete = evidence["complete_replay"]
    assert complete["recovery_complete"] is True
    assert complete["missing_sequences"] == []

    assert evidence["exact_session_input"]["sets_equal"] == "pass"
    assert evidence["quality"]["passed"] is True
    assert evidence["first_publish"]["status"] == "published"
    assert evidence["retry"]["status"] == "skipped"


def test_exact_set_claim_is_verified_against_the_committed_lists(evidence):
    """Do not take the runtime check string at face value; recompute from what is published.

    A false-positive upstream check must not be able to produce a public document whose own two
    lists disagree while this suite still passes.
    """
    exact = evidence["exact_session_input"]
    sealed = exact["sealed_event_ids"]
    selected = exact["selected_event_ids"]
    sealed_count = evidence["edge_session"]["sealed_event_count"]

    assert set(sealed) == set(selected), "the committed lists themselves must be equal as sets"
    assert len(sealed) == len(selected) == sealed_count
    # One unique event_id per sealed event: duplicates would make counts agree while coverage is short.
    assert len(set(sealed)) == len(sealed)
    assert len(set(selected)) == len(selected)
    assert exact["sets_equal"] == "pass"
    assert exact["sets_equal_rechecked_by_builder"] is True


def test_builder_rejects_mismatched_or_duplicated_event_id_lists():
    """The builder guard must fail loudly rather than publish a false exact-set claim."""
    builder = _load_builder()

    # Baseline: the contract-satisfying case does not raise.
    builder._assert_exact_session_input(["a", "b", "c"], ["c", "b", "a"], 3)

    with pytest.raises(builder.EvidenceBuildError, match="extra="):
        builder._assert_exact_session_input(["a", "b"], ["a", "b", "c"], 2)

    with pytest.raises(builder.EvidenceBuildError, match="missing="):
        builder._assert_exact_session_input(["a", "b", "c"], ["a", "b"], 3)

    with pytest.raises(builder.EvidenceBuildError, match="duplicates"):
        builder._assert_exact_session_input(["a", "a", "b"], ["a", "b"], 3)

    with pytest.raises(builder.EvidenceBuildError, match="counts disagree"):
        builder._assert_exact_session_input(["a", "b"], ["a", "b"], 3)


def test_snapshot_relations_and_same_snapshot_invariant_are_recorded(evidence):
    first, retry = evidence["first_publish"], evidence["retry"]

    assert first["snapshot_relation"] == "created_by_current_attempt"
    assert first["snapshot_created_by_current_attempt"] is True
    assert first["producer_attempt_run_id"] == first["spark_attempt_run_id"]

    assert retry["snapshot_relation"] == "reused_from_prior_attempt"
    assert retry["snapshot_created_by_current_attempt"] is False
    # The producing run is genuinely unknown on a skip; it must not be guessed.
    assert retry["producer_attempt_run_id"] is None
    assert retry["spark_attempt_run_id"] != first["spark_attempt_run_id"]

    assert retry["gold_snapshot_id"] == first["gold_snapshot_id"]
    assert retry["source_hash"] == first["source_hash"]
    assert retry["snapshot_count"] == first["snapshot_count"]
    for check in ("same_source_hash", "same_snapshot_id", "creates_no_new_snapshot"):
        assert retry[check] == "pass", check


def test_snapshot_ids_survive_json_parsing_without_rounding(evidence):
    """Iceberg snapshot ids exceed 2**53, so they must not be stored as JSON numbers.

    A browser parsing this document would silently round such a number, and the rendered report
    would then display an id that was never observed.
    """
    snapshot_id = evidence["first_publish"]["gold_snapshot_id"]
    assert isinstance(snapshot_id, str), "int64 ids must be exact decimal strings"
    assert snapshot_id.isdigit()
    if int(snapshot_id) > 2**53:
        assert int(float(snapshot_id)) != int(snapshot_id), (
            "this id would have been rounded as a JSON number, which is why it is a string"
        )
    assert evidence["identity_spaces"]["iceberg_snapshot_id"] == snapshot_id


def test_identity_spaces_are_recorded_separately(evidence):
    spaces = evidence["identity_spaces"]
    for key in (
        "edge_sequence",
        "event_id",
        "kafka_offsets",
        "adapter_source_hash",
        "spark_attempt_run_id",
        "iceberg_snapshot_id",
    ):
        assert spaces.get(key), key
    # The runtime counterexample the completeness contract rests on.
    assert spaces["edge_sequence"] != spaces["kafka_offsets"]


def test_verification_boundary_separates_ci_from_local_runtime(evidence):
    boundary = evidence["verification_boundary"]
    ci = boundary["automated_public_ci"]
    assert ci["workflow"] == ".github/workflows/ci.yml"
    assert (REPO_ROOT / ci["workflow"]).exists()
    assert "requirements.txt" in ci["installs"]
    uncovered = " ".join(ci["does_not_cover"]).lower()
    for runtime in ("kafka", "spark", "airflow"):
        assert runtime in uncovered, f"CI must state it does not cover {runtime}"
    # This is a HISTORICAL field: it records the workflow state when the evidence was captured,
    # not a live claim. The badge in the READMEs is the current signal, so a green run after push
    # does not turn this document into a contradiction.
    assert "github_actions_status" not in ci, (
        "a bare current-status field would go stale the moment the workflow first runs"
    )
    assert ci["github_actions_status_at_evidence_capture"] == "not_yet_run"
    assert boundary["documented_local_runtime"]["kafka_and_publish"].endswith(".sh")


def test_claim_boundary_lists_both_verified_and_not_verified(evidence):
    verified = evidence["claim_boundary"]["verified"]
    not_verified = " ".join(evidence["claim_boundary"]["not_verified"]).lower()
    assert len(verified) >= 3
    for forbidden in ("production", "streaming", "exactly-once", "cluster"):
        assert forbidden in not_verified, f"{forbidden} must be explicitly not claimed"


# --------------------------------------------------------------------------- #
# Rendered artifacts
# --------------------------------------------------------------------------- #
def test_report_renders_the_committed_evidence_document(evidence):
    html = REPORT_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="evidence" type="application/json">(.*?)</script>', html, re.DOTALL
    )
    assert match, "report must embed the evidence document it renders"
    embedded = json.loads(match.group(1).replace("<\\/", "</"))
    assert embedded == evidence, "report embeds a document that differs from the committed one"


def test_three_screenshots_exist_and_are_non_trivial_pngs():
    for name in SCREENSHOTS:
        path = OVERVIEW / "assets" / name
        assert path.exists(), name
        raw = path.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n", f"{name} is not a PNG"
        width, height = struct.unpack(">II", raw[16:24])
        assert width >= 600 and height >= 200, f"{name} is {width}x{height}"
        assert len(raw) > 10_000, f"{name} is only {len(raw)} bytes and is likely blank"


# --------------------------------------------------------------------------- #
# Reader-facing pages
# --------------------------------------------------------------------------- #
def test_root_readme_first_screen_carries_the_current_release_contract():
    lines = ROOT_README.read_text(encoding="utf-8").splitlines()
    first_screen = "\n".join(lines[:FIRST_SCREEN_LIMIT])

    required = {
        "CI badge": "actions/workflows/ci.yml/badge.svg",
        "architecture diagram": "```mermaid",
        "trust walkthrough": "docs/portfolio/industrial-telemetry-trust/README.md",
        "trust runtime evidence": (
            "industrial-telemetry-trust/evidence/runtime-evidence.json"
        ),
        "operator screenshot": "01-operator-decisions.png",
        "publish decision": "PUBLISH",
        "blocked decision": "BLOCKED",
        "reprocess decision": "REPROCESS REQUIRED",
    }
    missing = [name for name, needle in required.items() if needle not in first_screen]
    assert not missing, f"README.md first screen is missing: {missing}"


def test_root_readme_states_actual_record_replay_and_live_boundary():
    text = ROOT_README.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "actual record" in lowered
    assert "historical_record_replay" not in lowered  # reader-facing prose, not raw enum
    assert "local opc ua" in lowered
    assert "실제 공장" in text
    assert "synthetic" in lowered
    for absent_claim in ("physical plc", "production opc ua", "continuous kafka"):
        assert absent_claim in lowered


def test_root_readme_names_commands_evidence_and_claim_boundary():
    text = ROOT_README.read_text(encoding="utf-8")
    required = (
        "PYTHONPATH=src python -m pytest -q",
        "scripts/verify_industrial_source_contract.sh",
        "scripts/verify_event_time_trust.sh",
        "docs/ARCHITECTURE.md",
        "docs/VERIFICATION.md",
        "docs/HISTORICAL-EVIDENCE.md",
        "## 주장 경계",
        "badge는 이 base suite만 증명",
    )
    for value in required:
        assert value in text


def test_root_readme_is_korean_first():
    first_screen = "\n".join(
        ROOT_README.read_text(encoding="utf-8").splitlines()[:FIRST_SCREEN_LIMIT]
    )
    assert "제조 설비 데이터는 언제 믿을 수 있는가" in first_screen
    assert sum("가" <= char <= "힣" for char in first_screen) > 100


def test_walkthroughs_expose_the_same_required_sections():
    required = (
        ("problem", "문제"),
        ("failure scenario", "실패 시나리오"),
        ("contracts", "계약"),
        ("implementation path", "구현 경로"),
        ("counterexamples", "반례"),
        ("runtime evidence", "runtime evidence"),
        ("limitations", "한계"),
        ("interview", "면접"),
    )
    english = WALKTHROUGHS[0].read_text(encoding="utf-8").lower()
    korean = WALKTHROUGHS[1].read_text(encoding="utf-8").lower()
    for en_term, ko_term in required:
        assert en_term in english, f"EN walkthrough missing section about {en_term!r}"
        assert ko_term.lower() in korean, f"KO walkthrough missing section about {ko_term!r}"


def test_walkthroughs_share_the_observed_values_with_the_evidence(evidence):
    """Reader-facing numbers must be the ones in the committed evidence, not restated guesses."""
    snapshot_id = evidence["first_publish"]["gold_snapshot_id"]
    for page in WALKTHROUGHS:
        text = page.read_text(encoding="utf-8")
        assert snapshot_id in text, f"{page.name} does not show the observed snapshot id"
        assert evidence["source_commit"] in text, f"{page.name} does not name the source commit"


# --------------------------------------------------------------------------- #
# Publication safety
# --------------------------------------------------------------------------- #
RELEASE_FILES = (ROOT_README,) + WALKTHROUGHS + (
    REPORT_PATH,
    EVIDENCE_PATH,
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
)


@pytest.mark.parametrize("path", RELEASE_FILES, ids=lambda p: p.name)
def test_reader_facing_files_contain_no_private_absolute_path(path: Path):
    """Generic /tmp reproduction paths are fine; user-specific home paths are not."""
    text = path.read_text(encoding="utf-8")
    leaks = re.findall(r"/home/[A-Za-z0-9._-]+", text)
    assert not leaks, f"{path.name} leaks a private path: {sorted(set(leaks))}"


@pytest.mark.parametrize("path", RELEASE_FILES, ids=lambda p: p.name)
def test_reader_facing_files_contain_no_obvious_secret(path: Path):
    text = path.read_text(encoding="utf-8")
    patterns = (
        r"api[_-]?key\s*[:=]",
        r"access[_-]?key\s*[:=]",
        r"client_secret",
        r"refresh_token",
        r"BEGIN (?:RSA|OPENSSH) PRIVATE KEY",
        r"mongodb\+srv://",
        r"AKIA[0-9A-Z]{16}",
    )
    for pattern in patterns:
        assert not re.search(pattern, text, re.IGNORECASE), f"{path.name} matches {pattern}"


@pytest.mark.parametrize("path", (ROOT_README,) + WALKTHROUGHS, ids=lambda p: p.name)
def test_relative_links_in_release_pages_resolve(path: Path):
    text = path.read_text(encoding="utf-8")
    broken = []
    for target in re.findall(r"\]\((?!https?://|#)([^)\s]+)\)", text):
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        if not resolved.exists():
            broken.append(target)
    assert not broken, f"{path.name} has broken relative links: {broken}"
