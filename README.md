# 제조 설비 데이터는 언제 믿을 수 있는가?

[![Base unit and contract tests](https://github.com/junhyun-dev/manufacturing-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/junhyun-dev/manufacturing-data-platform/actions/workflows/ci.yml)

실제 산업 기록을 센서처럼 수집하고, 값의 의미·시간·품질·완전성을 검증한 뒤
**trusted dataset으로 발행할지, 차단할지, 재처리할지 결정하는** 로컬·bounded 데이터
플랫폼 프로젝트입니다.

주 사용자는 telemetry 수집 결과를 downstream 분석·ML에 공개할 책임이 있는 제조 데이터
플랫폼 운영자입니다. 분석가와 ML 엔지니어는 운영자가 공개한 trusted dataset의 소비자입니다.

> 대표 결과: [Industrial Telemetry Trust Report](docs/portfolio/industrial-telemetry-trust/README.md) ·
> [정적 HTML](docs/portfolio/industrial-telemetry-trust/report.html) ·
> [runtime evidence JSON](docs/portfolio/industrial-telemetry-trust/evidence/runtime-evidence.json)

![정상·품질 이상·collector 중단 판정 비교](docs/portfolio/industrial-telemetry-trust/assets/01-operator-decisions.png)

## 한눈에 보는 결과

같은 MetroPT-3 source 범위를 세 가지 방식으로 수집해 서로 다른 다음 행동을 냅니다.

| 상황 | 관측 결과 | 판정 | 다음 행동 |
|---|---|---|---|
| 정상 수집 | expected 9 / observed 9 / Good 9 | `complete` | `PUBLISH` |
| 품질 이상 | expected 9 / observed 9 / Uncertain 1 / Bad 1 | `blocked_quality` | `BLOCKED` |
| collector 중단 | expected 9 / observed 3 / missing 6 | `incomplete` | `REPROCESS REQUIRED` |

중복·역순 입력은 허용 범위 안에서 정상 입력과 같은 dataset version으로 수렴합니다.
too-late·missing·quality failure는 기존 trusted current를 전진시키지 않습니다.

```mermaid
flowchart LR
  source["MetroPT-3<br/>실제 historical record"]
  opcua["Local OPC UA server<br/>tag replay"]
  collector["Subscription collector<br/>value · unit · time · status"]
  spool["Durable local spool<br/>expected / observed"]
  trust{"Trust decision<br/>quality · gap · event time"}
  current["Versioned trusted JSONL<br/>manifest · current"]
  blocked["Blocked / incomplete<br/>reprocess evidence"]
  report["Industrial Telemetry<br/>Trust Report"]

  source --> opcua --> collector --> spool --> trust
  trust -- publish --> current --> report
  trust -- refuse --> blocked --> report
```

## 어떤 데이터를 사용하는가

[UCI MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt%203%20dataset)는 지하철
공기압축기에서 수집된 압력·온도·전류·밸브 계열 기록입니다. 전체 배포 CSV의
1,516,948개 행과 SHA-256을 검증하고, 재현 가능한 데모에서는 첫 3개 physical row의
다음 tag를 선택합니다.

- `TP2`: 압력, `bar`
- `Oil_temperature`: 오일 온도, `°C`
- `Motor_current`: 모터 전류, `A`

따라서 한 collection의 기대 관측 집합은 `3 rows × 3 tags = 9 observations`입니다.
저장소에는 CC BY 4.0 출처를 명시한 [3-row fixture](tests/fixtures/metropt3/README.md)만
포함하며, 전체 CSV는 커밋하지 않습니다.

## 실제와 simulation의 경계

이 프로젝트에서 세 가지를 분리합니다.

```text
actual record
  공개 MetroPT-3 historical value

replay simulation
  local OPC UA server가 historical row를 DataValue로 재생

fault injection
  quality 시나리오의 Uncertain/Bad StatusCode와 collector 중단
```

즉 센서값을 임의로 만든 데모는 아니지만, 실제 공장 네트워크나 현재 동작 중인 설비에
연결한 것도 아닙니다.

## 수집 단계에서 보존하는 것

`industrial_telemetry_v1`은 다음 정보를 한 관측값의 계약으로 묶습니다.

- equipment ID, tag ID, OPC UA NodeId
- value와 engineering unit
- 원본 historical timestamp
- OPC UA source timestamp와 server timestamp
- collector가 기록한 collection time
- Good·Uncertain·Bad StatusCode
- mapping version과 source file identity
- actual record·replay·fault injection provenance

OPC UA subscription은 값이 같아도 timestamp가 바뀐 관측을 보존하도록
`StatusValueTimestamp` trigger를 사용합니다. 수집 완전성은 추정 cadence가 아니라 봉인된
expected event identity 집합과 실제 observed 집합을 비교해 판단합니다.

## 이벤트 시간과 trusted dataset

수집된 canonical telemetry에 별도 arrival envelope를 씌워 다음을 검증합니다.

| 입력 | Accepted | 핵심 evidence | 판정 |
|---|---:|---|---|
| in order | 9 | exact expected set | `publishable` |
| duplicate + out of order | 9 | duplicate 1, out of order 3 | `publishable` |
| too late | 6 | too late 3, missing 3 | `reprocess_required` |
| missing | 8 | missing 1 | `incomplete` |
| quality failure | 9 | Uncertain 1, Bad 1 | `blocked_quality` |

정상과 허용 범위 내 disorder는 같은 content-addressed dataset version으로 수렴합니다.
trusted 결과는 JSONL, manifest, `current_trusted.json`으로 구성되며 새 발행 전 기존
`current → manifest → data` digest chain을 다시 검증합니다. 기존 current가 손상되거나
symlink로 바뀌면 조용히 교체하지 않고 immutable integrity failure를 남깁니다.

로컬 Spark 3.5.8 file micro-batch에서도 watermark, deduplication, checkpoint restart 후
accepted event identity가 engine-independent 결과와 일치하는지 확인했습니다. 이 결과는
Kafka source나 Iceberg streaming sink를 검증한 것이 아닙니다.

## 실행

### Base CI와 같은 테스트

```bash
python -m pip install -r requirements.txt
PYTHONPATH=src python -m pytest -q
```

GitHub Actions badge는 이 base suite만 증명합니다. OPC UA, Spark, Kafka, Iceberg,
Airflow runtime은 optional dependency와 별도 로컬 runbook으로 검증합니다.

### OPC UA source contract

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-opcua.txt
PYTHON_BIN=.venv/bin/python ./scripts/verify_industrial_source_contract.sh
```

이 command는 공개 3-row fixture를 local OPC UA server에서 replay하고 normal·quality·
interrupted collection을 검증한 뒤 임시 output을 제거합니다.

### Event-time trust와 local Spark parity

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-event-time.txt
./scripts/verify_event_time_trust.sh
```

### Trust Report 재생성

전체 MetroPT CSV와 accepted local runtime evidence가 `.cache/`에 있는 authoring 환경에서:

```bash
python3 scripts/build_industrial_trust_report.py \
  --baseline-commit 36e7344 \
  --verified-on 2026-07-31
python3 scripts/capture_industrial_trust_report.py
```

Builder는 source checksum·row count, collection report/spool/seal/last-good,
event-time report, trusted current/manifest/data를 교차 검증합니다. HTML은 committed
evidence JSON과 동일한 document를 embed하고 그 값만 렌더링합니다.

## 공개 evidence

| 확인하려는 것 | Evidence |
|---|---|
| 세 operator 판정과 화면 | [Trust Report walkthrough](docs/portfolio/industrial-telemetry-trust/README.md) |
| 실제 source·OPC UA replay·fault 구분 | [source provenance 화면](docs/portfolio/industrial-telemetry-trust/assets/02-source-provenance.png) |
| duplicate·late·missing·trusted current | [event-time 화면](docs/portfolio/industrial-telemetry-trust/assets/03-event-time-trust.png) |
| 화면이 읽는 authoritative 값 | [runtime-evidence.json](docs/portfolio/industrial-telemetry-trust/evidence/runtime-evidence.json) |
| 실행·검증 범위 | [Verification](docs/VERIFICATION.md) |

## Historical Evidence — 기존 v1

현재 제품의 Golden Flow는 위 industrial telemetry trust 경로입니다. 그 이전에는 synthetic
machine event를 대상으로 다음 복구 원리를 검증했습니다.

```text
sealed edge spool
→ local Kafka landing
→ complete + exact-set recovery gate
→ Spark quality
→ local Iceberg publish
```

부분 복구는 Spark/Iceberg state를 만들기 전에 거부되고, 같은 source 재실행은 새 snapshot을
만들지 않습니다. 이 경로는 현재 제품에 연결된 Extension이 아니라 검증된
[Historical Evidence](docs/HISTORICAL-EVIDENCE.md)입니다. 새로운 continuous pipeline 요구가
생기면 현재 telemetry contract에서 다시 설계하며, 두 경로가 연결돼 있다고 주장하지 않습니다.

## 주장 경계

현재 증거로 말할 수 있는 것:

- 실제 공개 산업 기록의 checksum을 검증하고 local OPC UA subscription으로 replay했다.
- tag·단위·source/server/collection time·quality·mapping·source identity를 보존했다.
- 정상·품질 이상·collector 중단의 expected/observed coverage와 operator action을 구분했다.
- duplicate·out-of-order·too-late·missing·quality failure를 local bounded 정책으로 판정했다.
- local Spark file micro-batch의 watermark/dedup/checkpoint identity parity를 확인했다.
- content-addressed local trusted dataset과 current integrity refusal을 구현했다.

현재 증거로 말하지 않는 것:

- physical PLC·sensor·실제 plant network 또는 production OPC UA 운영 경험
- continuous Kafka→Spark→Iceberg telemetry streaming
- production lateness SLA, HA, throughput, cluster Spark correctness
- multi-partition Kafka rebalance, distributed transaction, end-to-end exactly-once
- 자동 historical correction, 실제 control-plane action 또는 AI model 결과

이 저장소는 개인 포트폴리오이며 회사 코드·고객 데이터·내부 schema를 포함하지 않습니다.

## 더 보기

- [현재 Architecture와 Golden Flow](docs/ARCHITECTURE.md)
- [검증 환경·명령·evidence 경계](docs/VERIFICATION.md)
- [기존 v1 Historical Evidence](docs/HISTORICAL-EVIDENCE.md)
