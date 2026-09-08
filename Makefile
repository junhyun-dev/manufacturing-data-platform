PYTHON_VERSION ?= 3.10
PYTHON_BIN ?= .venv/bin/python

.PHONY: help setup test verify

help:
	@echo 'make setup  - install the pinned base + OPC UA environment into .venv'
	@echo 'make test   - run unit and contract tests (no Spark/Kafka/Airflow install)'
	@echo 'make verify - replay the fixture and retain decisions + trusted-data read-back'

setup:
	@test -x .venv/bin/python || uv venv --python $(PYTHON_VERSION) .venv
	uv pip install --python .venv/bin/python -r requirements-dev.lock

test:
	$(PYTHON_BIN) -m pytest -q

verify:
	PYTHON_BIN="$(PYTHON_BIN)" bash scripts/verify_telemetry.sh
