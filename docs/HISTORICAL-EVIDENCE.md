# Historical Evidence — synthetic manufacturing v1

## 현재 제품과의 관계

현재 제품은 [industrial telemetry trust Golden Flow](ARCHITECTURE.md)다. 아래 v1은 현재
runtime에 연결된 Extension이 아니라, 이전에 local·bounded 범위에서 검증한 복구·품질·재실행
원리의 Historical Evidence다.

```text
synthetic machine event
→ sealed edge spool
→ local Kafka landing
→ complete + exact-set recovery gate
→ Spark quality
→ local Iceberg publish
```

## 검증했던 것

- landing 뒤 offset commit 전 crash에서 duplicate를 늘리지 않는 bounded recovery
- incomplete edge recovery를 downstream publish 전에 차단
- deterministic batch bridge와 provenance 보존
- Spark quality gate 뒤 local Iceberg partition overwrite
- 같은 source 재실행에서 새 snapshot을 만들지 않는 idempotent behavior
- local Airflow wrapper가 동일한 CLI/Spark entrypoint를 trigger하는 경계

## 현재 주장하지 않는 것

- v1 machine event와 v2 telemetry observation이 하나의 production pipeline으로 연결됨
- continuous Kafka→Spark→Iceberg streaming
- multi-partition rebalance, distributed exactly-once, cluster HA
- production Airflow·Spark·Kafka·Iceberg 운영 경험
- 현재 서비스 사용자가 v1 경로를 사용함

## 보존 위치

- accepted baseline: Git commit `36e7344`
- 상세 실행 기록: private canonical `VERIFICATION_LOG.md`
- 당시 public walkthrough: `docs/portfolio/platform-overview/`, `docs/portfolio/kafka-k1-k1-5/`
- source와 tests: 현재 requalification Slice에서는 변경하지 않음

새 streaming·lakehouse 압력이 생기면 v1을 자동 재활성화하지 않는다. 현재 telemetry identity와
운영자 판정 흐름에서 다시 Product/Technical Discovery를 수행하고, 재사용 가능한 계약만 선택한다.
