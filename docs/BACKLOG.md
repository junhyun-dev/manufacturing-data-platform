# Manufacturing backlog

확인한 근거 공백에 따라 순서를 정한다. 모든 항목을 구현하겠다는 약속은 아니다.
현재 선택한 작업은 [PROJECT_STATUS](../PROJECT_STATUS.md) 한 곳, 각 작업의 범위와 완료 조건은 이 파일이 소유한다.
새 제품 의미와 외부 행동의 최종 결정자는 프로젝트 작성자다.

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

**재현성 조사 / 기능 확장 전 확인.** 전체 OPC UA suite 반복 중 interrupted collection에서
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

**다음 후보 / 제품 계약 논의.** 현재 결과는 trusted JSONL에서 끝난다. 분석가의 실제 질문,
분석 단위(grain), query, 반복 사용 근거가 없다. 데이터 신뢰성 데모를 유용한 데이터 엔지니어링
프로젝트로 발전시킬 때 먼저 닫을 공백이다.

- 결과 가설: 분석가가 검증된 version 하나를 읽어 설비·tag·시간 구간별 집계 하나를 얻고,
  그 결과의 source coverage와 dataset version을 함께 확인한다.
- 첫 행동: 질문 하나를 고르고 grain, 원본 timezone 해석, 구간, null/quality, 불완전한 구간의
  표시를 정한다. 작성자가 수용하기 전까지 제안으로 둔다. 3-row fixture로 생산 규칙을 추측하지 않는다.
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

## 이력서와 면접에서의 사용

지금은 **로컬 산업 데이터 품질·발행 검증 프로젝트**로 설명할 수 있다. source/time/unit/quality를
보존하고, 불완전하거나 신뢰할 수 없는 입력의 발행을 막고, 이전 trusted dataset을 보호한 근거가 있다.
production 데이터 플랫폼, 사업 성과, 분석가의 실사용, 처리 규모는 아직 별도 근거가 필요하다.

보완 우선순위는 분석 결과(MFG-01), 복구 결과(MFG-02), 제3자 재현(MFG-03), 측정한 규모(MFG-04)다.
기술 이름을 늘리는 것보다 각 결과를 한 번씩 닫는다. row count만으로 충분하지 않은 이유,
watermark와 완전성이 다른 이유, 정확히 무엇이 멱등한지를 code·반례·실행 명령으로 설명한다.
AI와 구현했다는 사실만으로 본인의 이해·판단을 입증할 수는 없으므로 그 설명은 작성자가 검토한다.
