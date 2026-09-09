# Changelog

This repository has no published release yet. Entries describe local changes and the release candidate;
a date and immutable Git tag are added only after remote CI and release verification succeed.

## Local guided explanation preview — version unassigned

- Added three selected questions about the currently reviewed source/version, handoff limits and
  descriptive time gaps, using authorized server query results with evidence navigation.
- Added a desktop side panel and narrow-screen dialog, with context invalidation, cancellation,
  timeout/retry and keyboard handling. No provider, free-text AI conversation or stored chat history.
- Verified API tests, actual HTTP/export/restart and Chromium full/sample behavior; see
  [dated evidence](docs/VERIFICATION.md#guided-explanation-verification).
- This local feature is not a published release or an added prerequisite for the existing `0.1.0` candidate.

## Unreleased — `0.1.0` candidate

### Added

- Telemetry Review browser flow for CSV validation, equipment/tag/time-range analysis and a
  version-pinned CSV plus manifest export.
- Separate latest-attempt and last-good state, retained-input retry and a public-sample delivery
  failure exercise.
- Transactional SQLite persistence, workspace isolation, CSRF and origin checks, storage bounds,
  integrity read-back and expiry/deletion behavior.
- Bundled, attributed MetroPT-3 one-day sample and actual HTTP/browser/cold-checkout verification.
- Digest-pinned Python 3.12 container with its own dependency lock, a non-root user, persistent data
  volume, read-only root filesystem, health check and release/revision labels.
- Configurable `sample` mode that disables arbitrary uploads for a bounded public preview while
  retaining the complete local CSV workflow in `full` mode.
- Apache-2.0 licensing for original code and documentation, with the bundled MetroPT-3 excerpts and
  derived samples kept under their attributed CC BY 4.0 terms.

### Known limitations

- No public deployment, independent user acceptance, account recovery or organization sharing has
  been verified.
- Public-preview rate limits, TLS/host configuration, storage lifecycle and runtime monitoring must
  be checked on the selected host before deployment.
- The file-review contract is separate from the retained MetroPT/OPC UA collection laboratory.
  File retry does not establish sensor recovery, OPC UA recollection idempotency or distributed
  exactly-once processing.
