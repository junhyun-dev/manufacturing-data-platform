# Industrial Telemetry Trust Report

> 실행 근거:
> [`evidence/runtime-evidence.json`](evidence/runtime-evidence.json) ·
> 화면: [`report.html`](report.html)

## 문제

센서 관측값이 저장됐다는 사실만으로 AI 학습 데이터나 분석용 trusted dataset에 포함할
수는 없다. 같은 source 범위라도 품질 상태가 나쁘거나 collector 중단으로 일부가
누락되면 서로 다른 판단이 필요하다.

이 문서는 다음 질문에 답한다.

> 실제 산업 기록을 OPC UA로 replay해 수집했을 때, 어떤 실행 근거가 있어야 발행하고
> 어떤 경우에 차단하거나 재처리해야 하는가?

## 구현 흐름

```text
checksum-verified MetroPT-3 historical CSV
→ local OPC UA replay server
→ subscription collector
→ industrial_telemetry_v1 + durable local spool
→ collection completeness/quality report
→ bounded event-time classification + local Spark parity
→ content-addressed trusted JSONL/manifest/current
→ normalized public evidence JSON
→ static Trust Report + browser screenshot
```

## 대표 판단

| 같은 source 범위 | 관측 결과 | 운영자 조치 |
|---|---|---|
| 정상 | expected 9 / observed 9 / Good 9 | `PUBLISH` |
| 품질 이상 | expected 9 / observed 9 / Uncertain 1 / Bad 1 | `BLOCKED` |
| collector 중단 | expected 9 / observed 3 / missing 6 | `REPROCESS REQUIRED` |

정상과 허용 범위 안의 duplicate/out-of-order 입력은 같은 trusted dataset version으로
수렴한다. too-late, missing, quality failure는 current version을 전진시키지 않는다.

## 데이터 출처와 재현 방식

- 데이터: UCI MetroPT-3, 지하철 공기압축기 historical record
- 전체 원본 identity: 1,516,948행과 SHA-256을 build 시 다시 계산
- bounded demo: physical row 1·2·3 × `TP2`, `Oil_temperature`, `Motor_current`
- 산업 인터페이스: local OPC UA subscription
- preserved semantics: equipment, tag, engineering unit, source/server/collection time,
  StatusCode, mapping version
- fault injection: quality scenario에만 Uncertain 1개와 Bad 1개

`actual record`는 공개된 실제 과거 관측값을 뜻한다. `local OPC UA replay`와
`fault injection`은 이 프로젝트가 만든 simulation이며 live plant 연결이 아니다.

## 재현

승인된 로컬 실행 근거와 원본 CSV가 있는 환경에서 다음을 실행한다.

```bash
python3 scripts/build_industrial_trust_report.py \
  --baseline-commit 36e7344 \
  --verified-on 2026-07-31

python3 scripts/capture_industrial_trust_report.py
```

Builder는 runtime report·spool·last-good·trusted current/manifest/data와 원본 CSV
checksum을 교차 검증한다. 값이 없거나 source 범위가 다르면 기존 public artifact를
성공 결과처럼 다시 만들지 않는다.

## 화면

- [`01-operator-decisions.png`](assets/01-operator-decisions.png):
  같은 source에서 세 가지 operator action 비교
- [`02-source-provenance.png`](assets/02-source-provenance.png):
  actual record·OPC UA replay·fault injection과 tag/time/unit
- [`03-event-time-trust.png`](assets/03-event-time-trust.png):
  event-time stress, trusted current, claim boundary

화면의 숫자는 손으로 다시 적지 않는다. `report.html`은 committed
`runtime-evidence.json`과 동일한 JSON document를 embed하고 그 값만 렌더링한다.

## 계약과 독립 검토

화면의 수치를 실행 근거에서만 가져오는 것이 이 보고서의 핵심 계약이다. 계약이 실제로
지켜지는지는 구현과 분리된 독립 검토로 확인했다.

| 단계 | 결과 |
|---|---|
| 계약 | 판정 사유의 모든 수치는 validated projection의 observed·quality·missing count에서만 유도한다 |
| 후보 구현(candidate) | Codex가 report builder와 contract test를 구현해 candidate로 제출했다 |
| 1차 독립 검토(independent review) | `REVISE` — metric은 projection에서 오지만 판정 사유의 수치는 문장에 다시 적혀 있었다 |
| 수정 | 판정 사유를 projection count에서 생성하고, 대표 범위의 exact cardinality와 fault 구성을 build 시 강제했다 |
| 2차 독립 검토 | `ACCEPT` — 변형 입력 회귀 테스트, artifact identity, 검증 범위를 다시 확인했다 |

1차 검토가 찾은 것은 화면의 값이 틀렸다는 것이 아니라, **입력이 바뀌면 틀린 설명이 통과할 수
있다**는 것이었다. 당시 값은 모두 일치했지만, 합계만 맞춘 변형(quality Good 6 / Uncertain 2 /
Bad 1, interrupted observed 6 / missing 3, normal expected 6 / observed 6)이 당시 build를 통과할
수 있었고, 그 경우 판정 사유에는 이전 수치가 그대로 남는다.

수정은 두 문제를 함께 해결했다.

- 판정 사유는 projection의 observed count, Uncertain/Bad count, missing count에서 문장을
  생성한다. 수치를 문자열에 중복 기입하지 않는다.
- build는 `expected == selected rows × selected tags`, quality의 Uncertain 1 / Bad 1,
  interrupted의 selected row 한 개 관측과 나머지 전량 missing을 강제하고, selected
  rows·tags의 duplicate를 거부한다.

두 경계는 [`tests/test_industrial_trust_report.py`](../../../tests/test_industrial_trust_report.py)의
변형 입력 회귀 테스트로 보호된다. 수정 뒤에도 `runtime-evidence.json`, `report.html`, 세 PNG는
수정 전과 byte 단위로 동일했다. 이 수정은 공개된 값을 바꾸지 않고, 앞으로 입력이 바뀌었을 때
낡은 설명이 통과하는 경로만 막는다.

Codex가 후보 구현(candidate)을 작성했고, 별도의 독립 검토(independent review)에서 계약 위반을
발견했다. 사용자가 수정 범위와 최종 수용 여부를 결정했다. 공개 근거만으로 검토 도구를 특정할 수
없어 이름을 쓰지 않으며, AI가 설계·검증 책임을 대신했다고 주장하지 않는다.

## 한계

이 프로젝트는 공개된 실제 과거 기록(actual historical source)을 로컬에서 범위를 한정해
replay하고, 로컬 파일 기반 trusted version을 만드는 데까지 검증했다. 다음 항목은 아직
검증하지 않았다.

- physical PLC·sensor·plant network 또는 production OPC UA
- production security·HA·throughput·lateness SLA
- Kafka partition/rebalance 또는 Iceberg streaming sink
- cluster Spark state correctness와 end-to-end exactly-once
- automatic source correction 또는 실제 운영 시스템을 변경하는 Console action
- AI model 학습·평가 결과

이 화면은 실행 근거를 보여주는 읽기 전용 산출물이다. 버튼처럼 보이는 조치 표시는 외부
시스템을 변경하지 않고 운영자에게 다음 행동만 제안한다.
