# Industrial Telemetry Trust Report

> 실행 근거:
> [`evidence/runtime-evidence.json`](evidence/runtime-evidence.json) ·
> 화면: [`report.html`](report.html)

## 문제

센서 관측값이 저장됐다는 사실만으로 AI 학습 데이터나 분석용 trusted dataset에 포함할
수는 없다. 같은 source 범위라도 품질 상태가 나쁘거나 collector 중단으로 일부가
누락되면 서로 다른 판단이 필요하다.

이 walkthrough는 다음 질문에 답한다.

> 실제 산업 기록을 OPC UA로 replay해 수집했을 때, 어떤 evidence가 있어야 발행하고
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

| 같은 source 범위 | 관측 결과 | Operator action |
|---|---|---|
| 정상 | expected 9 / observed 9 / Good 9 | `PUBLISH` |
| 품질 이상 | expected 9 / observed 9 / Uncertain 1 / Bad 1 | `BLOCKED` |
| collector 중단 | expected 9 / observed 3 / missing 6 | `REPROCESS REQUIRED` |

정상과 허용 범위 안의 duplicate/out-of-order 입력은 같은 trusted dataset version으로
수렴한다. too-late, missing, quality failure는 current version을 전진시키지 않는다.

## Source와 provenance

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

accepted local runtime evidence와 원본 CSV가 있는 환경에서 다음을 실행한다.

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

## 한계

검증한 것은 actual historical source를 사용한 local bounded replay와 로컬 파일 기반
trusted version이다. 다음은 이 결과로 주장하지 않는다.

- physical PLC·sensor·plant network 또는 production OPC UA
- production security·HA·throughput·lateness SLA
- Kafka partition/rebalance 또는 Iceberg streaming sink
- cluster Spark state correctness와 end-to-end exactly-once
- automatic source correction 또는 실제 운영 시스템을 변경하는 Console action
- AI model 학습·평가 결과

이 화면은 읽기 전용 evidence artifact다. 버튼처럼 보이는 action 표시는 외부 시스템을
변경하지 않는 operator recommendation이다.
