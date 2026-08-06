# Verification — 무엇을 어디까지 증명했는가

## 검증 환경을 숫자와 함께 읽는 법

같은 source tree라도 optional dependency에 따라 pytest collection 수가 다르다.

| 환경 | 설치 범위 | 2026-08-06 collection | 의미 |
|---|---|---:|---|
| base / CI형 | `requirements.txt` | 185 | optional OPC UA·Spark runtime test 일부는 module skip |
| local OPC UA env | base + `requirements-opcua.txt`가 설치된 `.venv` | 213 | industrial source contract test까지 collection |

따라서 `213 tests`처럼 환경이 없는 숫자를 프로젝트 전체 검증 수치로 사용하지 않는다. GitHub Actions
badge는 workflow가 실제 설치·실행한 범위만 증명한다.

## 현재 제품 evidence

| 질문 | 자동 evidence | bounded runtime evidence | visible evidence |
|---|---|---|---|
| actual record와 replay/fault를 구분하는가 | source·provenance contract tests | local OPC UA replay | source provenance 화면 |
| collection이 완전한가 | expected/observed/seal tests | normal·quality·interrupted run | operator decision 화면 |
| duplicate·late·missing을 구분하는가 | event-time policy tests | bounded verification run | event-time trust 화면 |
| 실패가 last-good을 전진시키지 않는가 | integrity·rerun tests | content-addressed current evidence | runtime evidence JSON |
| 화면이 임의 숫자를 만들지 않는가 | report builder contract test | accepted evidence hash 교차 검증 | static HTML·PNG |

대표 공개 결과:

- [Trust Report walkthrough](portfolio/industrial-telemetry-trust/README.md)
- [Static report](portfolio/industrial-telemetry-trust/report.html)
- [Authoritative runtime evidence](portfolio/industrial-telemetry-trust/evidence/runtime-evidence.json)

## 재현 명령

### Base suite

```bash
python -m pip install -r requirements.txt
PYTHONPATH=src python -m pytest -q
```

### OPC UA source contract

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-opcua.txt
PYTHON_BIN=.venv/bin/python ./scripts/verify_industrial_source_contract.sh
```

### Event-time trust와 Spark parity

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-event-time.txt
./scripts/verify_event_time_trust.sh
```

### Committed report contract

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_industrial_source_contract.py \
  tests/test_event_time_trust.py \
  tests/test_industrial_trust_report.py
```

## 증거 사다리

| 수준 | 현재 상태 | 말할 수 있는 것 |
|---|---|---|
| source/code contract | PASS | observation·identity·quality·coverage·manifest 규칙 구현 |
| local bounded runtime | PASS | public record를 local OPC UA로 replay하고 실패 시나리오 재현 |
| local Spark parity | PASS | file micro-batch의 accepted identity가 engine-independent 판정과 일치 |
| visible product result | PASS | 정상·품질 이상·중단을 같은 report에서 비교 |
| physical plant integration | NOT_VERIFIED | 실제 PLC·sensor·plant network 경험으로 주장 금지 |
| production operation | NOT_VERIFIED | HA·throughput·SLA·on-call·cluster correctness 주장 금지 |
| external user validation | NOT_VERIFIED | 실제 제조 운영자의 반복 사용·피드백 없음 |

상세 실행 이력과 private audit trail은 private canonical의 `VERIFICATION_LOG.md`와 accepted Slice가
소유하며 public reader 문서에 mutable 상태를 복제하지 않는다.
