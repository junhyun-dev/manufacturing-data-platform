# Repository working guide

## Start here

1. Read [README](README.md) for the operator outcome and replay boundary.
2. Read [PROJECT_STATUS](PROJECT_STATUS.md) for the current change, evidence and next gate.
3. Read [Contract](docs/CONTRACT.md), then the selected item in [Backlog](docs/BACKLOG.md).
4. Check `git status --short --branch`, `git rev-parse HEAD` and the actual diff before editing.

The repository must be sufficient for a new session. Product facts and commands must
not depend on a private workspace, chat transcript, a particular model, or installed skills.
Use [Architecture](docs/ARCHITECTURE.md) to locate code; historical pipelines are separate evidence.

## Work and verification

- Keep one implementation change active. The selected backlog item owns its outcome,
  non-goal, strongest counterexample and completion evidence. Do not create parallel status files.
- Preserve existing dirty changes. Use a short-lived branch from the verified integration baseline.
- Change an accepted rule together with its code, affected consumer and meaningful test.
- Run `make setup`, `make test`, `make verify`; [Verification](docs/VERIFICATION.md) explains outputs
  and optional runtimes. Setup requires Python 3.10+ and uv. It installs into this repo's `.venv`.
- Do not turn missing optional dependencies or skipped tests into runtime success.
- Read actual reports and `current → manifest → data`; an implementation summary is insufficient.
- If a finding does not prevent this outcome, record it in Backlog rather than opening another feature.
- A new user, source, recovery policy, lateness policy, or dataset identity rule needs an explicit
  contract decision before implementation. Keep proposals marked as proposals.

## Side effects and closeout

Local fixture replay, a repo virtualenv, tests, branches and local generated evidence are permitted.
The runtime binds loopback OPC UA ports and writes fresh directories under `.cache/telemetry-runs/`.
No plant endpoint, credentials, cloud service, Kafka broker or production data is needed.

Push, PR publication, merge, deployment, external messages, paid resources and production connections
require the user's confirmation for that action. A local passing run is not a release or user acceptance.
Do not start another AI or a standing reviewer without authorization.

At handoff, update PROJECT_STATUS with the actual phase, source revision or diff boundary,
verification result and **one** next action. Record `NOT RELEASED` when appropriate. Retained runs are
local evidence, not product current; keep only useful runs after their exact paths and recovery needs
are understood. Never delete the entire `.cache` or an existing virtualenv as routine setup.
