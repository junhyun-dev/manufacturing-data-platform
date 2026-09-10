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

## Equipment data map — first local view

On 2026-09-10 the author accepted the researched B direction: select an equipment group in one file,
see its measurement items as a small map, then inspect observations and export the same version's evidence.
This is a local UI change. Physical asset identity, health, causality, plant topology, graph storage,
external data/AI, public release and deployment are not part of this acceptance.

### Meaning and data authority

- The map represents membership in one authorized, integrity-checked dataset version. The first view used the
  selected CSV equipment label as its center; the accepted Graph canvas section below extends presentation to
  file-local groups. All groups and items come only from that version's `current.series`.
  Display identity includes dataset ID, version, equipment, tag and unit. Identical names in another file
  or workspace never create a link. A label is not a verified global asset identifier.
- Lines mean `이 파일 버전에 기록된 측정 항목`. They have no direction, flow, causal, correlation or physical
  distance meaning. Measurement nodes have equal size; selection uses text plus a visible outline.
  A failed file attempt must not color an equipment/item node as a physical fault.
- Distinguish current result availability/version, latest file-attempt status and `설비 상태: 판단 근거 없음`.
  The bundled sample is a historical train-compressor record with an added equipment label, not live plant data.
  Keep original observation range/time basis visible, separate from server processing times in recent history.
  Sample delivery failure remains explicitly identified as an exercise. No continuous health/uptime timeline.
- Node counts, if shown, are whole-version series counts. Selected-range statistics, chart, quality and export
  remain owned by the existing server query/export paths. Missing quality is not Good; gaps are not outages.
  No new API, stored graph, metadata ingestion, calculation, permission or retention policy is introduced.

### Selection, layout and accessibility

- Preserve `equipment-filter`, `tag-filter`, the explicit `조회` action and existing range controls. The map and
  native selectors share one draft equipment/tag selection. Changing equipment or tag clears the old successful
  query, visible statistics/export eligibility and explanation, and invalidates in-flight query responses.
  Selecting a node fills the item selector and shows `선택한 항목을 조회해 주세요` until a successful query.
  Do not automatically request every node's statistics. Selecting the already selected node need not clear a result.
- Date-only edits retain the existing last-successful-query behavior: statistics/export/explanation stay bound to
  the submitted range, with that range visible; draft date values are not represented as already calculated.
  A new query clears the previous result while it loads. Dataset changes and replace/retry/recovery reset the
  map/query/explanation together using the refreshed authorized dataset description.
- At desktop width, show the equipment map and selected-item analysis in a connected layout. Keep the item's
  name, unit, version context, observation plot and source-evidence action easy to find. Reuse existing source/history
  sections and the result-explanation panel rather than opening a competing overlay or duplicating calculations.
- At narrow width, stack the content and keep the complete native item list available. A labelled show/hide-map
  control may default to collapsed on narrow screens. Both map buttons and native selectors must work by keyboard.
  Use ordinary buttons with accessible names and pressed state; decorative SVG lines are hidden from assistive
  technology. No drag, hover, color or animation is the only way to discover a relation, select an item or read evidence.
- The first local view used at most eight measurement nodes. The Graph canvas section below replaces that
  presentation bound with explicit group expansion and bounded pages. Keep complete native equipment/item
  selectors and honest displayed/total counts. Long/untrusted labels remain inert text, readable from the complete
  list/detail without page overflow.
- Stable acceptance targets: `equipment-map-section`, `equipment-map`, `map-selection-status`, `map-refresh`,
  `map-source-link`, `map-view-toggle`, `map-overflow`, and measurement buttons with `data-map-tag`.
  Existing query, chart, source/history, export and explanation IDs remain available.

### Changed context and failure

- Each query captures dataset/version/latest-attempt and submitted selection. Render only if its request generation,
  active dataset, version and equipment/tag still match. Compare the response version and latest-attempt ID with
  the captured description: a mismatch clears the map/result and requests an explicit file refresh, not a silent
  combination of old membership and new attempt state. This detects observed drift; it is not instantaneous cross-tab revocation.
- Missing current, deletion/expiry/authorization denial or integrity failure clears obsolete map and result content
  when observed by dataset, query, explanation or export paths. Show a useful unavailable state and a `map-refresh`
  action where a refresh can recover. A generic transient network error may retain the labelled map context,
  but not a failed query's old statistics. Failed refresh must not make stale content appear freshly verified.
- Existing server workspace authorization, immutable-source checks, last-good publication and export pinning remain
  enforcement points. Render all labels with textContent or equivalent safe DOM setters. Store no separate graph,
  remembered cross-dataset selection or external dependency state.

### Completion evidence

Use real HTTP and Chromium against local full/sample modes. Verify public sample membership and independent CSV
counts/aggregates/hash → successful selection → matching ZIP; refused replacement/delivery and retained version;
recovery, no-current/integrity/expired/deleted/cross-workspace failures; empty selection; more than eight items;
same equipment label in separate files; long markup labels; late query response after selection/context change;
transient failure and explicit refresh. Check actual desktop/390/320px screenshots, keyboard map/list selection,
selected-node focus, source-evidence focus and the existing explanation modal. Synthetic multi-equipment data is
a test fixture, not evidence of plant relationships. Passing these checks establishes local behavior; the map's
advantage over the existing selectors and independent user task success remain unverified.

## Review navigation — wide view, fullscreen and item search

Accepted on 2026-09-10 for local implementation. The equipment-map contract above remains in force.
The outcome is finding a measurement by its full name and reading its observations, source and matching ZIP
in a wider connected workspace. This is presentation/metadata navigation, not a new analysis or identity model.
That initial navigation acceptance covered layout and search. The later Graph canvas section below adds map
zoom/pan and replaces the eight-node presentation bound. Physical relation/health inference, graph editing or
execution, a graph store, new data API, persistence or external call remain outside the accepted scope.

### Wide view and fullscreen lifecycle

- A `넓게 보기` / `기본 화면으로` button changes the existing document layout, preserving the original DOM
  and all current map/list/query/source/history/export/explanation targets. Reduce surrounding navigation space;
  keep dataset/equipment/version context, query controls, chart and evidence reachable. Narrow screens stack
  and scroll normally; the wider mode must not require dragging or suppress browser text/page zoom.
- Entering/leaving either presentation mode never changes dataset/version/latest-attempt pins, draft selection,
  submitted range, successful result, explanation answer or ZIP parameters, and never triggers a data query.
  An in-flight query may finish normally across a mode change. Only existing data/selection actions invalidate it.
- Fullscreen is optional and entered from an explicit user gesture. Request it on the document root so that the
  existing explanation panel, toast and native deletion dialog remain available. Enter wide layout first.
  Pending fullscreen transitions prevent duplicate requests; UI state follows actual `fullscreenElement` /
  `fullscreenchange`, not an optimistic boolean. Unsupported/denied requests leave ordinary wide view usable
  and show a plain-language status. No-current/unavailable content cannot initiate a new expanded view.
- Fullscreen exit (button, Esc or browser/system exit) leaves ordinary wide view. `기본 화면으로` also exits
  native fullscreen before restoring the base layout. If exit fails, retain reachable exit controls and report it.
  Re-entering is explicit. Keep the current selection/result and restore focus to the corresponding mode control
  and the appropriate saved scroll position when returning to base view; never focus a hidden/removed element.
- Modal ownership takes precedence: deletion confirmation handles its own Escape; the narrow explanation
  dialog retains focus containment and closes once. A fullscreen event while either is open must not steal
  focus or activate deletion, close a second layer by application handlers, or strand background inert state.
  Error/no-current content inside an already expanded view stays readable with usable exit controls.

### Search is metadata navigation

- Search all `current.series` items for the currently selected equipment in the authorized dataset/version.
  Match tag name by trimmed, case-insensitive plain substring (no regex, fuzzy alias or cross-file search).
  Render names and units as inert text. Expose full names, match/total counts, an explicit no-match state and clear.
  Keep the original complete native equipment/tag selectors. The Graph canvas section owns revealing the selected item.
- Typing, clearing, paging or focusing results makes no HTTP request and changes no draft selection, submitted
  result, explanation or export. A selection outside the search results is explicitly still the current selection.
  Empty search shows an instruction/total count and uses the existing full list; it need not duplicate every item.
- Bound a nonempty search to 20 result buttons per page with reachable previous/next controls and accurate
  page/match counts. Every match is reachable. This is a rendering bound, not a new accepted data-size limit.
  Result selection uses the same existing item-selection action; selecting a different tag clears old statistics,
  export and explanation until explicit query. Selecting the already selected item preserves the successful result.
- Dataset/equipment switch and refreshed dataset descriptions clear the search term/page. Observed context,
  authorization, expiry, deletion or integrity failures clear/disable stale search results with the map; a generic
  query failure may retain valid metadata but cannot revive old statistics. Delayed responses follow existing pins.
- Stable targets: `review-wide-toggle`, `review-fullscreen-toggle`, `review-view-status`, `tag-search`,
  `tag-search-clear`, `tag-search-status`, `tag-search-results`, `tag-search-prev`, `tag-search-next`,
  and result buttons with `data-search-tag`. Preserve search focus while typing/paging; choosing a result puts
  focus on the corresponding existing selected map button or native selector. Long names must wrap without page overflow.

### Completion evidence

Use actual full/sample HTTP and Chromium. Establish successful query/ZIP context, then assert that modes,
search/clear/page and fullscreen errors do not change it or add queries. Check real native fullscreen entry/exit
separately from labelled unsupported/rejection/event-order injections; do not report an API stub as native support.
Check basic/fullscreen explanation and deletion-dialog coexistence, button/Escape focus return, 1440/390/320px,
orientation/200% browser text scaling, normal scrolling, and keyboard-only selection to matching ZIP.
Use the actual three-item sample and labelled synthetic 8/11/50/200-item inputs with similar/128-character/markup
names. Include zero matches, selection beyond the first eight/page, another equipment/file with the same name,
empty results, refused replacement/retained current, changed latest attempt, transient failure, integrity/deleted/
expired/cross-workspace refusal and delayed query across view/selection changes. Reuse existing server oracles.
Record measured fixture behavior without claiming production capacity, independent user success or release.

## Graph canvas — file-local membership exploration

Accepted for first local implementation on 2026-09-10 after the author clarified the diagram-workspace intent.
This section replaces the first map's eight-item presentation limit. Existing validation, ownership, last-good,
query, export, guided explanation and wide/fullscreen promises remain in force. Implementation and browser
verification status are recorded in PROJECT_STATUS and Verification; acceptance alone is not a passing runtime.

### Outcome and rendering boundary

- Explore equipment-label groups and their measurement membership in one authorized dataset/current version,
  expand/collapse groups, pan/zoom the map, find the displayed overview or selected item, and inspect the existing
  observation/source/same-version ZIP detail. No inter-equipment physical, health, causal or execution edges.
- Group expansion is view state, not equipment selection. Multiple groups can be open. A measurement button
  identifies both equipment and tag; identical tags in different groups never select the wrong series. Keep
  equal measurement-node dimensions, inert full names/units in detail and selection text plus outline.
- Initial rendering budget: at most 20 equipment groups per group page and 200 measurement buttons in total.
  Start with the selected group open. Divide the measurement budget among open groups; a group uses explicit
  previous/next item pages if it exceeds its share. When only one group is open, all its first 200 items can be
  drawn together. Budget changes on expansion must retain valid group page offsets and provide honest counts.
  This is a view budget, not a CSV acceptance limit or measured production capacity. Main may adjust it downward
  only after recording measured browser evidence and preserving access to all accepted input items.
- Group pages and per-group item pages show ranges/counts and labelled previous/next actions. Complete native
  equipment/tag selectors and current-equipment name search remain available. No node is silently lost because
  of a render budget. Group paging/collapse may hide a selected node; its selected detail/query remains valid.
  A selected-position action reveals its group/page and puts the node in view. Ordinary native or search item
  selection also reveals that item; group-page changes alone never select another equipment.
- Use deterministic, non-overlapping group/measurement layout and a shared world coordinate system for DOM
  buttons and decorative SVG membership lines. No user graph editing, draggable node placement or saved layout.
  A small public sample remains historical 1-group/3-item data. Multi-group/50/200-item examples are synthetic.

### Camera and input

- Provide stable controls `map-zoom-in`, `map-zoom-out`, `map-zoom-level`, `map-fit`, `map-focus-selection`,
  `map-pan-toggle`, `map-pan-left`, `map-pan-right`, `map-pan-up`, `map-pan-down`, `map-camera-status`, and
  `map-minimap`. Keep `equipment-map` as the clipped viewport and use `map-world` for transformed content.
  Group controls expose `data-map-equipment` and `data-map-toggle`; group item paging uses `data-map-items-prev`,
  `data-map-items-next`, `data-map-items-status` with the equipment label as value. Item buttons retain `data-map-tag` and
  additionally identify their equipment. Use `map-groups-prev`, `map-groups-next`, `map-groups-status` for paging.
- Zoom changes the map camera only. Initial technical range is 1%–200%; very small scale is an overview, not
  a readable-name claim. Fit computes bounds of the currently displayed nodes with padding; it does not expand
  hidden data. Selected-position reveals the selected node at a readable scale (at least 75%) and centers it.
  Focus entering a node keeps that node visible at a readable scale without changing data selection.
- Provide pointer pan on background in an explicit labelled move mode, plus click/tap directional buttons and
  keyboard-equivalent controls. Ignore node/control starts, distinguish a drag from a click, and end safely on
  pointercancel/lost capture. Exit move mode with its button or viewport Escape. Do not intercept modal Escape.
  Normal page scrolling and browser zoom remain available outside that explicit mode; do not capture Ctrl/Cmd
  browser zoom. Any optional wheel camera binding must be documented and confined to the map (Alt+wheel).
- The minimap shows the displayed node layout and current viewport rectangle, labelled as displayed content.
  Clicking it can move the camera; provide the same movement without dragging via the direction/fit controls.
  Minimap graphics need not duplicate every node in the keyboard tab sequence.
- Camera controls and detail do not scale with the world. Viewport resize/wide/fullscreen must retain a usable
  camera and selection; avoid unconditional fit on every query or transient render. Respect reduced motion.
  At 1440/390/320px and browser text zoom, the toolbar, list, detail and exit path remain reachable. A labelled
  narrow map toggle remains available; no huge world dimensions may overflow the document itself.

### State, lifecycle and integration

- Pan/zoom/fit, move mode, minimap, group/page expansion and selected-position make no API request and do not
  change dataset/version/latest attempt, draft equipment/tag, submitted range, successful query, explanation
  or ZIP. They must not cancel a pending valid query. Camera state is local and disposable, not stored history.
- Explicit item selection from another group updates the existing equipment/tag controls as one selection action,
  then uses the existing query/explanation invalidation path. Same-item selection preserves the successful result.
  Date-only draft edits keep the submitted-range meaning. Search typing/clear/paging stays presentation-only.
- Key graph state to dataset/version/latest attempt from the authorized description. File switch, replace/retry/
  recovery/refresh, missing current and observed context/auth/deletion/expiry/integrity failure discard stale graph
  metadata and pending camera callbacks. Generic query failure may retain valid metadata; never restore old stats.
  A late callback from a previous dataset must not redraw, select or focus its old nodes in the new context.
- Reuse the current result/source/history/explanation and wide/fullscreen controls. Respect modal ownership:
  no viewport shortcut/focus-in handler may activate inert content, close a second layer or steal dialog focus.
  No API/schema/store/model change, raw CSV calculation, external dependency request or graph database is required.
- Technical first implementation: ordinary DOM/SVG plus a small local map controller using browser pointer and
  resize APIs. Keep graph layout/camera responsibilities separate from existing app selection/query code; a local
  `map-canvas.js` file may be loaded before app.js. No third-party package or renderer conversion is required.

### Completion evidence

Main directly reviews the diff and actual Chromium screens. Check real sample and labelled synthetic 8/11/50/200
items, multiple equipment groups with identical tags, more than 20 groups and more than 200 items; assert counts,
complete reachability, non-overlapping world boxes and layout/pan/zoom response timings rather than claiming
capacity from a static bound. Verify camera and grouping while a query is held, same/other item selection,
source and independent CSV/ZIP identity, previous-result/delivery/recovery, transient and context failure,
empty results, deleted/expired/cross-workspace/integrity refusal, hostile long labels, 1440/390/320px, keyboard,
click-only navigation, pointer cancellation, minimap, real wide/fullscreen entry/exit and existing modal coexistence.
Reuse unaffected HTTP oracles; update earlier browser expectations only where this accepted presentation changed.

### Dedicated map fullscreen

Accepted on 2026-09-10 after the author asked for the equipment map itself to occupy the screen. This extends
the display layout only; the preceding camera/data/query/evidence and modal safety rules remain unchanged.

- Place `map-fullscreen-toggle` (지도 전체화면 / 지도 보기 나가기), `map-fullscreen-status`, and
  `map-review-link` (관측·근거로 돌아가기) in the map's reachable controls. Keep a compact selected item/status
  and existing source link. The canvas fills remaining viewport width/height after these compact controls;
  sidebar, chart, table and verbose context do not consume the dedicated map area. Use the existing map DOM,
  not a clone, so handlers, camera, selected item and pending query remain the same.
- A `map-fullscreen-layer` inside the application shell may temporarily host the existing map section;
  restore it to its original location on exit. Make covered background content non-interactive/unfocusable
  while preserving pre-existing inert values. Existing explanation and native delete dialog retain ownership;
  neither may be hidden behind the map or closed as a side effect of an application Escape handler.
  The same explanation launcher may join the map header during this mode and return to its original parent
  on exit, so it cannot cover evidence/return actions. Keep exit controls reachable while scrolling.
- Native fullscreen still targets the document root so existing dialogs remain in its fullscreen subtree.
  Enter map-focused layout first; when unsupported/denied keep a clearly labelled browser-area fallback.
  Status follows actual fullscreen state, not a requested boolean. Serialize pending entry/exit, avoid duplicate
  requests, and retain a visible exit on failure. Entering from an existing review fullscreen must not request
  another native entry. A map exit restores the prior base/wide layout and narrow map expansion; exit only
  native fullscreen acquired by this map entry. Browser/system fullscreen exit also leaves the dedicated map.
- Fallback Escape leaves the map unless a dialog/explanation owns it; Escape used to end an active map drag
  must not additionally close another layer. Exit and evidence navigation restore visible valid focus and scroll.
  The existing source link or guided-answer evidence first returns to normal review before focusing its target;
  `map-review-link` focuses the successful analysis, or query controls when a new selection needs a query.
- View entry/exit and evidence navigation launch no query and change no file/version/latest-attempt pins,
  draft or submitted range, successful result, explanation answer, ZIP or map selection. Normal explicit item
  selection still uses existing invalidation. An explicit guided-answer evidence click retains its existing
  close/discard policy; the map transition itself must not discard an answer. Context loss/deletion must not strand exit controls in a hidden
  ancestor; restore the underlying error/empty view safely, with the normal native exit still reachable.
- Verify actual map bounds, not only a fullscreen attribute: at 1440×900 the map viewport should occupy at
  least 85% of viewport width and 65% of viewport height; at 390×844 and 320×844 at least 90% width and 50%
  height. Shorter/zoomed screens may scroll compact controls, while exit remains reachable. Check zoom/pan,
  fit/minimap and selected position on real sample and a labelled synthetic 200-item fixture; preserve query
  and matching ZIP across entry/exit and a held response. Test real native entry/exit separately from injected
  rejection/unsupported/exit-failure cases, and verify keyboard focus plus explanation/delete-dialog coexistence.
  Reuse unaffected data oracles; this narrow display change does not require a new full repository run.
The existing OPC UA timestamp failures and missing independent user task observations remain separate open work.

## Completion and public-release boundary

Verify normal upload, sample-mode upload refusal, rejected replacement preserving an earlier result, corrected replacement, sample delivery failure
and stable recovery, empty/timezone/unit/duplicate cases, corrupt retained source/version, independent browser isolation,
CSRF/size bounds, restart persistence, actual browser use and export read-back. A fresh checkout must launch with one command
after setup and use the bundled sample without the author's cache. Inspect mobile and desktop screens.

Local runtime binds loopback. A public deployment requires a concrete approved host/TLS/runtime configuration, reviewed
anonymous-data retention and resource limits, and user authorization for publishing/deployment. Real plant connections,
accounts/organization sharing, live streaming, sensor diagnosis, production uptime and market adoption remain out of scope.
