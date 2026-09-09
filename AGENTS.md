# Repository working guide

## Start here

1. Read [README](README.md) for the operator outcome and replay boundary.
2. Read [PROJECT_STATUS](PROJECT_STATUS.md) for the current change, evidence and next gate.
3. For the web service read [File Review Contract](docs/FILE_REVIEW_CONTRACT.md); for OPC UA read
   [Contract](docs/CONTRACT.md). Then read the selected item in [Backlog](docs/BACKLOG.md).
4. Check `git status --short --branch`, `git rev-parse HEAD` and the actual diff before editing.

The repository must be sufficient for a new session. Product facts and commands must
not depend on a private workspace, chat transcript, a particular model, or installed skills.
Use [Architecture](docs/ARCHITECTURE.md) to locate code; historical pipelines are separate evidence.

## Product sources and change lifecycle

- Keep the README as the front door and link each question to one living owner. Research and design
  proposals stay in the existing research or Backlog location until the product owner accepts them;
  they do not become current behavior because they are newer or more detailed.
- Accepted promises remain in the relevant Contract even when implementation is incomplete. Treat that
  mismatch as an implementation or release gap. Change an accepted rule together with its Contract,
  implementation, affected browser and API consumers, and meaningful tests.
- Architecture maps current responsibility; PROJECT_STATUS points to one current change; Backlog owns
  bounded future work; Verification records commands, revisions, observed results and limits. A release
  note or source commit is a candidate claim. Actual deployment requires the built artifact, environment,
  activation state and runtime read-back.
- When sources conflict, compare the same scope and version against accepted meaning and actual behavior.
  Classify the result as a code defect, documentation gap or proposed policy change instead of automatically
  choosing the newest prose or the code.
- Before moving or removing a source, inspect inbound links, generated consumers, supported versions and
  the exact Git recovery point. Keep one owner for current meaning, update the former entry to point to it,
  and preserve historical evidence when readers still need its original claim boundary.

## Work and verification

- Keep one implementation change active. The selected backlog item owns its outcome,
  non-goal, strongest counterexample and completion evidence. Do not create parallel status files.
- Preserve existing dirty changes. Use a short-lived branch from the verified integration baseline.
- Change an accepted rule together with its code, affected consumer and meaningful test.
- Run `make setup`, `make test`, `make verify`; [Verification](docs/VERIFICATION.md) explains outputs
  and optional runtimes. Setup requires Python 3.10+ and uv. It installs into this repo's `.venv`.
- Do not turn missing optional dependencies or skipped tests into runtime success.
- Read actual reports and `current → manifest → data`; an implementation summary is insufficient.
- For the file service, use `make serve` and [File Review Guide](docs/FILE_REVIEW_GUIDE.md). Verify
  upload/query/export through HTTP and the browser, including previous-result and failure behavior.
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
