# Manufacturing backlog

확인한 근거 공백에 따라 순서를 정한다. 모든 항목을 구현하겠다는 약속은 아니다.
현재 선택한 작업은 [PROJECT_STATUS](../PROJECT_STATUS.md) 한 곳, 각 작업의 범위와 완료 조건은 이 파일이 소유한다.
새 제품 의미와 외부 행동의 최종 결정자는 프로젝트 작성자다.

## MFG-12 — Guided result explanation preview

**진행 중 — 현재 결과 설명 역할 수용 뒤 첫 로컬 구현.** 기준 `defbacd452257ff626ffa1888005fbf7135940e9`.

- 사용자 결과: 교체 실패 뒤 어떤 원본·버전의 통계가 남았는지 이해하고 그 결과의 근거로 이동한다.
- 범위: 하단 진입·선택형 질문 3개·서버 snapshot 근거·설명 패널, 맥락 변화/취소/실패 처리와 좁은 화면 접근성.
  [수용한 첫 계약](FILE_REVIEW_CONTRACT.md#guided-result-explanation--first-local-preview)이 Data/API/UI·반례를 소유한다.
- 구현 판단: 기존 workspace와 snapshot/query 계산을 재사용한다. 실제 데이터의 규칙 기반 설명이며 mock 수치나 AI 생성 답변으로 표시하지 않는다.
- 제외: 자유 입력/다중 턴, 실제 LLM·외부 전송·비용, 파일 변경 실행·계정·조직·두 버전 비교, 공개 Release 범위 변경.
- 반례: 실패한 새 파일의 평균으로 오인, 미제출 조건 적용, 다른 workspace 유출, 취소/파일 변경 뒤 늦은 답변, 근거 없는 설비 정상/고장 단정.
- 완료: 실제 diff/독립 기대값 검토, 필수 검사, 실제 HTTP·full/sample browser·320/390/1440px와 근거 이동·지연/취소 반례.
  guided preview 완료를 자유 대화·AI 평가·실사용 향상으로 세지 않는다.

## MFG-11 — Product source ownership and navigation

**로컬 완료 — 2026-09-09 작성자가 승인한 문서·작업 기준 정비.** 변경 기준 `dd82b75`와 기존 문서 작업을 보존했다.

- 사용자 결과: 새 독자가 현재 CSV 서비스와 보존 실험을 구분하고, 시나리오·계약·화면·API·데이터·검증을 어디서 읽고 바꾸는지 찾는다.
- 범위: 기존 README·AGENTS·Architecture의 연결과 변경/폐기 책임, 현재 상태·backlog·조사·검증 기록의 역할 정리.
  연구 근거는 `docs/research/`, 작업과 수용 gate는 이 backlog, 현재 한 행동은 PROJECT_STATUS가 소유한다.
- 보존: 기존 제품/권한/데이터 계약, source·런타임 설정, 보존된 보고서 artifact, 기존 MFG ID와 조회·복구 의미.
- 반례: 수용된 약속을 미구현이라고 제안으로 되돌리거나, 과거 OPC UA 결과를 현재 웹 서비스/배포 성과로 읽거나, 이동한 근거를 찾을 수 없다.
- 완료: 실제 diff와 링크/소비자 대조, 기존 reader-facing claim 검사의 의미 보존, 필수 통합 검사, 독자 입구에서 owner·미결정·다음 행동까지 연결 확인.
  로컬 정비이며 chat 구현·제품 Release·배포 승인이 아니다.
- 결과: README는 현재 CSV 서비스의 입구, Architecture는 실제 code·runtime 책임 지도, 두 조사 문서는 제안의 근거가 됐다.
  Dockerfile/Compose의 강제 지점을 실제 설정에 맞게 보정했다. [통합 검증](VERIFICATION.md#source-ownership-verification)은
  248 passed / 17 skipped와 fixture hash read-back을 포함한다. 새 독자의 사용 성공은 아직 관찰하지 않았다.

## MFG-08 — Product value and source reality

**원본·대안 조사 완료 / 첫 파일 서비스 방향 수용 / 시장 수요 미검증.**
[원본 점검·제품 대안·사용자 검증 가설](research/file-review-workflow.md)이 조사 근거를 소유한다.
수용한 첫 범위는 [File Review Contract](FILE_REVIEW_CONTRACT.md), 구현 결과는 MFG-01이다.

- 사용자 결과: 요청받은 설비·태그·시간 구간의 출처·품질 한계를 확인하고, 정정 뒤 근거와 함께 전달한다.
- 남은 질문: 실제 담당자가 기존 CSV+SQL/스프레드시트 대신 반복해서 사용할 이유가 있는가?
- 반례: 공개 원본의 값을 사용하고 평균이 정확해도 실제 설비 관측의 완전성·센서 정확도·제품 수요는 증명되지 않는다.
- 다음 증거: MFG-09에서 실제 업무 한 건·비민감 파일로 올바른 버전 선택, 도움 요청과 전달 결과를 관찰한다.
  접근할 사용자가 없으면 조사·공개 준비는 계속하되 실사용 수용으로 기록하지 않는다.

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

**첫 파일 서비스 구현·로컬 검증 완료 / 외부 수용은 별도.** 2026-09-08 작성자가 공개 가능한 실사용 서비스 후보를 만들도록 위임했다.
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

**활성 release gate / 실제 독립 사용·공개 운영은 미실행.** 첫 파일 서비스와 bounded sample-only
컨테이너를 로컬에서 구현·검증했다. README와 테스트만으로 반복 사용이나 운영 책임을 증명하지 않는다.

- 바로 다음 한 행동: 병합된 `main`의 `v0.1.0` release notes와 tag 대상을 검토하고 GitHub Release 여부를 결정한다.
  그 뒤 실제 검토자 한 명의 비민감 CSV로 설명 없는 10분 사용을 관찰한다.
- 로컬 수용 근거: sample 모드는 임의 upload/replace를 API 403으로 거부한다. digest-pinned Python 3.12 이미지가
  UID 10001·read-only root로 실행됐고, release/revision read-back, 7,144개 Oil_temperature 조회,
  같은 volume 재시작 후 동일 dataset version을 확인했다. Chromium desktop/mobile에서도 upload UI 제거,
  누락·복구·browser isolation과 page error 0을 확인했다.
- 원격 릴리스 뒤 첫 사용: 파일 검토를 실제로 하는 사람 한 명의 비민감 CSV와 업무 질문으로 10분 사용 시나리오를
  구체화한다. 접근할 사용자가 없으면 후보 호스트의 공개 체험 배포안을 준비하되 제품 채택으로 기록하지 않는다.
- 공개 host 전 구체화: TLS/허용 Host/secure cookie/영속 또는 폐기 volume, edge 요청·세션 생성 제한, runtime log/alert, 실제 동시 요청 메모리와
  DB/WAL 용량, 정리 일정과 운영 책임. [실행 guide](FILE_REVIEW_GUIDE.md)의 현재 한도를 근거로 설정·검증한 뒤 승인받는다.
- 공급망 gate: 2026-09-08 `requirements-service.lock`의 Python advisory audit는 알려진 취약점 0건이었다.
  base OS image scan은 로컬 Docker Scout 인증이 없어 미실행이므로 선택한 registry/host의 scanner로 다시 확인한다.
- 알려진 UX 공백: CSV 열 매핑과 큰 파일/장기 보관/공유 계정은 없다. 실제 첫 파일이 요구하는 한 가지를 고른다.
  Chrome으로 로컬 확인했으며 Safari·Firefox·모바일 실기기와 보조기술 검증은 후속이다.

### 사용자 질문과 조사 근거로 여는 구조 gate

아래는 예정 기능 목록이 아니다. 실제 사용에서 막힌 질문과 작성자의 새 제안을 공식 제품 사례·공개 화면·코드 근거에
대조해 가장 작은 검증을 고른다. 첫 사용자 접근 전에도 조사·설계 추천은 가능하며, 그 근거를 수요 검증으로 승격하지 않는다.
같은 문제가 반복되거나 현재 단일 프로세스·SQLite 경계를 넘는 증거가 생기면 오른쪽 구조를 검토한다.
제품 의미·권한·비용이 바뀌는 구현은 수용된 계약 뒤에 진행한다. 제품 내 채팅 후보는 [MFG-10](#mfg-10--context-bound-review-assistant-discovery)에서 조사한다.

| 관찰할 사용자 질문 | 먼저 검증할 작은 변경 | 더 큰 구조를 여는 근거 |
|---|---|---|
| “내 파일의 열 이름·시간대·단위가 다른데 어디서 맞추는가?” | 업로드 전 열 대응과 시간대·단위 확인 한 화면, 저장하지 않는 매핑 1회 | 두 번째 파일에서도 같은 대응을 재사용해야 할 때 versioned mapping profile/schema registry 검토 |
| “수정 전후에 무엇이 달라졌고 왜 이제 전달해도 되는가?” | 두 source version의 행·구간·품질 변화 요약을 기존 manifest에 연결 | 여러 사람이 정정 원인과 승인 순서를 남겨야 할 때 append-only event/audit model 검토 |
| “받는 사람이 계정 없이도 같은 결과를 확인할 수 있는가?” | dataset version·query·digest에 고정된 읽기 전용 결과물의 이해 가능성부터 시험 | 비공개 장기 공유·회수·기기 간 복원이 실제로 필요할 때 identity, authorization, retention 계약을 함께 설계 |
| “8 MiB/50,000행을 넘기거나 동시에 두 명이 쓰면 끝까지 처리되는가?” | 실제 한계 파일의 시간·메모리·DB 증가와 명확한 거부 메시지 측정 | 요청 시간이 사용자 흐름을 막거나 동시 사용이 확인될 때 async job state, queue, object storage와 다중 writer DB 검토 |
| “이 구간 판단과 관련된 매뉴얼·점검 절차의 어느 페이지를 같이 보내야 하는가?” | 사용 허가가 분명한 PDF 한 건을 구조화해 문서 hash·page 근거를 evidence ZIP에 고정 | 반복 검색할 여러 문서가 생길 때 versioned document store와 비동기 변환 검토. 검색/RAG는 page 근거 정확도 평가 뒤 결정 |

마지막 행은 [Docling Serve](https://github.com/docling-project/docling-serve)를 붙이기 위한 명분이 아니라, telemetry 검토자가
실제로 문서 근거를 함께 전달하는지 확인하는 질문이다. Docling의 실제 사용자도 object별 source confidence를 결과 gate에
쓰려는 [요구 #624](https://github.com/docling-project/docling-serve/issues/624)를 남겼다. 이는 provenance 설계 참고이며 이
Manufacturing 흐름의 수요 증거는 아니다.

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

## MFG-10 — Context-bound review assistant discovery

**공개 조사·현재 코드 대조 완료 / 현재 결과 설명 역할 수용 / 외부 AI 설계는 미수용.** 작성자는 제품 우측 하단의 대화 기능 조사를 요청했다.
[실제 사례·화면 추천·Data/API·안전 검증안](research/review-assistant.md)이 조사와 후속 설계 후보를 소유한다.

- 추천 결과: 마지막으로 확인한 파일 버전·조회 구간에 근거해 “교체가 실패했는데 왜 이전 평균이 남는가?”를 설명한다.
- 현재 경계: 첫 파일 계약과 MFG-09 Release 범위 유지. 외부 전송·보관·비용·실행 권한과 이번 Release 포함은 미결정이다.
- 반례: 미제출 필터 초안을 마지막 분석 결과로 오해하거나, 늦은 답변을 다른 버전에 붙이거나, 품질 미제공을 정상으로 단정한다.
- 수용된 방향: 2026-09-09 현재 결과 설명형으로 계속 진행. 선택 질문 기반 로컬 preview는 MFG-12이며, 자유 대화와 외부 AI 연결은 별도 후속 결정이다.
- 그 뒤 완료 조건: 대표 질문과 답변 불가, 근거·허용 데이터·실패 동작을 계약으로 닫은 작은 end-to-end Slice를 검증한다.
  고정 응답/mock은 흐름 검증이며 AI 품질이 아니다. 실제 AI 호출·유료 서비스·원본 외부 전송·배포는 별도 승인 범위다.

## 이력서와 면접에서의 사용

지금은 기존 **로컬 산업 데이터 품질·발행 검증**에 더해 **CSV 검토·분석·수정·근거 전달 웹 서비스 후보**를
구현·검증한 근거가 있다. 최종 통과 결과·현재 branch·외부 반영 여부는 PROJECT_STATUS로 확인한다. source/time/unit/quality를
보존하고, 불완전하거나 신뢰할 수 없는 입력의 발행을 막고, 이전 trusted dataset을 보호한 근거가 있다.
production 데이터 플랫폼, 사업 성과, 분석가의 실사용, 처리 규모는 아직 별도 근거가 필요하다.

파일 서비스의 분석·보관 원본 복구와 기존 OPC UA 실험을 분리해 설명한다. 다음은 사용자 업무·대안(MFG-08),
분석 결과(MFG-01), 각 계약의 복구 결과(MFG-02), 제3자 재현(MFG-03),
반복 사용·운영 피드백(MFG-09)을 연결한다. 측정한 규모(MFG-04)는 선택한 workload를 뒷받침한다.
기술 이름을 늘리는 것보다 각 결과를 한 번씩 닫는다. row count만으로 충분하지 않은 이유,
watermark와 완전성이 다른 이유, 정확히 무엇이 멱등한지를 code·반례·실행 명령으로 설명한다.
AI와 구현했다는 사실만으로 본인의 이해·판단을 입증할 수는 없으므로 그 설명은 작성자가 검토한다.
