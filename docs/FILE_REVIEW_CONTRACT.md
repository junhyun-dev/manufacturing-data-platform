# Telemetry File Review — first usable slice

The author authorized building a usable service candidate on 2026-09-08. This slice serves a person
who receives telemetry CSV exports, checks whether the file can support a selected analysis, and
shares the checked result. It is a local release candidate; external adoption and deployment are separate.

## User outcome

Upload a file or open the bundled public sample → inspect validation and source limitations →
query one equipment/tag/time range → download those rows with a manifest → replace a faulty file
and compare the new result. The public sample also supports an explicitly labelled delivery-failure
exercise and retained-input recovery. The exercise never manufactures a missing physical measurement.

This is a new **file review** contract. Uploaded files do not pass through `industrial_telemetry_v1`:
that existing contract retains its MetroPT/OPC UA provenance, status, and replay meaning.

## Input and calculation rules

- UTF-8 CSV, required columns `timestamp,equipment,tag,value,unit`; optional `quality`. Header order
  is free; other columns and duplicate headers are refused. A downloadable template is provided.
- At most 8 MiB and 50,000 data records per upload. No local path or remote URL ingestion endpoint.
- One record is one equipment/tag/timestamp observation. Exact duplicate keys are refused, including
  identical duplicates. Unit changes within an equipment/tag series are refused; no implicit conversion.
- ISO timestamps must be consistently timezone-aware or timezone-unspecified. Aware values normalize
  to UTC before duplicate detection. Unspecified times remain source wall time and are labelled accordingly.
- `value` must be finite. A supplied `bad` quality can have an empty value, but still prevents publication.
  Quality accepts `good`, `uncertain`, `bad`, `unspecified`, case-insensitively. Missing/blank quality means
  `unspecified`, never `good`. Other values are errors. Supplied uncertain/bad quality blocks publication.
- An otherwise valid file with unspecified quality may pass **file validation**. Its unknown quality count
  remains visible in the result and export. This does not certify sensor accuracy or OPC UA quality.
- Queries select one equipment/tag and `[start, end)`. Statistics are SQL sample count/mean/min/max;
  empty ranges return count zero and null statistics. No interpolation or time-weighted average.
- Source intervals above 60 seconds are descriptive gaps, not inferred outages or missing-record counts.
  A plot may show at most 500 actual points; aggregates and downloads use all selected records.
- Equipment, tag and unit labels are 1–128 characters without control characters. Timestamps normalize
  to fixed microsecond precision for chronological comparison; finer precision is refused, never truncated. UTC query inputs without an explicit offset
  are interpreted as UTC, as labelled by the client. SQL averages scale finite values before accumulation
  to avoid overflow; this is a floating-point sample mean, not decimal-exact arithmetic.

## State, identity and recovery

- Each anonymous browser workspace owns its datasets; identifiers alone never grant cross-workspace access.
  Workspace cookies expire after 24 hours; inactive workspaces are removed on subsequent session creation/startup.
  Users can delete a dataset immediately. Files are stored on the running server, not only in the browser.
- Original bytes are immutable and SHA-256 pinned. A version hashes contract version, source SHA, time basis,
  and canonical normalized rows. Filenames, browser identity and attempt clocks do not change that content version.
- Latest attempt and last published version are separate. A blocked replacement keeps the previous result available
  with its original source/version and an explicit latest-failure notice. A result never silently changes source range.
- SQLite transactions commit attempt history, immutable version and current pointer together. Reads use one snapshot
  and verify raw-source and version hashes before analysis or export. Recovery rechecks the retained original bytes.
- The sample-only failure exercise removes a nonempty subset from actual delivery while retaining the original
  expected record set. Recovery evaluates the complete retained input. A repeated recovery converges to the same
  content version. This is file delivery recovery, not OPC UA recollection or distributed exactly-once processing.
- A changed upload creates a new source/version after validation. A malformed input cannot be repaired by clicking
  retry; a corrected file must be provided. Last-good data remains unchanged on refusal or transaction failure.
- Resource bounds: 10 datasets per workspace, 32 MiB raw/normalized retained bytes per workspace, 256 MiB globally,
  100 retained attempts per dataset. Expiry/deletion removes associated sources and versions as one transaction.
- SQLite sets `PRAGMA user_version=1`. Startup refuses a database with a higher schema version instead of opening it
  with older code. Same-version volume restart is supported; online backup and downgrade recovery are not claimed.

## Runtime modes and artifact identity

- `MFG_REVIEW_MODE=full` is the default loopback workflow and permits upload and replacement. `sample` is the bounded
  public-preview candidate: upload and replacement are refused server-side with HTTP 403 `UPLOADS_DISABLED`, and the
  client removes those controls. Invalid mode values refuse startup.
- Sample mode still creates anonymous workspaces and retained sample datasets. It does not supply request-rate limiting,
  public TLS, monitoring, or an abuse boundary; those belong to an approved host configuration before deployment.
- `MFG_REVIEW_RELEASE` and `MFG_REVIEW_REVISION` identify the running artifact through `/healthz`; they are operator/build
  inputs and do not by themselves prove that a Git tag or release exists.
- The release container uses a digest-pinned Python base, dependencies pinned by `requirements-service.lock`, a
  non-root `10001:10001` user, read-only root filesystem, bounded `/tmp`, and a writable SQLite volume. The verified
  deployment unit remains one process plus one database; horizontal replicas are unsupported.

## HTTP interface for the first client

All routes are same-origin. Mutations require the session cookie and `X-Review-CSRF` from `/api/session`.
Every dataset route checks workspace ownership. Errors use `{"error":{"code":"...","message":"..."}}`.

| Route | Result |
|---|---|
| `GET /api/session` | `{csrf_token, capabilities: {uploads, sample, accounts}, release, limits, expires_hours: 24}`; sets workspace cookie |
| `GET /api/datasets` | `{datasets: [dataset, ...]}` |
| `POST /api/datasets?name=...` | Raw CSV body; `{dataset}`. Validation refusal is a recorded dataset result, not a HTTP transport failure |
| `POST /api/datasets/sample` | `{dataset}` from the pinned bundled public sample |
| `GET /api/datasets/{id}` | `{dataset}` with latest attempt, current version and recent history |
| `POST /api/datasets/{id}/replace?name=...` | Raw CSV body; `{dataset}` |
| `POST /api/datasets/{id}/delivery-check` | Sample only; `{dataset}` after intentionally incomplete delivery |
| `POST /api/datasets/{id}/retry` | `{dataset}` after re-evaluating retained original bytes |
| `DELETE /api/datasets/{id}` | `{deleted: true}` |
| `GET /api/datasets/{id}/query?equipment=...&tag=...&start=...&end=...&version=...` | Query result below; omitted range selects all; omitted version pins current at read time |
| `GET /api/datasets/{id}/explanation?question=...&latest_attempt_id=...&version=...&equipment=...&tag=...&start=...&end=...` | Guided explanation preview defined below; requires explicit version and the latest attempt seen by the query |
| `GET /api/datasets/{id}/export?...same filters...&version=...` | ZIP with selected `observations.csv` and `manifest.json`; version is required |
| `GET /api/template.csv` | Small valid user-file template |
| `GET /healthz` | `{status, contract, release, revision, mode}` after a SQLite read; no private file paths |

Dataset shape (null current means no usable published result):

```json
{
  "id": "opaque-id", "name": "압축기 기록", "source_kind": "upload",
  "latest": {
    "id": 1, "kind": "import", "status": "ready", "at": "ISO UTC",
    "source_name": "observations.csv", "source_sha256": "sha256",
    "expected_rows": 3, "observed_rows": 3, "missing_rows": 0,
    "issues": [], "quality_counts": {"good": 0, "unspecified": 3, "uncertain": 0, "bad": 0},
    "version": "sha256", "version_changed": true
  },
  "current": {
    "version": "sha256", "source_name": "observations.csv", "source_sha256": "sha256",
    "rows": 3, "time_basis": "unspecified", "published_at": "ISO UTC",
    "range": {"start": "2020-02-01T00:00:00", "end": "2020-02-01T00:00:20"},
    "quality_counts": {"good": 0, "unspecified": 3, "uncertain": 0, "bad": 0},
    "series": [{"equipment": "APU-1", "tag": "Oil_temperature", "unit": "°C", "count": 3}]
  },
  "history": []
}
```

Issues have `code`, `message`, optional `row` (1-based CSV data-record number). Status is `ready`, `incomplete`,
or `blocked`. History contains the most recent 12 attempt objects, newest first. Query shape:

```json
{
  "version": "sha256", "latest_status": "ready", "previous_result": false,
  "time_basis": "unspecified", "equipment": "APU-1", "tag": "Oil_temperature", "unit": "°C",
  "filter": {"start": null, "end": null},
  "summary": {"count": 3, "mean": 53.625, "min": 53.6, "max": 53.675,
    "gap_count": 0, "max_gap_seconds": 10,
    "quality_counts": {"good": 0, "unspecified": 3, "uncertain": 0, "bad": 0}},
  "points": [{"timestamp": "2020-02-01T00:00:00", "value": 53.6, "quality": "unspecified"}],
  "displayed_points": 3, "rows": []
}
```

`rows` is a preview of at most 100 selected normalized observations; export includes the complete selection.
Each point includes `gap_before`, derived from the underlying selected intervals rather than the distance
between decimated display points. Dataset responses include nullable `current_error`: an integrity failure
sets current to null and preserves access to file management; query/export still refuse the broken artifact.
`previous_result` is true when the displayed version differs from the latest successful attempt or the latest attempt
was refused. It is not a freshness/SLA promise. Export text fields escape spreadsheet-formula prefixes and the manifest
records that transformation, source hash, version, query, quality limitations, CSV digest and generation time.

## Guided result explanation — first local preview

On 2026-09-09 the author accepted continuing with a helper that explains the currently reviewed CSV result.
The first local implementation uses three selectable questions and deterministic explanations of real server facts.
It is a step toward the researched conversational helper, not an implemented general-purpose AI chat.
No provider, paid call, external data transfer, free-text question collection, account system, or release/deployment is authorized by this scope.

### Outcome and questions

After a replacement is refused, a person can identify the retained source/version, understand why its statistics remain,
and find the same result's evidence before sharing it. The lower-right entry is `이 결과에 질문` and the panel is `결과 설명`.
The panel states that it explains selected questions from checked data and is not AI free conversation.

| Question ID | Visible question | Required answer and limit |
|---|---|---|
| `previous_result` | `왜 이 결과가 보이나요?` | Distinguish refused latest attempt + retained version, current successful result, and an explicitly queried older version. Identify the actual source and latest status; never call failed replacement rows analyzed data. |
| `handoff_limits` | `전달할 때 무엇을 적어야 하나요?` | Show selected count/sample mean, pinned source/version/range/time basis and unspecified-quality count; link the same result evidence. Missing quality is not Good and file validation is not sensor certification. Empty selection has zero count and no mean. |
| `gap_limits` | `시간 공백은 설비 중단인가요?` | Show descriptive gap count and maximum observed interval; no inferred downtime, lost-record count, causal diagnosis, or physical normality. Fewer than two observations cannot establish an interval. |

### Data and HTTP boundary

The existing query response gains additive `latest_attempt_id`, from the same authorized, integrity-checked snapshot
as the query result. Existing query/export calculation, defaults, response fields and manifest semantics remain supported.

`GET /api/datasets/{id}/explanation` accepts the question enum above, positive integer `latest_attempt_id`, a nonblank
explicit `version`, and the existing equipment/tag/start/end parameters. Missing or invalid required arguments are 422;
a blank version is 400 `VERSION_REQUIRED`. It authorizes the workspace and uses `Store.snapshot()` and the existing
`query()` calculation. A latest-attempt mismatch returns 409 `CONTEXT_CHANGED` without explanation content.
Existing session, cross-workspace, unknown/deleted version, invalid-filter and integrity errors remain enforced.
There is no alternate SQL, filesystem, URL, raw-upload or provider access path. Apart from existing workspace activity
refresh, the route does not modify dataset/attempt/source/version/current or store questions/answers.

Response shape (values are actual server facts; it contains no observation rows or chart points):

```text
{
  mode: "guided", question: enum,
  context: {dataset_id, version, source_name, source_sha256,
            latest_attempt_id, latest_status, equipment, tag, unit, time_basis, filter},
  latest: {id, kind, status, at, source_name, expected_rows, observed_rows, missing_rows},
  previous_result: boolean,
  summary: <existing query summary>,
  title: string, paragraphs: [plain-text string, ...],
  evidence: ["query", "source", "history"]
}
```

Evidence IDs are a fixed allowlist of existing on-page targets, not arbitrary response URLs. A response describes the
snapshot read during that request, not a promise that another tab cannot change the dataset afterwards.
Source labels are inert data; render them with textContent, never model HTML/markdown. Existing quotas and deployment
limits still apply. This preview has no provider call or token charge and does not establish public abuse resistance.

### Browser lifecycle and accessibility

- Explanation requests copy `state.query`'s last successful parameters, version and latest-attempt ID. Editing filter
  controls without submitting must not change answer scope. Display `마지막 조회 결과 기준` and the pinned context.
- No successful result means no explanation request; show a useful instruction. An empty successful query is explainable
  and must not recall an earlier mean. Dataset change, new query, replace/retry, deletion or reload invalidates prior
  explanation content and in-flight requests. A 401/404/integrity/context-changed response clears content and asks the user
  to reload/review the dataset; it never falls back to a remembered answer.
- Keep at most one explanation request in flight. Show loading, cancel and explicit retry on failure; a 10-second
  browser timeout stops waiting. No automatic retries or provider work. Cancel/close and context changes invalidate
  late responses even if transport abort does not stop server computation. Only the latest valid request can render.
- Keep at most one answer in tab memory, with no localStorage/server conversation history. Close cancels pending work;
  completed content may be reused only while the same verified query context remains active. Dataset deletion/expiry
  clears it when the client observes that event; no cross-tab instantaneous revocation claim.
- At desktop width, use a right panel with enough room for context and evidence. At narrow width use a modal dialog
  occupying the available viewport. Provide a visible close button, initial focus, Escape and focus return; trap focus
  only for the modal state and make its background inert. Resizing across modes may close cleanly.
- Evidence actions close the panel and move focus/scroll to the corresponding current query/source/history section.
  They may not silently navigate to a newer dataset/version. Keyboard, 320/390px and 1440px layouts must remain usable.

### Falsifying checks and completion

Check independent expected numbers and identity against query/export; failed replacement and retained-version selection;
ready latest plus older explicit version; empty range, missing quality and long gap; unknown question/missing pins;
cross-workspace access, deletion/expiry and tampering; changed latest attempt between query and explanation; labels with
markup/instruction text; unsubmitted filter edits; delayed responses after cancel/switch/delete/new query; timeout/retry;
keyboard/modal behavior and actual mobile/desktop screenshots. Assert attempts/current do not change on explanation.
Full/sample browser and real HTTP read-back must retain the existing upload/query/export/recovery flow.
These prove the guided preview's behavior; AI accuracy, user task improvement and general conversation remain unverified.

## Completion and public-release boundary

Verify normal upload, sample-mode upload refusal, rejected replacement preserving an earlier result, corrected replacement, sample delivery failure
and stable recovery, empty/timezone/unit/duplicate cases, corrupt retained source/version, independent browser isolation,
CSRF/size bounds, restart persistence, actual browser use and export read-back. A fresh checkout must launch with one command
after setup and use the bundled sample without the author's cache. Inspect mobile and desktop screens.

Local runtime binds loopback. A public deployment requires a concrete approved host/TLS/runtime configuration, reviewed
anonymous-data retention and resource limits, and user authorization for publishing/deployment. Real plant connections,
accounts/organization sharing, live streaming, sensor diagnosis, production uptime and market adoption remain out of scope.
