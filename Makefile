PYTHON_VERSION ?= 3.10
PYTHON_BIN ?= .venv/bin/python

.PHONY: help setup test verify serve verify-service

help:
	@echo 'make setup  - install the pinned base + OPC UA environment into .venv'
	@echo 'make test   - run unit and contract tests (no Spark/Kafka/Airflow install)'
	@echo 'make verify - replay the fixture and retain decisions + trusted-data read-back'
	@echo 'make serve  - open Telemetry Review at http://127.0.0.1:8000'
	@echo 'make verify-service - check real HTTP, export read-back and restart persistence'

setup:
	@test -x .venv/bin/python || uv venv --python $(PYTHON_VERSION) .venv
	uv pip install --python .venv/bin/python -r requirements-dev.lock

test:
	$(PYTHON_BIN) -m pytest -q

verify:
	PYTHON_BIN="$(PYTHON_BIN)" bash scripts/verify_telemetry.sh

serve:
	PYTHONPATH=src $(PYTHON_BIN) -m uvicorn manufacturing_data_platform.file_review.app:create_app --factory --host 127.0.0.1 --port 8000 --limit-concurrency 16 --timeout-keep-alive 5

verify-service:
	$(PYTHON_BIN) scripts/verify_file_review.py
