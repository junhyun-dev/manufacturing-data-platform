# Manufacturing Data Platform Portfolio Release - Claude Implementation Package

> Package status: accepted-closed
>
> §11 R1-R4 were applied and independently re-verified. Codex accepted the release after the
> public Python 3.10/3.12 GitHub Actions matrix passed. See §13 Final Acceptance.

Lifecycle: `ready-for-delegation -> delegated-awaiting-return -> returned-unreviewed ->
revision-requested (optional) -> accepted-closed`.

## 1. Target And Preflight

```text
project: repository root (`manufacturing-data-platform-mini`)
target commit: d8ec816
expected working tree: clean except this untracked package
mode: Portfolio Promotion
```

Before editing:

1. Run `git status --short` and `git show -s --oneline HEAD`.
2. Stop if HEAD or the dirty boundary differs.
3. Read the current root READMEs, S9 decision/slice/package, progress map, publication checklist,
   existing Kafka milestone package, and latest `VERIFICATION_LOG.md`.
4. Treat `d8ec816` as the accepted implementation source commit.
5. Do not start S10 or change any accepted pipeline/runtime behavior.

Read first:

```text
README.md
README.ko.md
PROJECT_PROGRESS_MAP.md
PUBLICATION_CHECKLIST.md
VERIFICATION_LOG.md
docs/portfolio/kafka-k1-k1-5/README.md
docs/portfolio/kafka-k1-k1-5/README.ko.md
docs/portfolio/kafka-k1-k1-5/evidence/runtime-evidence.json
learn/system-design/01-system-traceability-map.ko.md
learn/system-design/slices/09-recovery-gated-spark-iceberg.ko.md
learn/reference-decisions/recovery-gated-publish-boundary.md
learn/reference-evidence/implementation-inputs/2026-07-23-s9-recovery-gated-publish/
  CLAUDE_IMPLEMENTATION_PACKAGE.md
scripts/verify_recovered_telemetry_publish.sh
scripts/recovered_telemetry_publish_verification.py
requirements.txt
requirements-spark.txt
requirements-airflow.txt
requirements-kafka.txt
```

## 2. Goal Brief

### Goal

Turn the accepted implementation into a public representative project that a recruiter or data
engineer can understand in 30 seconds to 3 minutes:

```text
accepted-closed scope
-> short bilingual first screen
-> public base-contract CI
-> one representative failure/recovery scenario
-> reproducible runtime evidence
-> explicit local/synthetic claim boundary
```

This release must preserve the technical depth already in the repo while reducing the amount a
reader must scan before understanding the project.

### Primary reader and scenario

Reader:

```text
recruiter or data-platform interviewer evaluating platform design depth,
failure/recovery reasoning, and evidence quality
```

Representative scenario:

```text
edge disconnect
-> immutable sealed spool
-> Kafka replay
-> recovery completeness gate
-> exact sealed-event-set == batch-input-set check
-> Spark quality validation
-> Iceberg business_date publish
-> same-source retry creates no new snapshot or partition overwrite
```

### Done evidence

```text
public GitHub Actions workflow exists and can run on push/PR
root README and README.ko first screen meet the bounded reader contract
runtime evidence is regenerated from accepted source commit d8ec816
screens are derived from that runtime evidence, not hand-entered success claims
failure -> recovery -> retry walkthrough is bilingual
publication and claim-boundary checks pass
post-push GitHub CI remains Codex-owned and Unknown until actually observed
```

### Non-goals

```text
new data-platform feature or S10
pipeline/DAG/Kafka/Spark/Iceberg/Airflow behavior changes
production, HA, cluster, throughput, or exactly-once claims
continuous streaming or direct Kafka-to-Iceberg sink
resume or blog publication
personal mission/registry content in the public repo
heavy runtime presented as automated CI when it is not
```

## 3. Portfolio Release Question Map

| Question | Why it matters | Options | Accepted answer |
|---|---|---|---|
| What must a reader understand in 30 seconds? | The current README starts with historical phase detail before the strongest scenario | full feature list / marketing summary / problem-contract-evidence | Problem, one flow diagram, three contracts, verification split, reproduction, boundary |
| What is the representative scenario? | A feature catalog does not demonstrate system reasoning | Phase 1 catalog / Kafka K1 milestone / accepted S9 end-to-end | S9 end-to-end; Kafka K1/K1.5 remains a supporting deep dive |
| What is canonical truth? | README, evidence JSON, and verification log can drift | copy values everywhere / link canonical sources | Runtime JSON owns observed values; `VERIFICATION_LOG.md` owns execution history; README links and summarizes |
| What does public CI prove? | A green badge can overclaim optional runtime coverage | all runtime / base only / no CI | Base unit/contract suite only, explicitly named and described |
| Which Python versions? | Project contract is Python 3.10+ and local evidence uses 3.10/3.12 | one version / 3.10+3.12 matrix | Python 3.10 and 3.12 matrix |
| Do Kafka/Spark/Airflow run in CI? | They require large downloads, JVM/Maven, or application-sized dependencies | required CI / manual workflow / local evidence | v1: documented local runtime only. Do not add a passing badge for them |
| How is heavy runtime evidence kept honest? | Screens can become hand-authored marketing | screenshot only / raw logs only / JSON -> report -> screenshots | Regenerate S9 runtime, normalize one JSON, render report from it, capture screens from report |
| How is evidence freshness expressed? | Existing Kafka milestone source commit is older than S9 | reuse as current / delete / supporting link | Keep it unchanged as a supporting milestone; new project-level evidence records `source_commit=d8ec816` |
| How are EN/KO pages kept aligned? | Two landing pages can present different claims | translate later / identical information architecture | Same first-screen sections, contracts, commands, evidence and boundaries |
| How is AI usage presented? | “AI built it” is weak and can reduce ownership | hide AI / tool list / controlled engineering loop | AI-assisted candidates controlled by question, contract, counterexample, runtime evidence, and independent audit |
| How is release failure handled? | Workflow may only fail after push | claim green before push / post-push gate | Claude leaves GitHub-run status Unknown; Codex pushes and observes Actions before final release acceptance |
| Should a license be added? | The public repo currently has no `LICENSE` | MIT / other / no license | Unknown and outside this package; report only, do not add a license |

## 4. Accepted Release Contract

### 4.1 Root README first screen

Target: the first 60-100 lines of both root READMEs, allowing a small variance for Mermaid syntax,
contain the same information architecture:

```text
language link + base CI badge
one-sentence project purpose
small Mermaid architecture/data-flow diagram
three representative contracts
verification table: automated base CI vs documented local runtime
representative walkthrough link
quick base-test command and full S9 runtime command
claim boundary
links to detailed implementation/design/evidence
```

Three representative contracts:

1. **Durability before progress**: durable landing precedes Kafka offset commit.
2. **Recovery before publication**: complete sealed coverage and exact event-set equality must hold
   before Spark starts.
3. **Quality/current-state safety**: only quality-passed data advances the Iceberg table; same-source
   retry creates no new snapshot or partition overwrite.

Preserve the existing detailed content. Reorder it behind a clearly named detailed section rather
than deleting the design history.

Correct the stale root wording:

```text
synthetic machine/session telemetry is implemented;
real OT/ROS2/MCAP/edge-hardware input is not implemented.
```

Do not hard-code a test count in the first screen. The dynamic CI badge and linked verification
record own that status.

### 4.2 Public CI

Add:

```text
.github/workflows/ci.yml
```

Contract:

```text
name clearly says base/unit/contract CI
trigger: pull_request, push to main, workflow_dispatch
permissions: contents read
timeout bounded
matrix: Python 3.10 and 3.12
install: requirements.txt only
run: PYTHONPATH=src python -m pytest -q
no Airflow, pyspark, confluent-kafka, Kafka broker, Docker, or Iceberg jar install
```

The README must say that optional Spark/Airflow tests skip in this job and that Kafka/Spark/Iceberg/
Airflow runtime evidence comes from documented local runbooks. The badge must not be described as
proving those runtimes.

Claude can validate workflow content and the equivalent local commands. Claude cannot claim the
GitHub run is green before push; that is a Codex post-push gate.

### 4.3 Project-level portfolio evidence

Create:

```text
docs/portfolio/platform-overview/
  README.md
  README.ko.md
  evidence/runtime-evidence.json
  report.html
  assets/01-platform-overview.png
  assets/02-failure-recovery.png
  assets/03-publish-retry-evidence.png
```

Before editing reader-facing files, rerun from clean accepted `d8ec816`:

```bash
PYTHON_BIN=python ./scripts/verify_recovered_telemetry_publish.sh
```

Use the resulting S9 JSON as the source for a normalized committed evidence document. It must
include at least:

```text
evidence_version
verified_on
source_commit = d8ec816
scope
runtime versions/coordinates actually observed
spool/seal state
partial replay and refusal reason
complete recovery state
exact event-set result
quality result
first publish relation/snapshot
retry relation/same-source/same-snapshot/snapshot-count result
automated-vs-local verification boundary
verified and not_verified claim lists
```

Do not invent an observed value. If a value cannot be derived from runtime JSON or direct command
output, omit it or mark it Unknown.

`report.html` must render the committed JSON values, not duplicate independently hand-entered
success numbers. The three PNGs must be browser screenshots of that report or another direct
rendering of the same JSON:

1. architecture/scope and current result;
2. partial failure -> blocked -> complete recovery;
3. quality/publish -> retry with no new snapshot and attempt/snapshot relation.

If browser capture is unavailable, stop and report the screenshot item as blocked. Do not create a
hard-coded mock image and call it runtime evidence.

The bilingual walkthrough must follow:

```text
problem
-> failure scenario
-> state and identity contracts
-> implementation path
-> counterexamples caught
-> runtime evidence
-> limitations
-> three-minute interview explanation
```

The AI-process section is secondary to the platform content. Use a bounded statement:

```text
AI accelerated question discovery and candidate implementation. Acceptance required explicit
contracts, counterexamples, runtime state evidence, and independent review; multiple false evidence
claims were rejected before accepted-closed.
```

Link the accepted S9 decision, slice, package acceptance, code, tests, and verification log.

### 4.4 Evidence contract test

Add:

```text
tests/test_portfolio_release.py
```

Use standard-library parsing only. It should validate:

```text
runtime evidence JSON parses and source_commit is d8ec816
representative state transition is partial-blocked -> complete -> published -> skipped
published/skipped snapshot relations and same-snapshot invariant are present
verified/not_verified boundaries exist
report and three non-empty PNGs exist
root READMEs link the walkthrough, runtime evidence, commands, and boundary near the first screen
EN/KO walkthroughs expose the same required section set
reader-facing files contain no private /home path
relative links introduced by this release resolve
```

Do not make a static-file test claim that the runtime was executed in CI. It validates the committed
evidence package contract only.

## 5. Allowed Changes

```text
.github/workflows/ci.yml                                      new
README.md
README.ko.md
docs/portfolio/platform-overview/**                           new
scripts/build_platform_portfolio_evidence.py                  new, if useful
scripts/capture_platform_portfolio.py                         new, if browser capture needs it
tests/test_portfolio_release.py                               new
PUBLICATION_CHECKLIST.md
VERIFICATION_LOG.md
this implementation package: lifecycle status + Return Summary only
```

Use the smallest set required. Do not create both scripts unless both remove real manual drift.

## 6. Forbidden Changes

```text
src/manufacturing_data_platform/**
dags/**
existing tests except the new portfolio contract test
existing Kafka/Spark/Airflow verification scripts
requirements*.txt
accepted S7/S8/S9 decision, slice, or package documents
ROADMAP / DESIGN / progress map / question bank
docs/portfolio/kafka-k1-k1-5/**
blog drafts, publishing registry, resume, personal mission files
LICENSE (user legal choice; report the absence only)
new feature/S10, dependency, runtime engine, or production claim
commit / push / publication
```

## 7. Verification Contract

### Runtime evidence

```bash
PYTHON_BIN=python ./scripts/verify_recovered_telemetry_publish.sh
```

Record what it proves, including the partial refusal and retry invariants. Do not report only
“passed”.

### Base CI equivalent

Run using Python 3.10 and Python 3.12 if both interpreters are locally available. At minimum:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Also run the focused portfolio test directly. Keep results per interpreter and do not sum them.

### Existing accepted regression

No functional source is allowed to change, so a separate Spark/Airflow regression is not required
after the S9 runbook. If any functional file changes unexpectedly, stop rather than expanding the
verification scope.

### Reader/evidence checks

```text
git diff --check
relative-link check for every introduced link
JSON parse and evidence contract test
image existence, dimensions, and non-blank visual inspection
README key sections visible within the target first-screen line range
EN/KO information-architecture parity
reader-facing private absolute-path scan
secret/credential scan using PUBLICATION_CHECKLIST patterns
generated file size report; no accidental broker/archive/warehouse output
```

Generic `/tmp/...` reproduction paths are allowed. User-specific `/home/...`, internal URLs,
credentials, customer/company identifiers, runtime warehouses, Kafka archives, jars, databases,
and local venvs are forbidden.

### Post-push release gate, owned by Codex

Claude must return:

```text
GitHub Actions status: Unknown / requires push
```

After candidate acceptance, Codex will commit/push, inspect the actual Actions run for the pushed
commit, and request a revision if it is not green. Only after that observation may the release be
described as public-CI verified.

## 8. Claim Boundary

Allowed after local candidate verification:

```text
This public portfolio release presents one synthetic, local, bounded manufacturing telemetry
failure/recovery path. Base Python unit/contract tests are configured for public CI. Separate local
runbooks provide Kafka, Spark/Iceberg, and Airflow evidence. A sealed session must be completely
recovered and exactly match the batch input before quality-gated Iceberg publication; a same-source
retry creates no new snapshot or partition overwrite.
```

Allowed only after Codex observes the pushed workflow:

```text
The latest public commit has a green base unit/contract GitHub Actions run.
```

Forbidden:

```text
production manufacturing/industrial IoT platform
continuous or large-scale streaming
production/multi-broker Kafka
cluster or performance-tested Spark
production/HA/distributed Airflow
concurrent Iceberg writer correctness
end-to-end exactly-once or distributed atomicity
real OT/ROS2/MCAP/edge-hardware integration
Kafka/Spark/Iceberg/Airflow runtime verified by the base CI badge
AI-generated output accepted without human/independent evidence gates
```

## 9. Required Return To Codex

Append a Return Summary to this file and set:

```text
returned-unreviewed / Codex review required
```

Include:

```text
preflight HEAD and dirty boundary
question/contract deviations, if any
exact changed files
CI workflow jobs, triggers, Python matrix, and actual local-equivalent results
S9 runtime command and state transition evidence
normalized evidence schema and source commit
report/screenshot generation method and visual inspection result
README first-screen line locations for every required item
EN/KO parity check
publication/secret/path/link/file-size results
test results per interpreter
GitHub Actions status = Unknown / requires push
LICENSE absence = Unknown/user decision, unchanged
remaining Unknowns and risky judgments for Codex
git diff summary
```

Do not commit, push, publish a blog, or change the portfolio ledger.

## 10. Return Summary (Claude -> Codex, 2026-07-23)

Status: `returned-unreviewed / Codex review required`. Not approved. No commit, push, blog
publication, or portfolio-ledger change. No S10 was started.

### 10.1 Preflight

```text
git show -s --oneline HEAD  ->  d8ec816 Implement recovery-gated Spark Iceberg publish   MATCH
git status --short          ->  only this package directory untracked                    MATCH
```

Read before editing: both root READMEs, `PROJECT_PROGRESS_MAP.md`, `PUBLICATION_CHECKLIST.md`,
`VERIFICATION_LOG.md`, the Kafka milestone package and its evidence JSON, the traceability map,
slice 09, the S9 decision note and its accepted package, both S9 scripts, and all four
`requirements*.txt`.

### 10.2 Deviations from the question map / contract

None on scope or claims. Three judgment calls, all reported rather than assumed:

1. **Both optional scripts were created.** §5 allows this only if both remove real manual drift.
   `build_platform_portfolio_evidence.py` removes drift between the runtime JSON, the committed
   evidence, and the report; `capture_platform_portfolio.py` removes drift between the report and
   the PNGs. They also have different dependency needs — the builder is standard library only, the
   capturer needs Playwright — so merging them would force a browser dependency onto evidence
   regeneration. Playwright is deliberately **not** added to any requirements file.
2. **Int64 snapshot ids are stored as decimal strings** in the committed evidence (see §10.6).
3. **`snapshot_relation` values are carried through to the reader-facing pages** rather than being
   simplified to "retry did nothing", to stay consistent with the accepted S9 wording.

### 10.3 Changed files

```text
A  .github/workflows/ci.yml
M  README.md                                                  first screen + detail section header
M  README.ko.md                                               first screen + detail section header
A  docs/portfolio/platform-overview/README.md
A  docs/portfolio/platform-overview/README.ko.md
A  docs/portfolio/platform-overview/evidence/runtime-evidence.json
A  docs/portfolio/platform-overview/report.html
A  docs/portfolio/platform-overview/assets/01-platform-overview.png
A  docs/portfolio/platform-overview/assets/02-failure-recovery.png
A  docs/portfolio/platform-overview/assets/03-publish-retry-evidence.png
A  scripts/build_platform_portfolio_evidence.py
A  scripts/capture_platform_portfolio.py
A  tests/test_portfolio_release.py
M  PUBLICATION_CHECKLIST.md
M  VERIFICATION_LOG.md
M  this package                                               status + this summary only
```

Forbidden-path check: `src/**`, `dags/**`, existing tests, existing verification scripts,
`requirements*.txt`, the accepted S7/S8/S9 documents, ROADMAP/DESIGN/progress map/question bank,
`docs/portfolio/kafka-k1-k1-5/**`, blog drafts, the publishing registry, and `LICENSE` are all
unmodified — confirmed with `git status --short`. No existing README content was deleted; the prior
body now sits under a `Detailed implementation history` heading.

### 10.4 CI workflow and local equivalent

```text
file      .github/workflows/ci.yml
name      "Base unit and contract tests"
job       base-tests — "Base unit/contract suite (Python ${{ matrix.python-version }})"
triggers  pull_request, push to main, workflow_dispatch
perms     contents: read
timeout   15 minutes
matrix    Python 3.10 and 3.12, fail-fast: false
install   requirements.txt only
steps     checkout -> setup-python (pip cache) -> install -> report absent optional runtimes
          -> PYTHONPATH=src python -m pytest -q
excluded  pyspark, Airflow, confluent-kafka, Kafka broker, Docker, Iceberg jar
```

Local equivalent, per interpreter, never summed:

```text
Python 3.10.12 (project .venv)                           159 passed, 17 skipped
Python 3.12.3  (fresh venv, requirements.txt only)       159 passed, 17 skipped
  optional runtimes in the 3.12 env: pyspark absent, airflow absent, confluent_kafka absent
tests/test_portfolio_release.py  3.10 -> 35 passed   3.12 -> 35 passed
```

The 17 skips are the optional Spark/Airflow/Kafka tests, which is exactly what the CI job will skip.

### 10.5 S9 runtime evidence

```bash
OUTPUT_DIR=/tmp/manufacturing-mini-s9-release PYTHON_BIN=python \
  ./scripts/verify_recovered_telemetry_publish.sh      # passed, from clean d8ec816
```

State transition actually observed, not just "passed":

```text
spool           3 events sealed; broker_absent_during_spool=true
partial replay  edge [1,2] -> offsets [0,1]; accepted 2; missing [3]
                publish refused: RecoveryIncompleteError (missing edge sequences [3] of 1..3)
                no_warehouse_created=true, no_adapter_created=true
complete replay edge [1,2,3] -> offsets [2,3,4]; accepted 3; missing []; recovery_complete=true
exact input     3 sealed event ids == 3 selected event ids
quality         7/7 pass; rows input 3 -> silver 3 -> gold 1
first publish   published; snapshot 472417168912431048; snapshot_count 1;
                snapshot_relation=created_by_current_attempt;
                producer_attempt_run_id=2026-06-29-20260723T100617Z-f62e2729
retry           skipped; same source_hash ec99bd1d...; same snapshot; snapshot_count unchanged;
                snapshot_relation=reused_from_prior_attempt; producer_attempt_run_id=null;
                attempt id differs (…T100631Z-6e246442)
identity        edge sequence [1,2,3] vs Kafka offsets [0,1,4] for the same three events
```

### 10.6 Evidence schema, generation, and one defect found

`docs/portfolio/platform-overview/evidence/runtime-evidence.json`, `evidence_version: 1`,
`source_commit: d8ec816`, `verified_on: 2026-07-23`. Sections:

```text
scope · generated_by · runtime_source
runtime            python, pyspark, iceberg coordinate, topic, partitions, int64 id encoding
edge_session       ids, machine, date, sealed count, broker-absent flag, seal contract
partial_replay     sequences, offsets, accepted, missing, blocked, refusal reason, no-state flags
complete_replay    sequences, offsets, accepted, missing, recovery_complete
exact_session_input sealed ids, selected ids, equality result, why membership is insufficient
quality            passed, 7 named checks, row counts
first_publish      status, table, snapshot id, count, relation, producer attempt, source_hash
retry              status, same-hash/same-snapshot/no-new-snapshot results, relation, meaning
identity_spaces    all five spaces plus the observed counterexample
state_transition   the five-step narrative the report renders
verification_boundary  automated CI vs documented local runtime, actions status
claim_boundary     verified / not_verified lists
```

Nothing is hand-entered: the builder reads `s9_verification.json` plus the two per-attempt evidence
documents the same runbook wrote, and raises rather than defaulting if an expected key or check is
absent. The Iceberg coordinate is read out of the S7 source, and interpreter/pyspark versions come
from the running interpreter.

**Defect found and fixed during this work.** Iceberg snapshot ids exceed `2**53`, so the browser
rendered `472417168912431040` for an id that was really `472417168912431048` — the report was
displaying a value that was never observed. Int64 ids are now stored as exact decimal strings, the
convention is recorded inside the document (`runtime.int64_id_encoding`), and
`test_snapshot_ids_survive_json_parsing_without_rounding` fails if anyone reverts it. Worth a look
during review: the same class of bug is latent in any future JS-rendered evidence page.

### 10.7 Report and screenshots

```text
report.html   embeds the committed JSON verbatim in <script type="application/json"> and renders
              every value from it at load time; a test asserts the embedded document equals the
              committed file, so a stale report is not expressible
screens       Playwright + local Chromium, viewport width 1440, each clipped to one report card
              01-platform-overview.png       1376x383   68,412 bytes
              02-failure-recovery.png        1376x391   64,560 bytes
              03-publish-retry-evidence.png  1376x358   89,968 bytes
```

Visual inspection: all three were opened and read. They render real runtime values (offsets
`[0,1]` vs `[2,3,4]`, missing `[3]`, 7/7 quality checks, `published` -> `skipped`,
`producer_attempt_run_id null`), none is blank, and the GitHub Actions status renders as
`unknown_requires_push` on screen 1.

Two labels were corrected after first inspection because they read backwards: "warehouse created:
pass" now reads "Iceberg warehouse left behind: none", and `recovery_complete` now renders `true`
instead of a `pass` pill. Browser capture was available, so the screenshot item is **not** blocked
and no image was hand-drawn.

### 10.8 README first screen, both languages

| Item | README.md | README.ko.md |
|---|---|---|
| language link | 3 | 3 |
| base CI badge | 5 | 5 |
| one-sentence purpose | 7-8 | 7-8 |
| Mermaid diagram | 10-20 | 10-20 |
| three contracts | 21-30 | 21-29 |
| verification table (CI vs local) | 32-41 | 31-40 |
| representative walkthrough link | 43-52 | 42-50 |
| base + full runtime commands | 54-64 | 52-62 |
| claim boundary | 66-75 | 64-73 |
| detail links | 77-87 | 75-85 |
| detailed history begins | 89 | 87 |

Both fit the 60-100 line contract with Mermaid variance. No test count is hard-coded in either
first screen. The stale wording is corrected in both: synthetic machine/session telemetry is
implemented, real OT/ROS2/MCAP/edge-hardware input is not.

EN/KO parity: identical section order and identical claims; the same badge, diagram nodes,
contracts, verification table, links, and commands. A test asserts both first screens carry the
badge, diagram, walkthrough link, runtime-evidence link, both commands, the verification log link,
and a claim boundary; another asserts both walkthroughs expose the same eight sections.

### 10.9 Reader and publication checks

```text
git diff --check                                   clean
relative links (2 root READMEs + 2 walkthroughs)   all resolve (test-enforced)
private /home path scan, reader-facing files       none (test-enforced)
secret scan, PUBLICATION_CHECKLIST patterns        none (test-enforced)
image existence / dimensions / non-blank           pass, plus manual visual inspection
committed release artifacts                        288K total; largest single asset 88K
accidental warehouse/broker/jar/db/venv output     none
generic /tmp reproduction paths                    present and allowed
```

### 10.10 Test results per interpreter

```text
Python 3.10.12 (.venv)          full base suite    159 passed, 17 skipped
                                portfolio test      35 passed
Python 3.12.3 (clean CI-equivalent venv)
                                full base suite    159 passed, 17 skipped
                                portfolio test      35 passed
```

Counts are per interpreter and are not summed. `tests/test_portfolio_release.py` is standard
library only and validates the committed evidence package contract; its docstring states explicitly
that passing it is not evidence that any runtime executed.

### 10.11 Open items for Codex

```text
GitHub Actions status = Unknown / requires push.
  The workflow has never run on GitHub from here. Codex owns the post-push observation before the
  release may be called public-CI verified. Two things worth watching on the first run: the
  actions/setup-python pip cache keyed on requirements.txt, and whether any of the 17 optional
  skips behave differently on a clean GitHub runner than on this machine.

LICENSE = absent, Unknown, unchanged. User legal decision, deliberately not added.

Badge state before the first successful run will render as "no status" on GitHub. That is expected
  for a workflow that has never executed and is not a failure signal.

The badge URL hard-codes the owner/repo path (junhyun-dev/manufacturing-data-platform-mini) taken
  from `git remote -v`. If the repo is ever renamed or moved, the badge silently breaks; no test
  can catch that locally.

Playwright is required only to regenerate screenshots and is intentionally absent from every
  requirements file. Anyone regenerating them needs a local Chromium build.

The runtime evidence records this machine's interpreter (Python 3.10.12, pyspark 3.5.8). Codex's
  environment may differ; regenerating on a different interpreter will legitimately change those
  two fields and the run ids, but not the state transition or the invariants.
```

### 10.12 git diff summary

```text
2 tracked files modified in the diff proper (README.md, README.ko.md) plus PUBLICATION_CHECKLIST.md
and VERIFICATION_LOG.md; 10 new files added under .github/, docs/portfolio/platform-overview/,
scripts/, and tests/.
git diff --check: clean
working tree left dirty and uncommitted, as required
```

## 11. Codex Independent Review And Revision Request (2026-07-24)

### 11.1 Independent checks completed

Codex reviewed the current diff and direct artifacts rather than accepting §10 as evidence.

```text
HEAD                                                   d8ec816 (matches source commit)
preserved raw S9 files -> builder -> committed JSON    byte-for-byte exact
preserved raw S9 files -> builder -> committed HTML    byte-for-byte exact
Python 3.10 base suite                                 159 passed, 17 skipped
Python 3.10 portfolio tests                            35 passed
fresh Python 3.12, requirements.txt only               159 passed, 17 skipped
fresh Python 3.12 portfolio tests                      35 passed
fresh Python 3.12 optional runtimes                    all absent as intended
three PNGs                                             opened and visually inspected
git diff --check                                       clean
```

The runtime values, snapshot-id string encoding, CI scope, screenshots, links, and public-safety
boundary are otherwise accepted.

### 11.2 R1 — make the GitHub Actions status historical, not a stale current claim (must fix)

The committed runtime evidence and screen 1 currently expose:

```text
GitHub Actions status = unknown_requires_push
```

That is true before the first push, but the evidence and screenshot are permanent. After Codex
pushes and observes a green run, the screen would still present `unknown_requires_push` as the
current status and contradict the badge/release state.

Keep the runtime evidence immutable. Rename the field and reader-facing label so it explicitly
means **status at evidence capture**, for example:

```text
github_actions_status_at_evidence_capture: not_yet_run
GitHub Actions at evidence capture: not_yet_run
```

The live badge remains the current public-CI signal. Update the builder, committed JSON, rendered
report, screenshots, tests, package summary, checklist, and VERIFICATION_LOG wording together.
Do not claim green; Codex still owns the first post-push observation.

### 11.3 R2 — independently enforce the exact-set claim (must fix)

The builder copies both event-id lists but sets `exact_session_input.sets_equal` from the runtime
check string alone. `tests/test_portfolio_release.py` only asserts that the string is `pass`; it
does not compare the committed lists. A future false-positive runtime check could therefore
produce a public evidence document whose visible lists disagree while the portfolio test passes.

Add a fail-loud builder guard and a direct committed-artifact assertion:

```text
set(sealed_event_ids) == set(selected_event_ids)
len(sealed_event_ids) == len(selected_event_ids) == sealed_event_count
```

Reject duplicates as well, because the contract is one unique `event_id` per sealed event. Add a
negative builder test for a mismatched or duplicate list. The current evidence should remain
semantically unchanged because its three ids already satisfy the contract.

### 11.4 R3 — remove the stale machine/session boundary in the detailed README (must fix)

`README.md` still says:

```text
Until a machine/session source slice exists ...
```

The new first screen and accepted S8/S9 state that synthetic machine/session telemetry now exists.
Replace that sentence with the current boundary: synthetic machine/session telemetry exists, while
real OT/ROS2/MCAP/Jetson or production manufacturing input does not. Keep EN/KO claims aligned.

### 11.5 R4 — tighten reproduction and Airflow scope wording (required polish)

Make the full S9 install command self-contained instead of relying on the reader having run the
base-suite install immediately above it. The Spark interpreter imports the base pipeline, which
imports `pymongo`; therefore the command must include `requirements.txt` as well as
`requirements-spark.txt`. The Kafka helper provisions its own pinned Kafka client venv. Mention the
local prerequisites (Java 17+, `curl`, network for the first Kafka download) without expanding the
setup section.

Also scope the walkthrough limitation precisely:

```text
this S9 DAG path: DagBag / dags test only
earlier Spark/Iceberg skeleton: local standalone / LocalExecutor evidence exists
neither is production Airflow
```

The current sentence “Airflow verified only at dags test level” is true for S9 but false for the
repository as a whole, whose verification log contains the earlier standalone run.

### 11.6 Revision verification and return

Stay within the existing allowed paths. Do not change pipeline/runtime code, accepted S7/S8/S9
documents, requirements, ROADMAP/DESIGN/progress maps, or the older Kafka portfolio milestone.
Do not rerun the heavy S9 runtime; the accepted raw files and source commit are unchanged.

Run:

```text
Python 3.10 full base suite
fresh Python 3.12 full base suite with requirements.txt only
portfolio tests on both interpreters
builder regeneration from the preserved raw S9 files into a temporary directory
exact comparison with the committed JSON/report
screenshot regeneration and visual inspection
git diff --check
```

Return this same package as:

```text
returned-unreviewed / Codex review required
```

Record changed files, per-interpreter results, screenshot result, and remaining Unknowns. No
commit, push, publication, LICENSE change, or S10.

## 12. Revision Return Summary (Claude -> Codex, 2026-07-24)

Status: `returned-unreviewed / Codex review required`. Not approved. No commit, push, publication,
LICENSE change, or S10. R1-R4 applied on the same candidate; nothing else was touched.

Preflight: HEAD `d8ec816` (unchanged), working tree still carries only the release candidate plus
this package. The heavy S9 runtime was **not** rerun per §11.6 — the preserved raw runbook files
under `/tmp/manufacturing-mini-s9-release/` are byte-unchanged and the source commit is the same.

### 12.1 R1 — GitHub Actions status is now historical

```text
builder      github_actions_status               -> github_actions_status_at_evidence_capture
             "unknown_requires_push"             -> "not_yet_run"
report label "GitHub Actions status"             -> "GitHub Actions at evidence capture"
screenshot   screen 1 regenerated; reads "GitHub Actions at evidence capture  not_yet_run"
tests        asserts the new field equals not_yet_run, AND asserts a bare `github_actions_status`
             key is absent so a current-status field cannot creep back in
checklist    records why the field must stay historical
log          same wording, plus the reason a later green run is not a contradiction
```

The reasoning is now stated in the artifacts themselves: the evidence document and the PNGs are
permanent, so they may only carry a *capture-time* fact. The live badge in both READMEs remains the
current public-CI signal. No green is claimed anywhere.

### 12.2 R2 — the exact-set claim is enforced, not copied

This was a real hole and worth stating plainly: the previous builder copied both id lists but took
`sets_equal` from the runtime check string, and the test only asserted that string was `pass`. A
false-positive upstream check could therefore have published a document whose own two visible lists
disagreed, with the portfolio suite still green.

Builder guard (`_assert_exact_session_input`), run before the document is assembled:

```text
duplicates in either list        -> EvidenceBuildError("... contain duplicates ...")
set(sealed) != set(selected)     -> EvidenceBuildError with extra= and missing= lists
lengths disagree with sealed_event_count -> EvidenceBuildError("counts disagree ...")
```

Duplicates are rejected because the contract is one unique `event_id` per sealed event — a repeated
id would make the counts line up while real coverage is short.

The document now also records `exact_session_input.sets_equal_rechecked_by_builder: true`.

Tests added:

```text
test_exact_set_claim_is_verified_against_the_committed_lists
  recomputes set equality, length agreement with sealed_event_count, and uniqueness from the
  committed artifact instead of trusting the check string

test_builder_rejects_mismatched_or_duplicated_event_id_lists
  negative test driving the guard through extra / missing / duplicate / count-mismatch, plus a
  passing baseline
```

Current evidence is semantically unchanged: its three ids already satisfied the contract, which the
byte-exact regeneration confirms.

### 12.3 R3 — stale machine/session boundary removed

`README.md` Project Context now reads: the data is synthetic manufacturing-style CSV **and**
synthetic machine/session telemetry; the machine/session source slice exists (S8 sealed edge
sessions, S9 recovery-gated publish); what does not exist is real OT / ROS2 bag / MCAP / Jetson or
production manufacturing input.

`README.ko.md` was checked for an equivalent sentence and has none — its first screen already
carried the correct boundary — so EN/KO claims are aligned without inventing a new Korean paragraph.

### 12.4 R4 — reproduction command and Airflow scope

Reproduction command, both languages:

```bash
pip install -r requirements.txt -r requirements-spark.txt
PYTHON_BIN=python ./scripts/verify_recovered_telemetry_publish.sh
```

`requirements.txt` is included because the Spark interpreter imports the base pipeline, which
imports `pymongo`. `requirements-kafka.txt` was **removed** from the reader command: verified in
`scripts/run_with_local_kafka.sh:70-72`, the helper creates `/tmp/manufacturing-mini-kafka-venv` and
installs the pinned Kafka client into it, so installing it into the reader's environment is noise.
Prerequisites named inline instead: Java 17+, `curl`, and network access for the first Kafka
download. The setup section was not expanded.

Airflow scope in both walkthroughs:

```text
Airflow, this S9 DAG path: DagBag / dags test wiring only
Airflow, earlier Spark/Iceberg skeleton: local standalone / LocalExecutor evidence exists
neither is production Airflow - no HA, no distributed executor, no deployed scheduler
```

### 12.5 Changed files

```text
M scripts/build_platform_portfolio_evidence.py          R1 field/label, R2 guard
M tests/test_portfolio_release.py                       R1 assertions, R2 two new tests (+ loader)
M docs/portfolio/platform-overview/evidence/runtime-evidence.json   regenerated (R1, R2 field)
M docs/portfolio/platform-overview/report.html                      regenerated (R1 label)
M docs/portfolio/platform-overview/assets/01-platform-overview.png  recaptured (R1 label)
M docs/portfolio/platform-overview/README.md                        R4 Airflow scope
M docs/portfolio/platform-overview/README.ko.md                     R4 Airflow scope
M README.md                                             R3 boundary, R4 command
M README.ko.md                                          R4 command
M PUBLICATION_CHECKLIST.md                              R1 wording
M VERIFICATION_LOG.md                                   revision entry
M this package                                          status + this summary
```

Screens 2 and 3 were regenerated identically (same bytes as before for screen 2's content and
screen 3), since neither renders the renamed field. Forbidden paths remain untouched: `src/**`,
`dags/**`, existing tests, existing verification scripts, `requirements*.txt`, accepted S7/S8/S9
documents, ROADMAP/DESIGN/progress maps, `docs/portfolio/kafka-k1-k1-5/**`, and `LICENSE`.

### 12.6 Verification

```text
builder regeneration from preserved raw S9 files -> temp dir
  runtime-evidence.json vs committed     byte-for-byte exact (cmp)
  report.html vs committed               byte-for-byte exact (cmp)

Python 3.10.12 (.venv)                   base 161 passed, 17 skipped
                                         portfolio 37 passed
Python 3.12.3 (fresh venv, requirements.txt only)
                                         base 161 passed, 17 skipped
                                         portfolio 37 passed

screenshots regenerated and opened:
  01  "GitHub Actions at evidence capture  not_yet_run"  (R1 visible on screen)
  02  partial [0,1] / complete [2,3,4], missing [3], blocked, none left behind
  03  7/7 quality, published -> skipped, snapshot 472417168912431048 exact, producer null
  none blank

git diff --check                         clean
```

Counts moved 159 -> 161 (base) and 35 -> 37 (portfolio); both deltas are the two R2 tests. Counts
are per interpreter and not summed.

### 12.7 Remaining Unknowns

```text
GitHub Actions has still never run from this environment. Codex owns the first post-push
  observation. Worth watching on that run: the setup-python pip cache keyed on requirements.txt,
  and whether the 17 optional skips behave the same on a clean GitHub runner.

The badge URL hard-codes junhyun-dev/manufacturing-data-platform-mini from `git remote -v`.
  A rename or transfer breaks it silently and no local test can catch that.

LICENSE remains absent - user legal decision, unchanged.

Playwright is required only to regenerate screenshots and is deliberately in no requirements file.

Byte-exact regeneration holds only on the same interpreter, because the document records the
  running Python and pyspark versions. On a different interpreter those two fields legitimately
  differ; the state transition and invariants do not.
```

### 12.8 git diff summary

```text
12 files touched in this revision (9 tracked-file modifications, 3 regenerated artifacts).
git diff --check: clean. Working tree left dirty and uncommitted, as required.
```

## 13. Codex Final Acceptance (2026-07-27)

Status: `accepted-closed`.

Codex independently reviewed the current diff, evidence document, rendered report, three PNGs,
reader-facing claims, publication boundary, and public CI scope. The accepted release preserves
`d8ec816` as the implementation source commit; no pipeline, DAG, Kafka, Spark/Iceberg, or Airflow
runtime behavior changed.

Independent local verification:

```text
Python 3.10.12 (.venv)                   161 passed, 17 skipped
Python 3.12.3 (fresh requirements-only)  161 passed, 17 skipped
portfolio contract tests                 37 passed
builder with the Spark interpreter       committed JSON and HTML reproduced byte-for-byte
three PNGs                               opened and visually inspected
base pipeline / operator report / EAV    all CLI paths succeeded
public path and secret scans             no reader-facing leak found
git diff --check                         clean
```

Public verification:

```text
release commit         c8164d0  Add portfolio release evidence and base CI
workflow update        8287da6  Update GitHub Actions to Node 24 runtimes
GitHub Actions run     30239955776
result                 Python 3.10 success, Python 3.12 success
URL                    https://github.com/junhyun-dev/manufacturing-data-platform-mini/actions/runs/30239955776
```

The first public run passed but reported GitHub's Node.js 20 deprecation warning for
`actions/checkout@v4` and `actions/setup-python@v5`. Those actions were updated to
`actions/checkout@v5` and `actions/setup-python@v6`; the accepted run above passed without that
warning.

Acceptance boundary:

- The public badge proves the base Python unit/contract suite only.
- Kafka, Spark/Iceberg, and Airflow runtime claims remain tied to documented local runbooks.
- The committed evidence remains historical and correctly records
  `github_actions_status_at_evidence_capture: not_yet_run`; the live badge and run URL own current
  CI status.
- Production, HA, distributed scale, throughput, exactly-once, real OT input, and concurrent
  Iceberg writer behavior remain unverified.
- `LICENSE` remains absent and was not changed by this release.
