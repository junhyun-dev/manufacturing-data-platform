# Industrial telemetry trust contract

This document describes existing bounded behavior. Executable validation lives beside the code;
new semantics require a contract change. See [Architecture](ARCHITECTURE.md) for component ownership.

## User and outcome

The proposed user is a data platform operator deciding whether a collected source range is fit
to expose to an analyst or ML engineer. The implemented result is a decision plus a local,
versioned JSONL dataset. A downstream analysis workflow and external user acceptance remain unverified.

Inputs are three rows of the public MetroPT-3 recording and three mapped tags. Local OPC UA
replay and deliberate faults exercise the collection boundary. This is not live factory ingestion.

## Identity, time and quality

| Boundary | Rule | Executable owner |
|---|---|---|
| Source | Verify exact CSV SHA-256 and schema; the committed fixture and full CSV have different hashes | [`industrial_source/source.py`](../src/manufacturing_data_platform/industrial_source/source.py) |
| Observation | `event_id = SHA256(source file hash : physical row : tag_id)`; row/tag selection defines the expected set | [`industrial_source/contracts.py`](../src/manufacturing_data_platform/industrial_source/contracts.py) |
| Time | Preserve the original timezone-unknown wall time; encode it as UTC **for replay transport only**. Keep server, collection and arrival timestamps separate | same contract; [`event_time_trust/core.py`](../src/manufacturing_data_platform/event_time_trust/core.py) |
| Value | Keep equipment/tag, unit, mapping version, OPC UA status and source/replay/fault provenance. Bad values are null; Good/Uncertain values are finite | same observation contract |
| Collection | Completeness means exact expected/observed identity coverage, not row count or guessed cadence | [`industrial_source/spool.py`](../src/manufacturing_data_platform/industrial_source/spool.py), [`report.py`](../src/manufacturing_data_platform/industrial_source/report.py) |
| Arrival | Same identity and identical canonical bytes is a duplicate; different bytes is a conflict | `event_time_trust/core.py` |

`bounded-event-time-v1` permits 15 seconds behind the greatest previously seen source timestamp.
An event exactly on that boundary is accepted; one before it is too late. This is a fixture policy,
not a measured source SLA. Arrival sequence orders evaluation; received-at time does not prove completeness.

Expected-set coverage describes delivery of the selected file observations. It does not establish
continuous acquisition from the physical equipment or explain gaps already present in the source CSV.
The [source audit](BACKLOG.md#mfg-08--product-value-and-source-reality) records this distinction;
its proposed consumer rules are not implemented contract changes.

## Decisions and persistence

| Condition, in evaluation priority order | Internal status | Visible action | Trusted current |
|---|---|---|---|
| Conflict, unexpected identity, or too-late event | `reprocess_required` | `REPROCESS REQUIRED` | unchanged |
| Expected accepted identities are missing | `incomplete` | `REPROCESS REQUIRED` | unchanged |
| Coverage is complete but contains Uncertain or Bad | `blocked_quality` | `BLOCKED` | unchanged |
| Exact coverage, no conflict/late rejection, all Good | `publishable` | `PUBLISH` | eligible version becomes current |

Source collection uses `complete` for its normal scenario. It is not interchangeable with the later
event-time `publishable` status. `REPROCESS REQUIRED` currently recommends an action; it does not execute recovery.

Publication writes immutable data and manifest, then an atomic local current pointer. Before publication,
the existing `current → manifest → data` chain is read and checked. A broken chain produces integrity
failure evidence and blocks replacement. Refusal preserves last-good. These are local single-writer
semantics; atomic rename does not establish concurrent-writer ordering or distributed transactions.

Dataset identity includes **all canonical observation bytes**, mapping versions, source identity and
policy version. Server and collection timestamps are among those bytes. Therefore:

- Reordering or duplicating the **same collected observations** converges to the same dataset version.
- A fresh OPC UA replay can retain the same event IDs but produce a new dataset version because the
  collection metadata changed. Source-level retry idempotency is not an established contract.
- Replaying into an existing sealed spool is not a supported recovery command. Use a fresh output root.

## Proof and limits

Run `make verify` for the committed three-row fixture. It retains collection spools, seals, reports,
five arrival scenarios, a trusted dataset, environment identity and read-back results. The checks
assert 9 accepted normal/disordered observations, 6 too-late-scenario accepted observations,
8 missing-scenario observations and blocked quality despite 9 observations.

[Verification](VERIFICATION.md) distinguishes fresh local runs from the historical public report.
Actual analyst use, recovery execution, throughput, live security, HA and production operation are
outside the established claim. [Backlog](BACKLOG.md) owns proposed extensions and their exit tests.
