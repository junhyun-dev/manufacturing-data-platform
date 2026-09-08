# Manufacturing backlog

확인한 근거 공백에 따라 순서를 정한다. 모든 항목을 구현하겠다는 약속은 아니다.
현재 선택한 작업은 [PROJECT_STATUS](../PROJECT_STATUS.md) 한 곳, 각 작업의 범위와 완료 조건은 이 파일이 소유한다.
새 제품 의미와 외부 행동의 최종 결정자는 프로젝트 작성자다.

## MFG-08 — Product value and source reality

**2026-09-08 외부 조사·원본 점검 완료 / 제품 가설은 미수용.** 현재 구현은 로컬 품질·발행 검증이다.
첫 사용자, 기존 업무의 비용, 반복 사용, 기존 대안보다 나은 결과는 확인하지 못했다. 실제 담당자·운영 데이터에
접근할 통로도 아직 확인되지 않았다. 아래 공개 데이터 검증안을 출발점으로 삼되 실제 사용자 검증과 구분한다.

### 검증할 제품 가설

설비 기록을 분석가에게 제공하는 데이터 담당자가 **요청받은 시간 구간을 전달해도 되는지 확인하고,
누락·정정 후 같은 분석 결과를 다시 전달하는 작은 데이터 제품**을 후보로 둔다. 소비자의 첫 질문은
“선택한 시간 구간의 압력·온도·전류 요약은 어떤 원본과 관측 범위를 사용했고, 다시 계산할 필요가 있는가?”다.
현재 `PUBLISH/BLOCKED/REPROCESS REQUIRED`에 분석 결과와 실제 복구 행동을 연결하는 방향이다.

이 가설의 수용 전에는 범용 historian, 제조 KPI 서비스, 예지보전 모델로 범위를 늘리지 않는다.
실제 첫 사용자는 연구용 데이터를 다루는 분석가일 수도 있다. 그런 검증을 공장 운영자의 수용으로 바꾸지 않는다.

### 외부 근거와 설계에 주는 영향

2026-09-08 원문 확인. 제품 문서는 대안의 기능 근거이며 이 프로젝트의 시장 수요를 입증하지 않는다.

| 근거 | 확인한 사실 | 이 프로젝트에서 검증할 것 |
|---|---|---|
| [Ignition 8.3 격리 데이터 처리](https://docs.inductiveautomation.com/docs/8.3/platform/store-and-forward/controlling-quarantine-data) | 실패 데이터의 격리, 원인 수정 뒤 retry, export/import를 이미 제공 | 차단 표시만으로 복구 업무를 해결했다고 하지 않는다. 사용자가 원인을 확인하고 실제로 복구하는 단계가 필요 |
| [AWS SiteWise late data와 quality](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/expression-tutorials.html) | 과거 구간의 metric을 다시 계산해 대체하며 소비자도 변경을 반영해야 함. 계산에 Good quality를 사용 | 기존 제품에도 품질·정정 기능이 있다. 추가 가치 후보는 선택한 source 범위·분석 결과·정정 이유를 함께 전달하는 사용 흐름 |
| [SiteWise 구간 집계](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/aggregates.html) | 구간별 기본 집계와 quality 필터 제공 | 그래프·평균을 추가하는 것만으로 차별성을 주장하지 않는다 |
| [Ignition 사용자 질문, 2026-03-26](https://forum.inductiveautomation.com/t/store-and-forward-quarantined-data/114695) | 사용자가 retry 뒤에도 격리가 반복되어 데이터 손실 여부를 물었고, 답변자는 duplicate key 가능성을 설명 | 중복과 수정의 구분, 재시도 후 결과 확인을 인터뷰·실험 질문으로 삼는다. 원인이 독립 검증된 장애 사례나 시장 규모 근거는 아님 |
| [UCI MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt%203%20dataset) | 실제 열차 압축기 기록, CC BY 4.0. 설명에 1Hz와 0.1Hz가 병존하며 row별 고장 label은 없음 | source 파일·간격을 직접 확인한다. OPC UA quality는 replay 시나리오의 값이며 원본의 센서 품질 측정값이 아님 |
| [MetroPT 연구 논문](https://www.nature.com/articles/s41597-022-01877-3) | 논문 Data Records는 2022년·20변수·다른 배포본을 설명 | 현재 2020년 MetroPT-3에 논문의 cadence·고장 구간·평가 결과를 그대로 옮기지 않는다 |

### 원본 파일을 직접 확인한 결과

UCI archive를 새로 받아 CSV SHA-256
`db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`를 확인했다.
CSV 1,516,948행을 physical order대로 읽고 timezone을 부여하지 않은 timestamp 차이를 계산했다.

- 첫/마지막 시각: `2020-02-01 00:00:00` / `2020-09-01 03:59:50`.
- 인접 간격 1,516,947개 중 10초는 1,337,521개, 9초는 128,277개. 60초 초과는 331개다.
- 최대 간격은 `2020-04-25 01:10:51 → 2020-04-27 01:12:49`, 172,918초다.
  이 원본에서 시간 역전·동일 timestamp의 인접 행은 없었다.
- 선택한 세 tag의 값은 모두 유한한 숫자였지만 이것은 센서 정확도나 OPC UA Good quality의 증거가 아니다.

따라서 **파일의 선택 행을 모두 전달했다는 완전성**과 **현실의 설비를 빠짐없이 관측했다는 완전성**을
구분해야 한다. 긴 간격이 운휴·수집 중단·공개용 추출 중 무엇 때문인지는 모른다. 10초 고정 cadence로
결측률·가동률을 계산하거나 간격을 보간해 실제 관측처럼 다루지 않는다. 원본 CSV를 다시 읽는 것으로
CSV에 없는 현실의 관측을 복구할 수는 없다. 이 점검은 파이프라인 처리량 실험이 아니다.

재현은 [source 조사 명령](VERIFICATION.md#source-and-consumer-research-probes), 현재 로컬 상세 결과는
`.cache/source-research/metropt3-profile.json`이다. 생성 파일은 checkout의 선행조건이 아니다.

### 더 단순한 대안과 비교

| 대안 | 먼저 비교할 이유 | 선택을 바꿀 조건 |
|---|---|---|
| CSV + SQL + expected set·unique·quality 검사 | 작은 고정 파일의 분석과 기본 거부는 이 조합으로 가능 | 이것으로 사용자의 반복 업무가 충분히 해결되면 얇은 실행 도구로 유지 |
| 기존 historian / SiteWise의 질의·복구 기능 | 수집·격리·집계·정정을 이미 제공하는 실제 대안 | 사용자 환경에서 기존 기능을 연결하는 편이 낫다면 재사용. 새 플랫폼 구축을 목적화하지 않음 |
| 현재 trust 구현 + 소비자 결과 + 범위 복구 | 기존 source·발행 검증을 실제 전달 업무에 사용할 후보 | 사용자가 버전·누락 범위·복구 결과 확인에 반복적인 어려움을 겪는지 먼저 확인 |

독립적인 SQLite 3.45.1 실험에서 첫 세 `Oil_temperature` 값의 sample mean은 소수 셋째 자리 기준
`53.625°C`였다. 가운데 관측을 빼면 `53.600°C`, 가운데 행을 중복하면 `53.638°C`가 된다.
Uncertain으로 바꿔도 숫자는 `53.625°C` 그대로다. expected set·unique·quality 검사를 더한 기준선은
세 변형을 모두 거부했다. 중복은 보수적으로 거부했으며 현재 엔진의 dedup·발행·복구 동등성을 검증한 것은 아니다.
숫자는 실제 기록이고 누락·중복·quality 변형은 실험 주입이다. 운영 효율이나 장비 건강에 대한 결과도 아니다.
`.cache/source-research/consumer-baseline.json`과 위 재현 명령에 경계를 남겼다.

### 사용자 검증과 중단 조건

1. 담당자에게 최근 실제 사례 한 건을 확인한다: 어떤 분석 결과를 기다렸는지, 누락·정정을 어떻게 알았는지,
   현재 도구와 수작업은 무엇인지, 잘못 전달하면 어떤 일이 생기는지. 기능 선호보다 기존 행동을 확인한다.
2. 같은 입력·정상/불완전/복구 시나리오로 단순 기준선과 제품 후보를 비교한다. 작성자의 설명 없이 올바른
   구간·버전을 고르는지, 걸린 시간·도움 요청·잘못된 선택을 기록한다. 절감률 목표나 사용자 성과를 미리 만들지 않는다.
3. 다음 구간에서도 다시 사용하고 싶은 이유와 걸림돌을 받는다. 외부 개발자의 재현 성공은 기술 검증,
   실제 업무 담당자의 반복 사용은 제품 가치 검증으로 각각 기록한다. 현재 둘 다 미실행이다.

첫 외부 검증 후보는 데이터 엔지니어/분석가 1명, 접근 가능하면 제조·설비 담당자 1명이다.
이는 조사 제안이며 메시지 발송이나 참여 수락이 아니다. 접근할 사람이 없으면 공개 데이터·독립 SQL 실험을
계속할 수 있지만 실사용 검증을 통과한 것으로 처리하지 않는다. 첫 usable version 뒤에도 실제 업무와 기존 대안의
빈틈을 찾지 못하면 범위를 로컬 품질·발행 도구로 유지한다. 제품 필요가 없는 기능 추가로 이를 보상하지 않는다.

**다음 제품 gate:** 이 질문과 입력 범위를 작성자가 수용하면 MFG-01의 소비자 계약 하나로 좁힌다.
MFG-07은 외부 재현·release의 신뢰성 선행조건이다. 이후 MFG-02의 복구, MFG-03의 재현 가능한 결과,
MFG-09의 독립 사용·운영 피드백을 한 번의 사용 흐름으로 연결한다. MFG-04의 규모와 MFG-06의 Spark는
그 사용 흐름에 필요한 경우에 선택한다.

## MFG-00 — Reproducible local entry

**로컬 정비 완료, 알려진 재현성 공백은 MFG-07.** 새 작업자가 특정 대화·private 파일 없이 설치하고,
저장소의 source를 재생해 판정과 저장 결과를 확인한 뒤 다음 작업을 찾을 수 있게 한다.

- 시작점: `0a3dfb81a8d6341b6e456e0aec72303018da93aa`. 당시 local env와 현재 작업 입구가 없었다.
- 발견: base CI는 현재 OPC UA와 event-time 모듈을 skip했고 base 의존성은 버전이 고정되지 않았다.
  검증 문서는 공개 독자가 접근할 수 없는 private log를 현재 근거로 가리켰다.
- 변경: 의존성 lock, setup/test/verify, 보존된 결과 재검증, 계약·작업 입구·이 backlog, OPC UA CI job.
  telemetry 판정 규칙과 보존된 공개 JSON/HTML/PNG는 그대로다. 수집 callback 실패를 timeout으로
  숨기는 진단 경로는 수정하고 storage failure 회귀 테스트를 추가했다.
- 반례: 핵심 모듈을 실행하지 않은 green suite, 또는 성공 문구 뒤에 실제 current chain은 읽을 수 없는 경우.
- 완료 조건: 새 환경 설치, base/OPC UA suite, 실제 replay, 디스크 digest 확인, Git·다음 작업·외부 행동 경계 복원.
  실제 결과는 PROJECT_STATUS에서 확인한다. 원격 CI 성공은 별도 gate다.

## MFG-07 — Intermittent local collection timeout

**재현성 조사 / 외부 재현·release 전 확인.** 전체 OPC UA suite 반복 중 interrupted collection에서
첫 3개 관측을 기다리다 5초 timeout이 한 번 발생했다. 실패 output에는 TP2 한 건만 있고 seal은 없었다.
그 뒤 같은 fixture의 6회 연속 수집 검증(총 18 scenario)은 성공했다. 원인은 아직 확정하지 못했다.

- 근거: `test_representative_verification_reports_five_operator_decisions`의 실제 실패와 보존된
  `.cache/telemetry-failure-observation/`. 구체적인 실행 경계는 PROJECT_STATUS를 따른다.
- 수정 범위: callback 내부 오류가 발생하면 기다리다 timeout으로 바뀌기 전에 원인을 노출한다.
  timeout에는 session·accepted·초기 알림·unknown mapping 수를 포함한다. 이는 진단 개선이며
  위 간헐 누락의 원인을 고쳤다는 주장은 아니다. timeout 연장·자동 retry·skip으로 숨기지 않는다.
- 다음 조사: 수정된 진단으로 동일 test를 단독 및 full suite에서 비교하고, 재발하면 callback 수와
  OPC UA publish/notification 경계를 좁힌다. 시간·의존성·부하 조건을 기록한다.
- 완료: 원인에 대응하는 작은 변경과 결정적인 반례 테스트, 실제 replay read-back으로 닫거나,
  환경 원인임을 입증하고 지원 환경·제약을 명시한다. 단순 재실행 성공은 해결 근거가 아니다.

## MFG-01 — One analyst result from a trusted version

**다음 후보 / MFG-08의 질문·범위 수용 뒤 제품 계약 논의.** 현재 결과는 trusted JSONL에서 끝난다. 분석가의 실제 질문,
분석 단위(grain), query, 반복 사용 근거가 없다. 데이터 신뢰성 데모를 유용한 데이터 엔지니어링
프로젝트로 발전시킬 때 먼저 닫을 공백이다.

- 결과 가설: 분석가가 검증된 version 하나를 읽어 설비·tag·시간 구간별 집계 하나를 얻고,
  그 결과의 source coverage와 dataset version을 함께 확인한다.
- 첫 행동: 질문 하나를 고르고 grain, 원본 timezone 해석, 구간, null/quality, 불완전한 구간의
  표시를 정한다. 작성자가 수용하기 전까지 제안으로 둔다. 3-row fixture로 생산 규칙을 추측하지 않는다.
- 검토용 최소 계약: `equipment × tag × [start, end) × dataset version`별 sample count·sample mean,
  선택한 source row 범위와 전달 coverage, quality 판정, source time 해석을 함께 제공한다.
  sample mean과 시간 가중 평균을 구분한다. source 공백은 관측 사실로 보여 주며 설비 운휴·결측률로 단정하지 않는다.
  분석 목적에 구간 평균이 유용한지도 먼저 확인한다. 이 정의는 아직 현재 Contract의 구현 동작이 아니다.
- 이전 결과의 가용성과 요청한 최신 구간의 준비 여부를 분리한다. 발행 거부 뒤 last-good을 계속 읽더라도
  그 결과의 범위·version과 최신 요청의 거부 사유를 표시해야 한다. 오래된 구간을 최신 결과로 보이지 않게 한다.
  모든 tag의 결과를 함께 막을지, 독립 구간별로 제공할지도 소비자 요구로 결정한다.
- 이후 최소 구현: 기존 trusted dataset을 읽는 local reader/query 하나. 질문에 맞는 가장 작은
  SQL/query 도구를 선택하며 Kafka·warehouse·대시보드 전면 개편은 열지 않는다.
- 독립 판정: fixture 정답을 손으로 계산한다. 정상 발행, 발행 거부, current 손상을 비교하고
  미검증 파일을 읽거나 여러 version을 섞는 경로가 없어야 한다.
- 완료: 새 독자가 같은 답을 재현하고 source/version까지 추적한다. 발행이 거부되면 이전
  검증된 답이 유지돼야 한다. 실제 독자를 구할 수 있으면 그 피드백도 별도로 기록한다.
- 중단 조건: 의미 있는 질문과 검증·feedback 경로를 찾지 못하면 데이터 품질 검증 프로젝트의
  좁은 주장으로 유지한다.

## MFG-02 — Recovery and replay identity

**계약 공백 / MFG-01 뒤.** `REPROCESS REQUIRED`는 현재 조치 제안이다.
[`core.py`](../src/manufacturing_data_platform/event_time_trust/core.py)의 version hash에는
server/collection time이 들어가고, [수집 실행](../src/manufacturing_data_platform/industrial_source/opcua_runtime.py)은
봉인된 scenario spool을 만든다. 원본 재수집과 저장된 관측값 재전달은 다른 동작이다.

- 실측 반례: 같은 fixture를 새 디렉터리 두 곳에 재생하면 event ID 9개는 같지만
  `server_timestamp`, `collected_at`이 달라져 dataset version이 달라졌다.
- 먼저 결정: dataset이 원본 사실을 식별하는지 수집 시도를 식별하는지, attempt provenance를
  어디에 두는지, 복구 결과가 이전 불완전 결과를 어떻게 대체하는지 정한다.
- 파일을 잘라 재저장하면 source hash가 바뀐다. 파일 안의 row identity와 파일을 넘어선 동일 관측·정정 identity를
  구분한다. 값·mapping·계산식의 변경이 어느 구간의 분석 결과를 무효화하는지도 정한다.
- 최소 결과: 수집 중단 한 건 → 근거 보존 → 해당 범위 복구 → 수용된 identity 규칙으로 발행.
  동일 재시도와 실제 값의 정정을 각각 비교한다. 실패하면 last-good을 유지한다.
- 완료: 실패 → 명시적 복구 → 검증된 발행 → 반복 재시도 → MFG-01 분석 결과 확인을 재현한다.
  source identity, attempt identity, dataset version을 각각 설명할 수 있어야 한다.
- 이 결과 전에는 원본 재수집의 멱등성, 자동 historical correction, end-to-end exactly-once를 주장하지 않는다.

## MFG-03 — Public report reproduction without the author's cache

**공개 재현성 공백.** 저장된 HTML/JSON/PNG는 과거 실행 근거다. Builder는 exact full MetroPT CSV와
보존된 OPC UA·Spark 실행 결과를 요구하지만 새 checkout에는 3-row fixture만 있다.
`make verify`의 새 Python trust evidence가 그 과거 full-source report를 재생성하지는 않는다.

- fixture 전용으로 명시한 별도 보고서와 전체 source authoring recipe 중 필요한 쪽을 고른다.
  fixture를 전체 CSV로 표시하거나 과거 날짜·hash를 새 실행 결과로 바꾸지 않는다.
- 완료: 새 checkout에서 허용된 source를 얻고 checksum을 확인해 해당 보고서를 생성하며,
  화면의 모든 수치를 생성한 run으로 추적한다. 누락·손상·다른 source는 출력 교체 전에 거부한다.
- 별도 검토한 공개 결과가 선택될 때까지 기존 보고서 artifact의 byte identity를 보존한다.

## MFG-04 — Measured workload beyond the explanation fixture

**벤치마크 후보.** 3행은 판정을 설명하기 위한 크기이며 처리 능력의 상한이 아니다.
전체 CSV 행 수를 실제 파이프라인 처리 실적으로 쓰면 안 된다.

- MFG-01에 필요한 rows/tags, window, replay rate, hardware, 자원 한도를 먼저 정한다.
  전체 파일 검증, 수집, trust 평가, query의 시간을 나누어 측정한다.
- 고정된 더 큰 입력 범위에서 소요 시간, peak memory, accepted/rejected 수와 재현성을 잰다.
  엔진을 바꾸기 전에 같은 입력·작업으로 단순 local baseline과 비교한다.
- 완료: 명령·source hash·machine spec·반복 측정이 구체적 한계 또는 개선을 뒷받침한다.
  production SLA를 만들거나 첫 실행과 no-op 재시도를 성능 개선처럼 비교하지 않는다.

## MFG-05 — Failure during publication and multiple writers

**필요가 생길 때 열 운영 경계.** 기존 파일 무결성 검사와 atomic rename이 구현돼 있지만
서로 다른 process의 writer 조정은 없다. 동시 발행과 process-kill 복구는 검증하지 않았다.
기존 exception injection 테스트의 증거는 그보다 좁다.

- 선택한 consumer/orchestrator가 process 재시도나 동시 writer를 요구할 때 연다.
- lock/catalog를 추가하기 전에 순서, reader consistency, orphan 처리, 복구 의미를 정한다.
- 완료: data/manifest/pointer 기록 중 process 종료와 경쟁 발행을 재현한다. reader가 정의된
  last-good 또는 명시적 실패를 보고, 그 상태에서 복구 명령을 실행할 수 있어야 한다.
- local `os.replace`를 분산 transaction이나 object storage 보장으로 확대하지 않는다.

## MFG-06 — Local Spark parity as repeatable optional evidence

**과거 근거 / 선택적 후속.** Spark 3.5.8 file micro-batch parity 구현은 있지만 기본 환경·새 CI의
검증 범위 밖이다. 과거 Kafka/Iceberg/Airflow pipeline은 현재 telemetry와 별개의 실험이다.

- Java/Python version을 기록한 별도 optional 환경에서 기존 parity 명령을 실행한다.
  watermark drop, dedup, checkpoint restart를 Python 판정과 대조한다.
- 시간·유지비가 정당화될 때만 별도 CI job을 추가한다. Kafka/Iceberg 연결은 consumer·복구
  요구와 새 계약이 있어야 하며 도구를 설치할 수 있다는 이유로 시작하지 않는다.

## MFG-09 — Independent use, release and feedback

**제품 검증 공백 / MFG-01·02의 usable version 뒤.** README와 테스트만으로 반복 사용이나 운영 책임을 증명하지 않는다.

- 첫 전달물은 source 구간 선택 → 준비 여부와 집계 확인 → 실패 이유 확인 → 범위 복구 → 정정된 결과 확인을
  실제로 실행하는 한 경로다. 첫 독자에게 맞는 CLI 또는 작은 화면 하나를 선택한다. 화면만 새로 꾸미는 작업과 구분한다.
- MFG-03과 연결해 작성자 cache 없는 설치·실행·결과 재생성을 검증한다. 지원 환경, 필요한 자원, 알려진 timeout,
  복구 방법과 결과의 source/version을 함께 전달한다. 외부 사용자가 읽을 수 있는 release candidate로 준비한다.
- MFG-08의 검증자가 처음 보는 구간에서 도움 없이 작업하는지, 어디서 멈추는지 기록하고 그 피드백으로 한 번 개선한다.
  설문 응답·GitHub star·작성자의 재실행은 업무의 반복 사용을 대신하지 않는다.
- 운영 실험은 고정된 여러 source 구간의 반복 수집·정정·재시작을 포함한다. 성공률, 소비 가능한 source 시점,
  거부 후 복구까지의 시간, query 시간, peak memory·disk 증가를 기록한다. 목표와 관측값, historical source time과
  실험 wall time을 구분한다. 통제된 재생을 장기간 실제 production 운영이라고 하지 않는다.
- 실제 release를 선택하면 검토 가능한 diff·원격 CI·version·release 결과·설치한 runtime의 identity/read-back·
  변경 후 검증을 연결한다. push·PR·release·배포는 준비한 결과에 대해 사용자의 최종 확인을 받은 뒤 수행한다.
- 완료: 독립 사용 결과, 한 차례 개선 diff, 재현 명령, 운영 수치와 미해결 한계가 연결된다. 외부 수용이 없으면
  `local release candidate`로 기록하며 상용 제품·현장 도입으로 승격하지 않는다.

## 이력서와 면접에서의 사용

지금은 **로컬 산업 데이터 품질·발행 검증 프로젝트**로 설명할 수 있다. source/time/unit/quality를
보존하고, 불완전하거나 신뢰할 수 없는 입력의 발행을 막고, 이전 trusted dataset을 보호한 근거가 있다.
production 데이터 플랫폼, 사업 성과, 분석가의 실사용, 처리 규모는 아직 별도 근거가 필요하다.

먼저 사용자 업무와 기존 대안(MFG-08)을 확인하고, 분석 결과(MFG-01), 복구 결과(MFG-02), 제3자 재현(MFG-03),
반복 사용·운영 피드백(MFG-09)을 연결한다. 측정한 규모(MFG-04)는 선택한 workload를 뒷받침한다.
기술 이름을 늘리는 것보다 각 결과를 한 번씩 닫는다. row count만으로 충분하지 않은 이유,
watermark와 완전성이 다른 이유, 정확히 무엇이 멱등한지를 code·반례·실행 명령으로 설명한다.
AI와 구현했다는 사실만으로 본인의 이해·판단을 입증할 수는 없으므로 그 설명은 작성자가 검토한다.
