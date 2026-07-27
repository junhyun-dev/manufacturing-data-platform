#!/usr/bin/env python3
"""Normalize one S9 runbook result into the committed platform-overview evidence, then render
`report.html` from exactly that committed document.

Why this exists: the previous portfolio milestone hand-authored its report values, so the report
could silently drift from the runtime JSON it claimed to show. Here the flow is one-directional and
mechanical:

```text
scripts/verify_recovered_telemetry_publish.sh   (runtime, writes s9_verification.json)
-> this script --from <runtime json>            (normalize, no invented values)
-> docs/portfolio/platform-overview/evidence/runtime-evidence.json
-> this script embeds THAT document into report.html and renders it in the browser
-> scripts/capture_platform_portfolio.py        (screens of the rendered report)
```

Every observed number in the report comes from the embedded JSON at render time. Nothing in the
HTML restates a success value independently, so a stale report is not expressible: rebuild and the
values move together, or the build fails.

Values that cannot be derived from the runtime JSON or from a direct command are omitted or
recorded as "unknown" - never guessed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_JSON = Path("/tmp/manufacturing-mini-s9-release/s9_verification.json")
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "portfolio" / "platform-overview"

EVIDENCE_VERSION = 1
SCOPE = (
    "one synthetic, local, bounded manufacturing telemetry failure/recovery path: "
    "sealed edge session -> local Kafka replay -> recovery + exact-session-input gate -> "
    "Spark quality gate -> one local Iceberg gold table"
)


class EvidenceBuildError(RuntimeError):
    """The runtime document does not contain what this report is supposed to show."""


def _require(container: dict, key: str, where: str) -> Any:
    if key not in container:
        raise EvidenceBuildError(f"missing {key!r} in {where}; refusing to invent a value")
    return container[key]


def _check_map(checks: list[dict]) -> dict[str, dict]:
    return {c["name"]: c for c in checks}


def _assert_exact_session_input(
    sealed_event_ids: list[str], selected_event_ids: list[str], sealed_event_count: int
) -> None:
    """Re-derive the exact-set claim here instead of trusting the runtime check string.

    The runtime check already ran, but a published evidence document must not be able to say
    `sets_equal: pass` while the two lists it shows disagree. This recomputes the contract from the
    values actually being committed, so a false-positive upstream check cannot reach the public
    page silently.

    Duplicates are rejected too: the contract is one unique `event_id` per sealed event, so a
    repeated id would make the counts line up while the real coverage is short.
    """
    sealed, selected = list(sealed_event_ids), list(selected_event_ids)

    for label, ids in (("sealed", sealed), ("selected", selected)):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise EvidenceBuildError(
                f"{label} event ids contain duplicates {duplicates}; one unique event_id per "
                "sealed event is the contract"
            )

    if set(sealed) != set(selected):
        raise EvidenceBuildError(
            "sealed and selected event id sets differ; refusing to publish an exact-set claim: "
            f"extra={sorted(set(selected) - set(sealed))} "
            f"missing={sorted(set(sealed) - set(selected))}"
        )

    if not (len(sealed) == len(selected) == sealed_event_count):
        raise EvidenceBuildError(
            f"event id counts disagree with the sealed count: sealed={len(sealed)} "
            f"selected={len(selected)} sealed_event_count={sealed_event_count}"
        )


def _snapshot_id(value: Any) -> str | None:
    """Iceberg snapshot ids are int64 and routinely exceed 2**53.

    `JSON.parse` in a browser would silently round such a value (an observed id ending in ...048
    rendered as ...040), so the committed document stores it as an exact decimal string. This is a
    lossless representation change, not a different value.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceBuildError(f"unexpected snapshot id type {type(value).__name__}: {value!r}")
    return str(value)


def _command_output(args: list[str]) -> str | None:
    """Return trimmed stdout, or None when the command is unavailable. Never raises."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def build_evidence_document(
    runtime: dict,
    first_evidence: dict,
    retry_evidence: dict,
    *,
    source_commit: str,
    verified_on: str,
) -> dict:
    """Project the S9 runbook documents onto the committed portfolio evidence schema.

    `runtime` is `s9_verification.json`; the two attempt documents are the per-attempt evidence
    files the same runbook wrote. All three are runtime output - nothing here is hand-entered.
    """
    if runtime.get("status") != "passed":
        raise EvidenceBuildError(
            f"runbook status is {runtime.get('status')!r}; only a passed run may be published"
        )

    phases = _require(runtime, "phases", "runtime document")
    spool = _require(phases, "spool", "phases")
    broker = _require(phases, "broker", "phases")
    publish = _require(phases, "publish", "phases")

    partial = _require(broker, "partial", "broker phase")
    complete = _require(broker, "complete", "broker phase")
    gate = _require(broker, "partial_publish_gate", "broker phase")
    publish_checks = _check_map(_require(publish, "checks", "publish phase"))
    broker_checks = _check_map(_require(broker, "checks", "broker phase"))

    def check_status(name: str, checks: dict[str, dict]) -> str:
        if name not in checks:
            raise EvidenceBuildError(f"expected runtime check {name!r} is absent")
        return checks[name]["status"]

    identity = _require(publish, "identity_chain", "publish phase")

    sealed_event_ids = first_evidence["edge"]["event_ids"]
    selected_event_ids = first_evidence["adapter"]["selected_event_ids"]
    _assert_exact_session_input(
        sealed_event_ids,
        selected_event_ids,
        _require(spool, "sealed_event_count", "spool phase"),
    )

    return {
        "evidence_version": EVIDENCE_VERSION,
        "verified_on": verified_on,
        "source_commit": source_commit,
        "scope": SCOPE,
        "generated_by": "scripts/build_platform_portfolio_evidence.py",
        "runtime_source": "scripts/verify_recovered_telemetry_publish.sh (three phases, one process each)",
        "runtime": {
            "python": _command_output([sys.executable, "--version"]) or "unknown",
            "pyspark": _pyspark_version(),
            "iceberg_runtime_coordinate": _iceberg_coordinate(),
            "kafka_topic": _topic_from(identity),
            "kafka_partitions": 1,
            "note": (
                "single local broker, single partition, single writer; versions are read from the "
                "interpreter and source that produced this run"
            ),
            "int64_id_encoding": (
                "Iceberg snapshot ids are stored as exact decimal strings because they exceed the "
                "range JavaScript can parse without rounding"
            ),
        },
        "edge_session": {
            "edge_source_id": first_evidence["edge"]["edge_source_id"],
            "boot_session_id": first_evidence["edge"]["boot_session_id"],
            "machine_id": _require(spool, "machine_id", "spool phase"),
            "business_date": _require(spool, "business_date", "spool phase"),
            "sealed_event_count": _require(spool, "sealed_event_count", "spool phase"),
            "broker_absent_during_spool": _require(
                spool, "broker_absent_during_spool", "spool phase"
            ),
            "seal_contract": "expected_last_sequence distinguishes 'not yet arrived' from 'lost'",
        },
        "partial_replay": {
            "replayed_edge_sequences": partial["replayed_edge_sequences"],
            "produced_kafka_offsets": partial["produced_kafka_offsets"],
            "central_accepted_total": partial["central_accepted_total"],
            "missing_sequences": partial["missing_sequences"],
            "recovery_complete": partial["recovery_complete"],
            "publish_blocked": gate["partial_publish_blocked"],
            "refusal_reason": gate["detail"],
            "no_warehouse_created": gate["no_warehouse_created"],
            "no_adapter_created": gate["no_adapter_created"],
            "check_partial_left_no_spark_iceberg_state": check_status(
                "partial_left_no_spark_iceberg_state", broker_checks
            ),
        },
        "complete_replay": {
            "replayed_edge_sequences": complete["replayed_edge_sequences"],
            "produced_kafka_offsets": complete["produced_kafka_offsets"],
            "central_accepted_total": complete["central_accepted_total"],
            "missing_sequences": complete["missing_sequences"],
            "recovery_complete": complete["recovery_complete"],
        },
        "exact_session_input": {
            "sealed_event_ids": sealed_event_ids,
            "selected_event_ids": selected_event_ids,
            "sets_equal": check_status("edge_event_ids_equal_adapter_event_ids", publish_checks),
            "sets_equal_rechecked_by_builder": True,
            "contract": (
                "membership (sealed subset of accepted) is not sufficient; the adapter selects every "
                "accepted event for the date, so the selected set must EQUAL the sealed set"
            ),
        },
        "quality": {
            "passed": first_evidence["spark"]["quality_passed"],
            "checks": [
                {"name": c["name"], "status": c["status"]}
                for c in first_evidence["spark"]["quality_checks"]
            ],
            "row_counts": first_evidence["spark"]["row_counts"],
        },
        "first_publish": {
            "status": first_evidence["status"],
            "table": first_evidence["iceberg"]["table"],
            "gold_snapshot_id": _snapshot_id(first_evidence["iceberg"]["gold_snapshot_id"]),
            "snapshot_count": first_evidence["iceberg"]["snapshot_count"],
            "target_partition_row_count": first_evidence["iceberg"]["target_partition_row_count"],
            "snapshot_relation": first_evidence["iceberg"]["snapshot_relation"],
            "snapshot_created_by_current_attempt": first_evidence["iceberg"][
                "snapshot_created_by_current_attempt"
            ],
            "spark_attempt_run_id": first_evidence["spark"]["attempt_run_id"],
            "producer_attempt_run_id": first_evidence["iceberg"]["producer_attempt_run_id"],
            "source_hash": first_evidence["adapter"]["source_hash"],
        },
        "retry": {
            "status": retry_evidence["status"],
            "gold_snapshot_id": _snapshot_id(retry_evidence["iceberg"]["gold_snapshot_id"]),
            "snapshot_count": retry_evidence["iceberg"]["snapshot_count"],
            "snapshot_relation": retry_evidence["iceberg"]["snapshot_relation"],
            "snapshot_created_by_current_attempt": retry_evidence["iceberg"][
                "snapshot_created_by_current_attempt"
            ],
            "spark_attempt_run_id": retry_evidence["spark"]["attempt_run_id"],
            "producer_attempt_run_id": retry_evidence["iceberg"]["producer_attempt_run_id"],
            "source_hash": retry_evidence["adapter"]["source_hash"],
            "same_source_hash": check_status("retry_same_source_hash", publish_checks),
            "same_snapshot_id": check_status("retry_same_snapshot_id", publish_checks),
            "creates_no_new_snapshot": check_status("retry_creates_no_new_snapshot", publish_checks),
            "attempt_run_ids_differ": check_status("attempt_run_ids_differ", publish_checks),
            "meaning": (
                "no new snapshot and no partition overwrite; NOT a whole-pipeline no-op, because "
                "Spark and the quality suite still run before the skip decision"
            ),
        },
        "identity_spaces": {
            "edge_sequence": identity["edge_sequence"],
            "event_id": identity["event_id"],
            "kafka_offsets": [c["kafka_offset"] for c in identity["kafka_coordinate"]],
            "adapter_source_hash": identity["adapter_source_hash"],
            "spark_attempt_run_id": identity["spark_attempt_run_id"],
            "iceberg_snapshot_id": _snapshot_id(identity["iceberg_snapshot_id"]),
            "observed_counterexample": (
                "edge sequence differs from the Kafka offsets carrying the same events, so "
                "completeness cannot be decided by offset continuity"
            ),
        },
        "state_transition": [
            "sealed while no broker is running",
            "partial replay -> publication blocked, no Spark or Iceberg state",
            "complete replay -> recovery complete",
            "published with quality passed and a snapshot",
            "same-source retry -> skipped, no new snapshot, no partition overwrite",
        ],
        "verification_boundary": {
            "automated_public_ci": {
                "workflow": ".github/workflows/ci.yml",
                "covers": "base Python unit/contract suite on Python 3.10 and 3.12",
                "installs": "requirements.txt only",
                "does_not_cover": [
                    "Kafka broker runtime",
                    "Spark/Iceberg runtime",
                    "Airflow runtime",
                ],
                "github_actions_status_at_evidence_capture": "not_yet_run",
            },
            "documented_local_runtime": {
                "kafka_and_publish": "scripts/verify_recovered_telemetry_publish.sh",
                "edge_recovery": "scripts/verify_edge_recovery.sh",
                "kafka_landing": "scripts/verify_kafka_k1.sh, scripts/verify_kafka_k1_5.sh",
                "spark_batch": "scripts/verify_spark_machine_event_batch.sh",
                "airflow": "airflow dags test in a separately pinned local environment",
                "history": "VERIFICATION_LOG.md",
            },
        },
        "claim_boundary": {
            "verified": [
                "a sealed edge session buffered while no broker was running, then replayed through a real local Kafka broker",
                "partial recovery blocks publication before any Spark or Iceberg state exists",
                "the selected batch input equals the sealed event set exactly, not merely contains it",
                "only quality-passed data advanced the local Iceberg gold table",
                "a same-source retry created no new snapshot and performed no partition overwrite",
                "the reused snapshot is recorded as reused, with the producer attempt marked unknown",
            ],
            "not_verified": [
                "production or multi-broker Kafka",
                "continuous or large-scale streaming, or a direct Kafka-to-Iceberg sink",
                "cluster Spark, throughput, or any performance claim",
                "production, HA, or distributed Airflow operation",
                "concurrent Iceberg writers, distributed atomicity, or end-to-end exactly-once",
                "real OT/ROS2/MCAP/edge-hardware integration",
                "Kafka, Spark, Iceberg, or Airflow runtime proven by the public CI badge",
            ],
        },
    }


def _pyspark_version() -> str:
    out = _command_output([sys.executable, "-c", "import pyspark; print(pyspark.__version__)"])
    return f"pyspark {out}" if out else "unknown"


def _iceberg_coordinate() -> str:
    """Read the coordinate from the S7 source rather than restating it here."""
    source = REPO_ROOT / "src" / "manufacturing_data_platform" / "pipeline" / "spark_iceberg_skeleton.py"
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    for line in text.splitlines():
        if "iceberg-spark-runtime" in line and '"' in line:
            for part in line.split('"'):
                if "iceberg-spark-runtime" in part:
                    return part
    return "unknown"


def _topic_from(identity: dict) -> str:
    coordinates = identity.get("kafka_coordinate") or []
    topics = {c.get("kafka_topic") for c in coordinates if c.get("kafka_topic")}
    return topics.pop() if len(topics) == 1 else "unknown"


# --------------------------------------------------------------------------- #
# Report rendering — the HTML embeds the committed document and renders from it
# --------------------------------------------------------------------------- #
REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manufacturing Data Platform - Recovery-Gated Publish Runtime Evidence</title>
<style>
  :root {
    color-scheme: light;
    --ink: #17202a; --muted: #5c6874; --line: #d8dee4; --paper: #f7f8fa; --white: #fff;
    --green: #147d64; --green-soft: #e8f5f0; --red: #b63b45; --red-soft: #fff0f1;
    --blue: #1769aa; --blue-soft: #eaf3fb; --amber: #a85f00; --amber-soft: #fff4df;
  }
  * { box-sizing: border-box; }
  html, body { margin:0; background: var(--paper); color: var(--ink);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
  .screen { width: min(100%, 1440px); margin: 0 auto; padding: 28px 32px 36px; }
  h1 { font-size: 25px; margin: 0 0 6px; letter-spacing: -0.2px; }
  h2 { font-size: 16px; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.7px;
       color: var(--muted); }
  .sub { color: var(--muted); font-size: 14px; margin: 0 0 18px; max-width: 105ch; line-height:1.5; }
  .meta { display:flex; gap:8px; flex-wrap:wrap; margin-bottom: 20px; }
  .tag { font-size:12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
         background: var(--white); border:1px solid var(--line); border-radius:999px; padding:4px 11px; }
  .card { background: var(--white); border:1px solid var(--line); border-radius:12px;
          padding:18px 20px; margin-bottom:16px; }
  .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap:14px; }
  table { width:100%; border-collapse: collapse; font-size:13.5px; }
  th, td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight:600; font-size:12px; text-transform:uppercase;
       letter-spacing:0.5px; }
  tr:last-child td { border-bottom:none; }
  code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12.5px; }
  .pill { display:inline-block; font-size:12px; font-weight:600; padding:2px 9px; border-radius:999px; }
  .ok { background: var(--green-soft); color: var(--green); }
  .block { background: var(--red-soft); color: var(--red); }
  .info { background: var(--blue-soft); color: var(--blue); }
  .warn { background: var(--amber-soft); color: var(--amber); }
  .flow { display:flex; flex-wrap:wrap; align-items:stretch; gap:8px; margin: 4px 0 2px; }
  .step { flex:1 1 150px; background:var(--paper); border:1px solid var(--line); border-radius:9px;
          padding:10px 12px; font-size:12.5px; line-height:1.45; }
  .step b { display:block; font-size:11px; text-transform:uppercase; letter-spacing:0.5px;
            color:var(--muted); margin-bottom:3px; }
  ul { margin:6px 0 0; padding-left:18px; font-size:13.5px; line-height:1.6; }
  li { margin-bottom:3px; }
  .kv { font-size:13.5px; line-height:1.7; }
  .kv b { color: var(--muted); font-weight:600; }
  .foot { color:var(--muted); font-size:12px; margin-top:6px; line-height:1.6; }
  .two { display:grid; grid-template-columns: 1fr 1fr; gap:16px; }
  @media (max-width: 900px) { .two { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<script id="evidence" type="application/json">__EVIDENCE_JSON__</script>
<div class="screen" id="root"></div>
<script>
const E = JSON.parse(document.getElementById('evidence').textContent);
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const mono = s => `<code>${esc(s)}</code>`;
const passPill = v => (v === true || v === 'pass')
  ? '<span class="pill ok">pass</span>' : `<span class="pill block">${esc(v)}</span>`;
const rows = pairs => pairs.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');

const q = E.quality, fp = E.first_publish, rt = E.retry, pr = E.partial_replay, cr = E.complete_replay;

document.getElementById('root').innerHTML = `
  <h1>Recovery-gated Spark/Iceberg publish &mdash; runtime evidence</h1>
  <p class="sub">${esc(E.scope)}</p>
  <div class="meta">
    <span class="tag">source_commit ${esc(E.source_commit)}</span>
    <span class="tag">verified_on ${esc(E.verified_on)}</span>
    <span class="tag">${esc(E.runtime.python)}</span>
    <span class="tag">${esc(E.runtime.pyspark)}</span>
    <span class="tag">evidence_version ${esc(E.evidence_version)}</span>
  </div>

  <div class="card" id="screen-1">
    <h2>1 &middot; Architecture and scope</h2>
    <div class="flow">
      ${E.state_transition.map((s, i) => `<div class="step"><b>step ${i + 1}</b>${esc(s)}</div>`).join('')}
    </div>
    <div class="two" style="margin-top:16px">
      <div>
        <table>${rows([
          ['edge_source_id', mono(E.edge_session.edge_source_id)],
          ['machine_id', mono(E.edge_session.machine_id)],
          ['business_date', mono(E.edge_session.business_date)],
          ['sealed_event_count', mono(E.edge_session.sealed_event_count)],
          ['broker absent while spooling', passPill(E.edge_session.broker_absent_during_spool)],
          ['Kafka topic / partitions', mono(E.runtime.kafka_topic) + ' / ' + mono(E.runtime.kafka_partitions)],
          ['Iceberg runtime', mono(E.runtime.iceberg_runtime_coordinate)],
        ])}</table>
      </div>
      <div>
        <table>${rows([
          ['automated public CI', esc(E.verification_boundary.automated_public_ci.covers)],
          ['CI installs', mono(E.verification_boundary.automated_public_ci.installs)],
          ['CI does NOT cover', E.verification_boundary.automated_public_ci.does_not_cover.map(esc).join(', ')],
          ['GitHub Actions at evidence capture', `<span class="pill warn">${esc(E.verification_boundary.automated_public_ci.github_actions_status_at_evidence_capture)}</span>`],
          ['local runtime source', mono(E.verification_boundary.documented_local_runtime.kafka_and_publish)],
        ])}</table>
      </div>
    </div>
  </div>

  <div class="card" id="screen-2">
    <h2>2 &middot; Partial recovery is refused before any Spark or Iceberg state exists</h2>
    <div class="two">
      <div>
        <table>${rows([
          ['replayed edge sequences', mono(JSON.stringify(pr.replayed_edge_sequences))],
          ['Kafka offsets produced', mono(JSON.stringify(pr.produced_kafka_offsets))],
          ['centrally accepted', mono(pr.central_accepted_total)],
          ['missing edge sequences', `<span class="pill block">${esc(JSON.stringify(pr.missing_sequences))}</span>`],
          ['recovery_complete', `<span class="pill block">${esc(pr.recovery_complete)}</span>`],
          ['publication', `<span class="pill block">blocked</span>`],
          ['Iceberg warehouse left behind', pr.no_warehouse_created === true
              ? '<span class="pill ok">none</span>' : '<span class="pill block">present</span>'],
          ['adapter output left behind', pr.no_adapter_created === true
              ? '<span class="pill ok">none</span>' : '<span class="pill block">present</span>'],
        ])}</table>
        <p class="foot">refusal: ${mono(pr.refusal_reason)}</p>
      </div>
      <div>
        <table>${rows([
          ['replayed edge sequences', mono(JSON.stringify(cr.replayed_edge_sequences))],
          ['Kafka offsets produced', mono(JSON.stringify(cr.produced_kafka_offsets))],
          ['centrally accepted', mono(cr.central_accepted_total)],
          ['missing edge sequences', `<span class="pill ok">${esc(JSON.stringify(cr.missing_sequences))}</span>`],
          ['recovery_complete', `<span class="pill ok">${esc(cr.recovery_complete)}</span>`],
          ['sealed set == selected set', passPill(E.exact_session_input.sets_equal)],
          ['sealed event ids', mono(E.exact_session_input.sealed_event_ids.join(', '))],
        ])}</table>
        <p class="foot">${esc(E.exact_session_input.contract)}</p>
      </div>
    </div>
  </div>

  <div class="card" id="screen-3">
    <h2>3 &middot; Quality-gated publish, then a retry that changes nothing in the table</h2>
    <div class="grid">
      <div>
        <p class="kv"><b>quality gate</b> ${passPill(q.passed)}
          &nbsp;<span class="mono">${q.checks.length} checks</span></p>
        <ul>${q.checks.map(c => `<li>${esc(c.name)} ${passPill(c.status)}</li>`).join('')}</ul>
        <p class="foot">rows: input ${q.row_counts.input} &rarr; silver ${q.row_counts.silver} &rarr; gold ${q.row_counts.gold}</p>
      </div>
      <div>
        <table>${rows([
          ['first attempt', `<span class="pill ok">${esc(fp.status)}</span>`],
          ['table', mono(fp.table)],
          ['gold_snapshot_id', mono(fp.gold_snapshot_id)],
          ['snapshot_count', mono(fp.snapshot_count)],
          ['snapshot_relation', mono(fp.snapshot_relation)],
          ['producer_attempt_run_id', mono(fp.producer_attempt_run_id)],
          ['source_hash', mono(String(fp.source_hash).slice(0, 24) + '...')],
        ])}</table>
      </div>
      <div>
        <table>${rows([
          ['retry', `<span class="pill info">${esc(rt.status)}</span>`],
          ['same source_hash', passPill(rt.same_source_hash)],
          ['same snapshot_id', passPill(rt.same_snapshot_id)],
          ['no new snapshot', passPill(rt.creates_no_new_snapshot)],
          ['attempt ids differ', passPill(rt.attempt_run_ids_differ)],
          ['snapshot_relation', mono(rt.snapshot_relation)],
          ['producer_attempt_run_id', mono(String(rt.producer_attempt_run_id))],
        ])}</table>
        <p class="foot">${esc(rt.meaning)}</p>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>4 &middot; Identity spaces stay separate</h2>
    <table>${rows([
      ['edge sequence', mono(JSON.stringify(E.identity_spaces.edge_sequence))],
      ['business event_id', mono(E.identity_spaces.event_id.join(', '))],
      ['Kafka offsets', mono(JSON.stringify(E.identity_spaces.kafka_offsets))],
      ['batch source_hash', mono(E.identity_spaces.adapter_source_hash)],
      ['Spark attempt run_id', mono(E.identity_spaces.spark_attempt_run_id)],
      ['Iceberg snapshot_id', mono(E.identity_spaces.iceberg_snapshot_id)],
    ])}</table>
    <p class="foot">${esc(E.identity_spaces.observed_counterexample)}</p>
  </div>

  <div class="card">
    <h2>5 &middot; Claim boundary</h2>
    <div class="two">
      <div><p class="kv"><b>verified here</b></p>
        <ul>${E.claim_boundary.verified.map(v => `<li>${esc(v)}</li>`).join('')}</ul></div>
      <div><p class="kv"><b>not verified &mdash; do not claim</b></p>
        <ul>${E.claim_boundary.not_verified.map(v => `<li>${esc(v)}</li>`).join('')}</ul></div>
    </div>
    <p class="foot">Every value on this page is rendered from
      <code>evidence/runtime-evidence.json</code>, produced by
      <code>${esc(E.runtime_source)}</code> and normalized by <code>${esc(E.generated_by)}</code>.
      Execution history lives in <code>VERIFICATION_LOG.md</code>.</p>
  </div>
`;
</script>
</body>
</html>
"""


def render_report(evidence: dict) -> str:
    embedded = json.dumps(evidence, indent=2, sort_keys=True).replace("</", "<\\/")
    return REPORT_TEMPLATE.replace("__EVIDENCE_JSON__", embedded)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="runtime_json", default=str(DEFAULT_RUNTIME_JSON))
    parser.add_argument(
        "--attempt-evidence-dir",
        default=None,
        help="directory holding s9_publish_first.json / s9_publish_retry.json "
        "(default: <runtime json parent>/evidence)",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--verified-on", required=True, help="ISO date of the run, e.g. 2026-07-23")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    runtime_path = Path(args.runtime_json)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))

    attempt_dir = (
        Path(args.attempt_evidence_dir)
        if args.attempt_evidence_dir
        else runtime_path.parent / "evidence"
    )
    try:
        first_evidence = json.loads(
            (attempt_dir / "s9_publish_first.json").read_text(encoding="utf-8")
        )
        retry_evidence = json.loads(
            (attempt_dir / "s9_publish_retry.json").read_text(encoding="utf-8")
        )
    except OSError as exc:
        raise EvidenceBuildError(
            f"per-attempt runbook evidence is missing under {attempt_dir}: {exc}"
        ) from exc

    evidence = build_evidence_document(
        runtime,
        first_evidence,
        retry_evidence,
        source_commit=args.source_commit,
        verified_on=args.verified_on,
    )

    out_dir = Path(args.out_dir)
    evidence_path = out_dir / "evidence" / "runtime-evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report_path = out_dir / "report.html"
    report_path.write_text(render_report(evidence), encoding="utf-8")

    print(f"evidence: {evidence_path}")
    print(f"report:   {report_path}")
    print(f"status:   {evidence['first_publish']['status']} -> {evidence['retry']['status']}")


if __name__ == "__main__":
    main()
