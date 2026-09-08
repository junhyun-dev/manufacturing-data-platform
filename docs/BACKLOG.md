# Manufacturing backlog

확인한 근거 공백에 따라 순서를 정한다. 모든 항목을 구현하겠다는 약속은 아니다.
현재 선택한 작업은 [PROJECT_STATUS](../PROJECT_STATUS.md) 한 곳, 각 작업의 범위와 완료 조건은 이 파일이 소유한다.
새 제품 의미와 외부 행동의 최종 결정자는 프로젝트 작성자다.

## MFG-08 — Product value and source reality

**2026-09-08 외부 조사·원본 점검 완료 / 사용자 결과 중심의 제품화 방향 수용.** 작성자는 기술 시연에서
사용자 결과·복구·반복 사용으로 발전시키고 여러 세션에서 이어가는 방향에 동의했다.
이후 작성자는 직접 사용할 수 있는 첫 서비스를 구현하도록 위임했다. CSV 검토·구간 분석·수정 파일·보관 원본 복구의
구체적인 첫 정책은 [파일 계약](FILE_REVIEW_CONTRACT.md)으로 수용했고, 시장 수요는 여전히 검증할 가설이다.
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

**현재 제품 gate:** MFG-01의 파일 서비스와 제한된 복구 흐름을 로컬 구현·검증한다. 이후 MFG-09에서
외부 사용과 공개 운영 조건을 확인한다. MFG-07은 기존 OPC UA 실험의 미해결 결함이며, 그 런타임을
사용하지 않는 파일 서비스의 사용자 흐름과 구분한다. Spark·전체 source·현장 수집은 실제 요구가 있을 때만 연다.

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

**첫 파일 서비스 구현 / 로컬 검증.** 2026-09-08 작성자가 공개 가능한 실사용 서비스 후보를 만들도록 위임했다.
기존 MetroPT/OPC UA 계약에 일반 업로드의 출처를 끼워 넣지 않고, [File Review Contract](FILE_REVIEW_CONTRACT.md)를
별도로 수용했다. 실제 사용자 접근·반복 사용은 아직 미확인이다.

- 대상과 결과: 설비 CSV를 전달받은 데이터 엔지니어·분석가가 파일을 검사하고, 설비/태그/시간 구간을 분석해
  선택한 전체 CSV와 source/version/quality 근거를 ZIP으로 전달한다. 웹 화면·파일 교체·이력까지 한 흐름이다.
- 수용한 의미: 한 행=한 관측, 키 중복·단위 혼합 거부, UTC 또는 시간대 미제공의 일관성,
  `equipment × tag × [start,end) × version`의 SQL 표본 통계. 품질 미제공을 Good으로 승격하지 않는다.
- 거부 행동: 최신 실패와 이전 정상 결과를 분리한다. 다운로드는 화면에서 확인한 버전을 고정한다.
  저장 원본/버전 손상은 분석을 막되 다른 파일의 목록·삭제·교체는 계속 사용할 수 있게 한다.
- 구현 경계: `file_review/`의 독립 FastAPI/SQLite/브라우저 서비스다. 기존 trusted OPC UA JSONL을
  이 화면에 연결한 것은 아니며, `industrial_telemetry_v1`의 수집·품질 정책도 바꾸지 않았다.
- 실제 공개 샘플: 하루치 7,144 source rows × 3 tags = 21,432 observations. 이 크기는 검증한 입력 범위이며 처리량 지표가 아니다.
- 가장 강한 반례: 수정 파일 실패·저장 중 실패 뒤 이전 결과가 바뀌거나, 서로 다른 브라우저의 파일이 노출되거나,
  다운로드가 화면과 다른 버전을 읽는 경우. API·저장소 오류 주입·실제 HTTP·브라우저로 검증한다.
- 재현: [사용 흐름과 명령](FILE_REVIEW_GUIDE.md), 실행 결과는 [PROJECT_STATUS](../PROJECT_STATUS.md).
- 남은 제품 gate: 제3자가 자기 CSV로 같은 일을 하고 도움/오류/기존 도구 대비 가치를 기록한다(MFG-09).
  실제 파일이 wide CSV나 다른 열 이름을 쓰면, 먼저 한 건을 확보해 명시적인 매핑·단위·시간대 확인을 검토한다.
  모든 제조 포맷을 추측해서 미리 지원하지 않는다.

## MFG-02 — Recovery and replay identity

**파일 전달 복구는 구현 / OPC UA 재수집 계약은 미해결.** 새 파일 서비스는 보관한 동일 원본의 재검사와
샘플 전달 누락 복구를 실제 실행하고 같은 content version으로 수렴한다. 수정 파일은 별도 version이다.
이 제한된 근거를 기존 OPC UA 재수집에 적용하지 않는다. 아래 실험의 `REPROCESS REQUIRED`는 여전히 조치 제안이다.
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

**기존 보고서의 재현성 공백.** 새 CSV 서비스는 bundled sample과 `make verify-service`로 cache 없이 실행하도록
구성했다. 이것으로 과거 OPC UA/Spark 보고서 재생성을 증명하지 않는다. 저장된 HTML/JSON/PNG는 과거 실행 근거다. Builder는 exact full MetroPT CSV와
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

**기존 OPC UA 경로의 후속 운영 경계.** 새 파일 서비스의 SQLite transaction은 저장 실패 rollback·동시 재검사·
재시작·무결성 거부를 검증한다. process-kill·원격 storage·여러 replica의 보장은 별도다. 기존 OPC UA 파일 무결성 검사와 atomic rename이 구현돼 있지만
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

**다음 제품 gate / 실제 독립 사용·공개 운영은 미실행.** 첫 파일 서비스는 로컬 구현·검증 단계까지 진행한다.
README와 테스트만으로 반복 사용이나 운영 책임을 증명하지 않는다.

- 바로 다음 한 행동: 파일 검토를 실제로 하는 사람 한 명의 비민감 CSV와 업무 질문으로 10분 사용 시나리오를
  구체화한다. 접근할 사용자가 없으면 후보 호스트의 공개 체험 배포안을 준비하되 제품 채택으로 기록하지 않는다.
- 공개 전 구체화: TLS/허용 Host/secure cookie/영속 볼륨, 익명 요청·세션 생성 제한, 실제 동시 요청 메모리와
  DB/WAL 용량, 정리 일정과 운영 책임. [실행 guide](FILE_REVIEW_GUIDE.md)의 현재 한도를 근거로 설정·검증한 뒤 승인받는다.
- 알려진 UX 공백: CSV 열 매핑과 큰 파일/장기 보관/공유 계정은 없다. 실제 첫 파일이 요구하는 한 가지를 고른다.
  Chrome으로 로컬 확인했으며 Safari·Firefox·모바일 실기기와 보조기술 검증은 후속이다.

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

지금은 기존 **로컬 산업 데이터 품질·발행 검증**에 더해 **CSV 검토·분석·수정·근거 전달 웹 서비스 후보**를
구현한 근거를 만들고 있다. 최종 통과 결과·현재 branch·외부 반영 여부는 PROJECT_STATUS로 확인한다. source/time/unit/quality를
보존하고, 불완전하거나 신뢰할 수 없는 입력의 발행을 막고, 이전 trusted dataset을 보호한 근거가 있다.
production 데이터 플랫폼, 사업 성과, 분석가의 실사용, 처리 규모는 아직 별도 근거가 필요하다.

파일 서비스의 분석·보관 원본 복구와 기존 OPC UA 실험을 분리해 설명한다. 다음은 사용자 업무·대안(MFG-08),
분석 결과(MFG-01), 각 계약의 복구 결과(MFG-02), 제3자 재현(MFG-03),
반복 사용·운영 피드백(MFG-09)을 연결한다. 측정한 규모(MFG-04)는 선택한 workload를 뒷받침한다.
기술 이름을 늘리는 것보다 각 결과를 한 번씩 닫는다. row count만으로 충분하지 않은 이유,
watermark와 완전성이 다른 이유, 정확히 무엇이 멱등한지를 code·반례·실행 명령으로 설명한다.
AI와 구현했다는 사실만으로 본인의 이해·판단을 입증할 수는 없으므로 그 설명은 작성자가 검토한다.
