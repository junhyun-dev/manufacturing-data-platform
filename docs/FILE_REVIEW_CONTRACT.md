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

## HTTP interface for the first client

All routes are same-origin. Mutations require the session cookie and `X-Review-CSRF` from `/api/session`.
Every dataset route checks workspace ownership. Errors use `{"error":{"code":"...","message":"..."}}`.

| Route | Result |
|---|---|
| `GET /api/session` | `{csrf_token, limits: {upload_bytes, rows, datasets}, expires_hours: 24}`; sets workspace cookie |
| `GET /api/datasets` | `{datasets: [dataset, ...]}` |
| `POST /api/datasets?name=...` | Raw CSV body; `{dataset}`. Validation refusal is a recorded dataset result, not a HTTP transport failure |
| `POST /api/datasets/sample` | `{dataset}` from the pinned bundled public sample |
| `GET /api/datasets/{id}` | `{dataset}` with latest attempt, current version and recent history |
| `POST /api/datasets/{id}/replace?name=...` | Raw CSV body; `{dataset}` |
| `POST /api/datasets/{id}/delivery-check` | Sample only; `{dataset}` after intentionally incomplete delivery |
| `POST /api/datasets/{id}/retry` | `{dataset}` after re-evaluating retained original bytes |
| `DELETE /api/datasets/{id}` | `{deleted: true}` |
| `GET /api/datasets/{id}/query?equipment=...&tag=...&start=...&end=...&version=...` | Query result below; omitted range selects all; omitted version pins current at read time |
| `GET /api/datasets/{id}/export?...same filters...&version=...` | ZIP with selected `observations.csv` and `manifest.json`; version is required |
| `GET /api/template.csv` | Small valid user-file template |
| `GET /healthz` | Liveness/readiness with contract version, no private file paths |

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

## Completion and public-release boundary

Verify normal upload, rejected replacement preserving an earlier result, corrected replacement, sample delivery failure
and stable recovery, empty/timezone/unit/duplicate cases, corrupt retained source/version, independent browser isolation,
CSRF/size bounds, restart persistence, actual browser use and export read-back. A fresh checkout must launch with one command
after setup and use the bundled sample without the author's cache. Inspect mobile and desktop screens.

Local runtime binds loopback. A public deployment requires a concrete approved host/TLS/runtime configuration, reviewed
anonymous-data retention and resource limits, and user authorization for publishing/deployment. Real plant connections,
accounts/organization sharing, live streaming, sensor diagnosis, production uptime and market adoption remain out of scope.
