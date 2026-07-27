# Platform Overview — a recovered edge session reaches the gold table only when it is provably complete

> 한국어판: [`README.ko.md`](README.ko.md)
> Runtime evidence: [`evidence/runtime-evidence.json`](evidence/runtime-evidence.json) · rendered as [`report.html`](report.html)
> Source commit for this evidence: `d8ec816`

This is the representative walkthrough for the whole platform. The Kafka ingestion milestone in
[`../kafka-k1-k1-5/README.md`](../kafka-k1-k1-5/README.md) remains a supporting deep dive on the
input path; this page is the end-to-end path a reviewer should read first.

## 1. Problem

A plant link drops. Collection cannot stop, so events pile up at the edge. When the link comes
back, everything replays — and the tempting move is to run the daily batch as soon as data starts
arriving again.

That is exactly the move that produces a number nobody can defend:

```text
the gold table advances while part of the disconnected window is still missing,
and afterwards nobody can say whether it was missing or simply never existed.
```

So the real question is not "how do we buffer and replay". It is:

```text
what has to be TRUE before a recovered window is allowed to change a trusted table?
```

## 2. Failure scenario

```text
edge sequences 1,2,3 are spooled while no broker is running, then sealed
-> link returns; only 1,2 replay through Kafka        (offsets [0,1])
-> publication is refused: sequence 3 is missing
-> 3 replays                                          (offsets [2,3,4])
-> recovery is complete
-> Spark quality suite passes
-> one Iceberg business_date partition is published
-> the same source runs again: no new snapshot, no partition overwrite
```

## 3. State and identity contracts

Three contracts carry the whole design.

**Durability before progress.** A Kafka offset is committed only after the record is durably
landed. A crash between the two costs a redelivery, never a record.

**Recovery before publication.** Two separate conditions must hold before Spark starts:

```text
completeness   every sealed event_id is present in the centrally accepted set
exact input    the selected batch event set EQUALS the sealed set, not merely contains it
```

The second is the subtle one. The adapter selects *every* accepted event for that
`business_date`, so one extra same-date event from another path would produce a batch that is
"complete" and yet is no longer the recovered session. Membership alone cannot see that.

**Quality and current-state safety.** Only quality-passed data advances the Iceberg table, and a
same-source retry creates no new snapshot and performs no partition overwrite.

Five identity spaces stay separate, each in its own field:

| Space | Example from this run | What it answers |
|---|---|---|
| edge sequence | `[1, 2, 3]` | what order did the edge record things in |
| business `event_id` | `evt-20260629-000001…3` | is this the same business event |
| Kafka coordinate | offsets `[0, 1, 4]` | where did transport put it this time |
| batch `source_hash` | `ec99bd1d1a16c684818d…` | is this the same batch input |
| attempt `run_id` / `snapshot_id` | `…T100617Z-f62e2729` / `472417168912431048` | which execution, which table commit |

Note the edge sequence `[1, 2, 3]` against Kafka offsets `[0, 1, 4]` for the same three events.
That is the direct runtime reason completeness is decided by `event_id` membership and **never** by
offset continuity.

## 4. Implementation path

```text
edge spool  fsync + atomic rename; the immutable file set IS the progress record
seal        expected_last_sequence separates "not yet arrived" from "lost"
landing     durable JSONL landing, then offset commit
gate        one shared readiness function, called by both the promotion and publish paths
adapter     existing deterministic canonical CSV + SHA-256 source_hash (unchanged)
equality    sealed event-id set == selected event-id set, checked before Spark starts
publish     existing Spark silver/gold + quality suite + Iceberg partition overwrite (unchanged)
evidence    one document binding all five identity spaces and the snapshot relation
```

The publish slice adds no transform, quality, adapter, Kafka, or Iceberg logic of its own. It
composes two already-verified contracts and refuses to let the second begin until the first holds.

## 5. Counterexamples caught

Each of these was written as a failing case first, and each is a scenario a reviewer can ask about:

```text
partial recovery                    refused; no warehouse and no adapter output left behind
extra same-date event from elsewhere refused with extra_event_ids, even though recovery is complete
sealed event missing from selection  refused with missing_event_ids
requested date != sealed session date refused before any output exists
quality failure                     no snapshot, no success-state advance
repeated replay                     transport evidence grows; accepted set and source_hash do not
skipped retry                       recorded as reusing a snapshot it did not create
```

Two of these were found by review rather than by the first implementation, and both were about the
*record* rather than the behaviour: a skipped retry once paired its freshly minted attempt id with
the reused snapshot (reads as "this run created it"), and a quality failure was once labelled as
reusing a snapshot that did not exist. Both are now explicit:
`snapshot_relation ∈ {created_by_current_attempt, reused_from_prior_attempt, no_snapshot}`, with
`producer_attempt_run_id` left `null` when the producing run is genuinely unknown.

## 6. Runtime evidence

Reproduce the whole path:

```bash
PYTHON_BIN=python ./scripts/verify_recovered_telemetry_publish.sh
```

Observed on `d8ec816` (full values in
[`evidence/runtime-evidence.json`](evidence/runtime-evidence.json)):

| Stage | Observed |
|---|---|
| spool | 3 events sealed, `broker_absent_during_spool = true` |
| partial replay | accepted 2, missing `[3]`, publication blocked, no warehouse, no adapter |
| complete replay | accepted 3, missing `[]`, `recovery_complete = true` |
| exact input | 3 sealed event ids == 3 selected event ids |
| quality | 7/7 checks pass, rows 3 → 3 → 1 |
| first publish | `published`, snapshot `472417168912431048`, `created_by_current_attempt` |
| retry | `skipped`, same `source_hash`, same snapshot, `snapshot_count` unchanged |

![Architecture and scope](assets/01-platform-overview.png)

![Partial failure, blocked publication, complete recovery](assets/02-failure-recovery.png)

![Quality-gated publish and a retry that changes nothing](assets/03-publish-retry-evidence.png)

The screens are browser captures of [`report.html`](report.html), which renders the committed
JSON — they are not hand-authored numbers. Execution history for every runbook lives in
[`../../../VERIFICATION_LOG.md`](../../../VERIFICATION_LOG.md).

### What is automated versus documented

| | Covers | Does not cover |
|---|---|---|
| Public CI ([`ci.yml`](../../../.github/workflows/ci.yml)) | base Python unit/contract suite, Python 3.10 and 3.12, `requirements.txt` only | Kafka, Spark/Iceberg, Airflow runtime |
| Local runbooks under [`scripts/`](../../../scripts/) | real local broker, Spark/Iceberg, Airflow `dags test` | anything distributed or production |

The CI badge proves the base suite. It does not prove any of the heavy runtimes, and this page does
not use it to.

## 7. Limitations

```text
synthetic data; one session, one machine, one business_date, one topic partition, one gold table
single writer; concurrent Iceberg writers are not addressed
a local filesystem durability boundary — no power-loss, NFS, or object-store guarantee
no distributed atomicity between the gate, Spark, and the Iceberg commit; retry converges, it is not a transaction
Airflow, this S9 DAG path: DagBag / `dags test` wiring only
Airflow, earlier Spark/Iceberg skeleton: local `standalone` scheduler / LocalExecutor evidence exists
neither is production Airflow — no HA, no distributed executor, no deployed scheduler
no real OT/ROS2/MCAP/edge-hardware input; the edge is simulated by a local spool
no streaming: this is a bounded batch publish, not a Kafka-to-Iceberg sink
runtime MongoDB is still unverified in this environment; the Mongo path is covered by mongomock
```

A retry being "safe" means the published table does not change. It is not a whole-pipeline no-op —
Spark still starts and the quality suite still runs before the skip decision.

## 8. Three-minute interview explanation

> The interesting part of this project is not that it moves data. It is that it refuses to.
>
> A plant link drops, so events buffer at the edge and replay when it comes back. The naive
> pipeline runs the batch as soon as data reappears, and the daily number silently moves while part
> of the window is still in flight. To prevent that I sealed each disconnected session with an
> expected last sequence, which is what lets the system distinguish "hasn't arrived yet" from
> "lost" — without a seal you cannot make that distinction at all.
>
> Completeness is decided by business `event_id` membership, not by Kafka offset continuity. In the
> actual run, edge sequences 1-3 landed at offsets 0, 1 and 4, because a replay puts the same event
> at a new offset. Those are different identity spaces and conflating them would give both false
> alarms and false confidence.
>
> Completeness turned out not to be sufficient. The batch adapter selects every accepted event for
> that date, so one extra same-date event from another path yields a batch that passes the
> completeness check and is no longer the session I sealed. So the gate also requires exact set
> equality before Spark starts — and it runs before any Spark import, so a partial recovery leaves
> no warehouse and no adapter output at all.
>
> After that the existing quality suite and Iceberg partition overwrite are reused unchanged, and a
> same-source retry produces no new snapshot. One detail I would call out: the engine mints a fresh
> run id even on a skipped retry, so the evidence records the snapshot as *reused* and marks the
> producing run unknown rather than implying the retry created it.
>
> The boundary is deliberate: synthetic data, one session, one partition, one local table. Public
> CI runs the base unit and contract suite; Kafka, Spark and Airflow evidence comes from documented
> local runbooks.

## 9. How this was built

AI accelerated question discovery and candidate implementation. Acceptance required explicit
contracts, counterexamples, runtime state evidence, and independent review; multiple false evidence
claims were rejected before `accepted-closed`.

Concretely, the rejected claims included a skipped retry implying it had created the snapshot it
reused, a verification check whose condition could pass even after the counterexample it guarded
disappeared, and "retry is a no-op" describing a path that still runs Spark and the quality suite.
The behaviour was correct in each case; the recorded claim was not, and that is what the review
gates were for.

## Detail links

- Decision: [`../../../learn/reference-decisions/recovery-gated-publish-boundary.md`](../../../learn/reference-decisions/recovery-gated-publish-boundary.md)
- Slice map: [`../../../learn/system-design/slices/09-recovery-gated-spark-iceberg.ko.md`](../../../learn/system-design/slices/09-recovery-gated-spark-iceberg.ko.md)
- Whole-platform trace: [`../../../learn/system-design/01-system-traceability-map.ko.md`](../../../learn/system-design/01-system-traceability-map.ko.md)
- Code: [`../../../src/manufacturing_data_platform/pipeline/recovered_telemetry_publish.py`](../../../src/manufacturing_data_platform/pipeline/recovered_telemetry_publish.py)
- Tests: [`../../../tests/test_recovered_telemetry_publish.py`](../../../tests/test_recovered_telemetry_publish.py)
- Runbook: [`../../../scripts/verify_recovered_telemetry_publish.sh`](../../../scripts/verify_recovered_telemetry_publish.sh)
- Verification history: [`../../../VERIFICATION_LOG.md`](../../../VERIFICATION_LOG.md)
