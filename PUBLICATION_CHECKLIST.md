# Publication Checklist

This repo is intended to be safe for a public GitHub portfolio.

## Public-Safe Scope

- [x] Personal learning project.
- [x] Synthetic manufacturing-style data only.
- [x] No company code.
- [x] No customer data.
- [x] No private business logic.
- [x] No credentials or secrets are required to run tests.
- [x] Runtime MongoDB and production Airflow deployment gaps are documented as blockers/backlog.

## Checked Before Initial Publication

Commands:

```bash
git ls-files | rg -v "^(PUBLICATION_CHECKLIST.md|VERIFICATION_LOG.md)$" | xargs rg -n -i "(api[_-]?key|access[_-]?key|secret|token|password|passwd|private[_-]?key|mongodb\\+srv|Bearer |AKIA|BEGIN RSA|BEGIN OPENSSH|client_secret|refresh_token)"
git ls-files | rg -v "^(PUBLICATION_CHECKLIST.md|VERIFICATION_LOG.md)$" | xargs rg -n -i "(personal path|private email|private company name|customer name|internal path)"
pytest
PYTHONPATH=src python -m manufacturing_data_platform.pipeline.run --catalog-backend json --output-dir /tmp/manufacturing-mini-publication-cli
PYTHONPATH=src python -m manufacturing_data_platform.pipeline.operator_report --output-dir /tmp/manufacturing-mini-publication-cli --business-date 2026-06-29
PYTHONPATH=src python -m manufacturing_data_platform.pipeline.run_eav --catalog-backend json --output-dir /tmp/manufacturing-mini-publication-eav-cli
```

Expected:

- Secret scan returns no sensitive repo content.
- Personal path/name scan returns no public-facing leakage.
- Tests pass.
- JSON CLI path succeeds.
- Operator evidence report CLI path succeeds.
- EAV JSON CLI path succeeds.

## Portfolio Release (2026-07-23)

Added for the public portfolio release. Re-run these before any release commit.

Commands:

```bash
# base suite, matching the public CI job (requirements.txt only)
PYTHONPATH=src python -m pytest -q

# committed portfolio evidence contract
PYTHONPATH=src python -m pytest -q tests/test_portfolio_release.py

# regenerate runtime evidence, report, and screens from a clean run
PYTHON_BIN=python ./scripts/verify_recovered_telemetry_publish.sh
python scripts/build_platform_portfolio_evidence.py --source-commit <commit> --verified-on <date>
python scripts/capture_platform_portfolio.py

# private path scan for reader-facing release files
grep -rn "/home/" README.md README.ko.md docs/portfolio/ .github/

git diff --check
```

Expected:

- [x] Base suite passes on Python 3.10 and 3.12 with `requirements.txt` only.
- [x] `tests/test_portfolio_release.py` passes: evidence JSON parses, names the accepted source
      commit, records the partial-blocked -> complete -> published -> skipped transition, keeps the
      snapshot relations and same-snapshot invariant, and lists verified/not-verified boundaries.
- [x] `report.html` embeds exactly the committed `evidence/runtime-evidence.json`; the three PNGs
      are browser captures of that report, not hand-authored images.
- [x] Root READMEs expose the CI badge, diagram, walkthrough link, runtime-evidence link, both
      commands, and the claim boundary in the first screen, in both languages.
- [x] No `/home/...` path, credential, customer identifier, or internal URL in reader-facing files.
      Generic `/tmp/...` reproduction paths are allowed.
- [x] No runtime warehouse, Kafka archive, jar, database, or local venv is committed.

Release-specific claim rules:

- The CI badge proves the **base unit/contract suite only**. Never describe it as proving Kafka,
  Spark/Iceberg, or Airflow runtime.
- Until the workflow has actually been observed on a pushed commit, do not describe the release as
  public-CI verified.
- The committed evidence records `github_actions_status_at_evidence_capture`, which is **historical**
  — it states the workflow state when the evidence was captured and stays valid afterwards. The live
  badge in the READMEs is the current signal. Never add a current-status field to the evidence
  document: it would go stale the moment the workflow first runs, and the screenshots are permanent.
- `LICENSE` is absent. That is a user legal decision and is intentionally left unchanged here.

## Not Public

The following should not be published as part of this repo:

- Personal mission documents.
- Resume/application materials.
- Job tracking databases or scraping tools.
- Company reference code or internal paths.
- Generated lakehouse outputs under `data/lakehouse/`.
