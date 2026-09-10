# Verification — 재현과 증거의 범위

현재 변경의 exact baseline·결과·다음 gate는 [PROJECT_STATUS](../PROJECT_STATUS.md)가 소유한다.
이 문서는 새 checkout의 실행 방법과 각 검증의 범위, [날짜별 파일 서비스 검증 기록](#file-service-verification)을 소유한다.
기록된 검증은 당시 revision의 근거이며 현재 배포·실사용을 자동으로 주장하지 않는다.

현재 CSV 웹 서비스는 [사용·검증 guide](FILE_REVIEW_GUIDE.md)의 `make serve`·`make verify-service`로
실행한다. 이 문서의 OPC UA·Spark·historical report 검증은 별도의 기존 실험이며 웹 실행의 선행조건이 아니다.

<a id="review-navigation-verification"></a>
## Review navigation — 2026-09-10 local verification

수용 기준은 `feat/review-navigation@3686f5dfa09d7abd19c0f2224192ef87bccf2def` 이후의 정적 UI 세 파일과
[`verify_review_navigation_browser.py`](../scripts/verify_review_navigation_browser.py) diff다. 기존 조사 세 문서는
`51b66ad`에 보존했다. [탐색 계약](FILE_REVIEW_CONTRACT.md#review-navigation--wide-view-fullscreen-and-item-search)과
[사용법](FILE_REVIEW_GUIDE.md#넓게-보기전체화면항목-이름-찾기)이 현행 약속과 실행 경로를 소유한다.
**웹 탐색은 LOCAL VERIFIED / 저장소 전체 검사 gate는 OPEN / NOT RELEASED·NOT DEPLOYED**다.
검증한 구현은 로컬 commit `743bebd0baaabdd1006ca3607bc11963c430185b`에 보존했다.

| 실제 검사 | 결과와 범위 |
|---|---|
| `make setup` | PASS, 기존 lock의 39 packages 확인 |
| 새 탐색 browser full/sample | **13/10개 묶음 PASS**, Chromium 140.0.7339.16, 최종 03:38:39–03:39:24 UTC |
| 기존 지도·설명·파일 browser full/sample | 각각 **14/11, 18/12, 11/7 PASS**, 최종 UI에서 재확인 |
| `MFG_REVIEW_MODE=full make verify-service` | PASS, 실제 HTTP·독립 CSV/ZIP·보관 원본 복구·재시작. Backend는 이후 변경 없음 |
| `make verify` | PASS, `.cache/telemetry-runs/run-YOqegXrl/`의 5개 판정과 current → manifest → 9개 event digest를 직접 재계산. 이 한 실행의 결과이며 아래 반복 검사 문제는 별개 |
| `make test` | 초기 **255 passed / 17 skipped**(52.22초). 최종 UI 뒤 전체 실행은 **1 failed / 254 passed / 17 skipped**, 브라우저 종료 뒤 단독 전체 실행은 **2 failed / 253 passed / 17 skipped**(37.46초). 아래 OPC UA 시각 검사 실패를 숨기지 않음 |
| 문서·공개 경계 | `tests/test_portfolio_release.py` **43 passed**(0.07초), 변경 문서 링크 대상 185개·Markdown fragment 61개와 추가 문장의 private-path/secret 검사·`git diff --check` PASS |

이번 실행 root는 `.cache/review-navigation-checks/20260910T030858567199Z/`다.
최종 `navigation-full-final/receipt.json`, `navigation-sample-final-2/receipt.json`,
`map-final-{full,sample}/`, `explanation-final-{full,sample}/`, `browser-final-{full,sample}/`에
실제 응답·ZIP·PNG·검사 결과가 있다. HTTP 전용 receipt는
`.cache/file-review-verification/20260910T032208717811Z/receipt.json`이다.
각 browser 검사는 자신의 workspace/fixture만 사용했다. 새 탐색 fixture 삭제 PASS, JS 오류와 외부 HTTP 요청은 없었다.

- 실제 공개 CSV의 온도 7,144개, 평균 55.7481173012318와 ZIP의 전체 값·원본 hash·version·조회 조건을
  Python CSV/통계와 비교했다. 미제출 날짜를 남긴 채 검색/지우기/화면 전환을 해도 같은 ZIP 근거를 유지했다.
- 검색 입력/페이지 이동과 화면 전환의 API 무호출, 기존 선택·설명·제출 결과 보존, 실제 항목 선택의 무효화를
  확인했다. 지연 중인 실제 query는 화면/검색 변경을 지나서 완료됐다. 다른 탭의 재검사, 거부된 교체, 삭제,
  cookie 없는 조회와 명시적 새로고침을 확인했다. 503·무결성 UI 반례는 표시한 응답 주입이며 서버 변조/만료는 기존 tests가 소유한다.
- 8/11/50/200항목, 128자 markup 이름, 다른 설비/파일의 같은 이름은 **합성 stress fixture**다.
  모든 검색 페이지에 접근하고 지도 최대 8개·선택 항목 포함·완전한 원래 목록·텍스트 비실행을 확인했다.
  200항목 fixture의 199개 검색 결과 페이지 순회는 0.788초였으나 자동화 한 실행이며 사용자 속도나 SLA로 주장하지 않는다.
- 1440/390/320px·가로 화면, 키보드·포커스·전체화면 진입/종료 실패·중복 요청 방지와 설명/삭제 dialog 공존을 확인했다.
  지원 API의 **실제 document-root fullscreen**과 거부/미지원/지연 Promise 주입을 구분했다.
  별도 Xvfb의 XTest 키로 브라우저 Esc와 실제 200% 확대(DPR 1→2)를 확인했다. Xvfb에는 창 관리자가 없어
  fullscreen 전후 창 크기는 CDP로 명시적으로 바꿨다. OS의 자동 전체화면 크기 변경·실제 휴대폰/Safari는 미검증이다.
- Main 직접 화면 검토: [넓게 보기](assets/file-review-navigation-desktop.png), [390px 검색/목록](assets/file-review-navigation-mobile.png).
  실제 공개 샘플이다. 로컬 `showcase-mobile-map.png`와 `native-200-x11.png`도 직접 열었다.
  확대 화면의 Playwright 캡처가 실제 창을 온전히 담지 못해 기존 설치된 X11 화면 캡처로 별도 대조했으며,
  브라우저 단축키 검증을 emulated viewport 변경으로 대신하지 않았다.

최종 HTTP로 받은 bytes와 checkout이 같았다. 아래 SHA-256이 검증한 UI를 특정한다.

```text
index.html  2af592cbd2548900feaa1932b16b0f38dbf5d1f6fd54659c2b72b318eda81826
app.js      14d8aa47956c1f2080de858b33b6b8303b6acd749fb86f2b305d41d20fb069ac
styles.css  339b77b5648c38465c0fe12970ca67b41634ee0fc4844cf970b8c35aec7e13b8
```

**남은 전체 검사 문제:** 변경하지 않은 `test_event_time_trust.py::test_representative_verification_reports_five_operator_decisions`와
`test_industrial_source_contract.py::test_local_opcua_three_scenarios_preserve_semantics_and_last_good`에서
`collected_at must not precede server_timestamp`가 발생했다. 최근 단독 전체 로그는 위 root의 `make-test-serial.log`다.
별도 한 번의 대상 검사(원래 validator에 그대로 위임하는 진단 wrapper)는 1 passed(9.51초)였고 실패 시각을 포착하지 못했다.
단순 병렬 실행 원인이나 해결 완료로 단정하지 않는다. timestamp 순서를 만드는 원인은 UNKNOWN이며
[MFG-02](BACKLOG.md#mfg-02--recovery-and-replay-identity)에 다음 조사와 종료 조건을 남겼다.
이번 UI 변경으로 laboratory 계약을 완화하거나 시각·Docker/WSL·관련 source/tests를 바꾸지 않았다.

분담 회고: 기존 Worker는 정적 UI 세 파일만 구현하고 03:33:44 UTC 반환 뒤 쓰기를 동결했다.
Main은 실제 diff와 독립 browser/CSV/ZIP을 검토했다. 삭제 dialog가 열린 채 좁은 화면으로 바뀐 뒤 취소하면
설명 밖에 포커스가 남는 반례를 찾아 Main이 한 번 보정했고, 같은 경로와 전체 관련 browser 검사를 통과시켰다.
Worker clarification/rework는 0/0; Main의 제품 통합 보정은 1회다. browser oracle은 포인터 대상·CSP·viewport·Xvfb
창 관리·텍스트 비교의 다섯 실행 보정과 작성 중 기계적 보정 두 건이 필요했다. 다음에는 브라우저 native 동작을
작은 probe로 먼저 분리해 인계 뒤 oracle 재작업을 줄이는 것이 제안이다. 공통 방법은 변경하지 않았다.
Worker UTC 시작/종료는 03:02:21–03:33:44, 수용 계약 commit부터 최종 탐색 browser 종료까지는 03:01:18–03:39:24다.
문서/preview 정리와 뒤 전체 검사 재확인은 이 구간 밖이다. 시각 순서 오류도 관측했으므로 이 기록을 정밀 성능 비교에 쓰지 않는다.
모델별 token·비용은 **UNKNOWN**이다. 로컬 검사 외 새 서비스·유료/외부 AI·push/PR/merge/Release/배포는 없다.
MFG-09/12의 실제 검토자 과제, 지도/검색의 사용자 효용과 세 항목에서의 이점은 계속 미검증이다.

로컬 preview는 기존 자기 제품 프로세스/DB 소유를 확인한 뒤 같은 DB로 갱신했다. 주소는 `http://127.0.0.1:8000`,
source revision은 `743bebd0baaabdd1006ca3607bc11963c430185b`다. 실제 health·UI bytes와 새 브라우저에서
샘플 이름 검색 → 온도 조회 → 넓게 보기 → 같은 version/hash의 7,144개 ZIP을 확인했다.
`.cache/review-navigation-preview/20260910T035019572965Z/{server,readback}.json`이 로컬 실행 근거다.
검증용 full/sample 서버만 종료했고 preview는 남겼다. 다른 제품 프로세스·Personal·공통 문서는 변경하지 않았다.


<a id="equipment-map-verification"></a>
## Equipment data map — 2026-09-10 local verification

기준은 `feat/equipment-data-map@a9abcf985476dbe0b9f0a3bc32b30a7b6ff38bc8`와 아래 정적 UI·browser oracle 변경이다.
기존 Discovery 네 문서는 `7b23848`, 수용 계약은 `a9abcf9`에 보존했다. Worker는 별도 checkout에서 정적 UI 세 파일만
구현했고 Main이 실제 diff·화면·서버/ZIP 정답을 검토해 통합했다. backend·DB·API·의존성·동결 portfolio artifact는 그대로다.
현행 의미는 [지도 계약](FILE_REVIEW_CONTRACT.md#equipment-data-map--first-local-view), 사용법은 [Guide](FILE_REVIEW_GUIDE.md#설비-데이터-지도로-항목-찾기)로 연결한다.

| 실제 검사 | 결과와 범위 |
|---|---|
| `make setup` | PASS, 기존 lock의 39 packages 확인 |
| `make test` | **255 passed / 17 skipped**, 57.39초; 기존 FastAPI/Starlette deprecation warning 2개. optional runtime은 실행하지 않음 |
| `make verify` | PASS, `.cache/telemetry-runs/run-gTqOADk1/`의 5개 fixture 판정과 current → manifest → 9개 event hash를 직접 읽고 재계산 |
| `MFG_REVIEW_MODE=full make verify-service` | PASS, 실제 HTTP·업로드·거부된 교체·복구·ZIP·재시작; `.cache/file-review-verification/20260910T021724069085Z/receipt.json` |
| 지도 browser oracle full/sample | **14/11개 묶음 PASS**, Chromium 140.0.7339.16; 마지막 실행 02:20:33–02:21:04 UTC |
| 기존 결과 설명 browser full/sample | **18/12개 PASS**, 실제 설명·취소/시간 초과·맥락 변경·삭제·모바일 dialog. 최종 후속 수정은 지도 배치만 변경 |
| 기존 파일 검토 browser full/sample | **11/7개 PASS**, 업로드/거부·이전 결과·복구·빈 구간·브라우저 격리·모바일 |

지도 재현 명령은 `python3 scripts/verify_equipment_map_browser.py --url <loopback server> --mode full`이며,
임의 업로드를 막은 별도 서버는 `--mode sample`을 쓴다. 이번 실행 root는
`.cache/equipment-map-checks/20260910T020802221477Z/`이고 최종 `map-final-full/receipt.json`,
`map-final-sample/receipt.json`, `responses.json`, 실제 ZIP·PNG를 보존한다. 같은 root의
`explanation-full/`, `explanation-sample/`, `browser-full/`, `browser-sample/`은 각 기존 verifier의 실행이다.
각 검사는 자신이 만든 browser workspace만 사용했다. 지도 fixture 삭제도 PASS이며 JS 오류·외부 HTTP 요청은 없었다.

- 실제 공개 샘플 CSV를 별도 `csv.DictReader`와 `statistics.fmean`으로 읽었다. 온도 7,144개,
  평균 55.7481173012318, 최소 44.85, 최대 64.075를 API/화면과 대조하고 ZIP의 전체 행·값·hash·version·조건을 확인했다.
- 지도/목록 선택을 공유하고 새 항목 선택 시 이전 통계·export·설명을 지운다. 날짜 편집만으로 제출 전 조건을
  적용하지 않는다. 실제 전달 누락·복구와 거부된 교체에서 같은 정상 version의 지도/ZIP이 유지됐다.
- 실제 다른 탭의 재검사로 latest attempt 불일치를 만들고 명시적 새로고침을 확인했다. 다른 workspace의 404,
  삭제 뒤 export 404, cookie 없는 query 401은 실제 HTTP다. 무결성 409·일시적 503은 UI 경계용 응답 주입이며,
  서버의 실제 변조/만료는 기존 API·integrity tests가 검증한다. 늦은 응답은 transport abort를 무효화하고 draft 변경
  event를 주입한 반례다. 이를 실제 사용자가 했던 행동이나 장애로 기록하지 않는다.
- 실제 브라우저에서 1440/390/320px 화면과 Tab/Enter/Space·선택 포커스·근거 이동·설명 dialog의 Escape/복귀를 확인했다.
  두 설비/11항목 합성 fixture는 1440/1280/1024/601/600/390/320px의 버튼 경계·선택 외곽선·중심/항목 겹침을 검사했다.
  모든 항목의 목록 접근, 여덟 개 안에 선택 항목 포함, 다른 파일의 같은 이름 분리, 긴 markup 문자열의 비실행도 확인했다.
- Main 화면 검토: 실제 [데스크톱](assets/file-review-equipment-map-desktop.png),
  [390px 모바일](assets/file-review-equipment-map-mobile.png), [이전 정상 결과](assets/file-review-equipment-map-retained.png).
  과거 MetroPT 공개 샘플 화면이며 실공장 상태·합성 다중 설비 화면·실제 사용자 관찰과 혼동하지 않는다.

최종 HTTP에서 내려받은 파일과 checkout bytes가 같았으며 SHA-256은 다음과 같다. health의 revision은 당시
`local-equipment-map-working-tree`였다. 이 digest가 검증한 UI를 특정하며 tag/배포 identity를 대신하지 않는다.

```text
index.html  5bff2f9b5874c2e9b8b17f96cd3a85b00b7e897e19a2d3e43026f714d14bdc15
app.js      5b76fb65c9240e3807e860a174a89211cd56ad0db01638a61a3629828f74d558
styles.css  78f65c1a882277a92ac466adbf128f5cb6d8de434ee447b7d369c46754d5d71a
```

분담 회고: Worker 반환 후 Main의 직접 검토에서 반복 identity 표시를 줄였고, SVG 선과 HTML 노드의 좌표계를 맞췄다.
두 차례 검토 반영 뒤에도 8개 항목의 중심 겹침이 독립 browser oracle에서 실패했다. Main이 조밀한 배치를 보정하고
320px에서 세 항목은 더 짧은 높이를 쓰도록 한 뒤 영향받은 full/sample 지도 검사를 다시 통과시켰다.
Worker의 최초 작업 시작 01:41:05 UTC부터 마지막 반환 완료 02:15:20 UTC까지 약 34분이며 두 검토 반영을 포함한다.
수용 계약 commit 01:39:54 UTC부터 최종 지도 검사 종료 02:21:04 UTC까지 약 41분은 관측 가능한 경과 시간으로,
계약 작성 전 조사나 뒤 문서/로컬 preview 정리는 포함하지 않는다. 확인 가능한 모델별 token·비용은 **UNKNOWN**이다.
이 한 사례로 분담 방식의 보편적 속도·비용 우위를 주장하지 않는다. 제안은 다음에도 구현 반환과 다른 독립 반례를
Main이 검토하되, 경미한 통합 수정을 불필요한 왕복으로 늘리지 않는 것이다. 공통 방법 변경은 하지 않았다.

이번 검사에서 Docker/WSL 조작·원격 조회·외부 AI·push/PR/merge/Release/배포는 하지 않았다.
지도 효용, 세 항목에서 기존 목록보다 빠른지, 물리 건강을 오해하지 않는지와 MFG-09/MFG-12의 독립 과제 관찰은 미검증이다.

<a id="visual-discovery-verification"></a>
## Equipment visual discovery — 2026-09-10

문서 변경 기준은 `feat/review-explanation@794a66c04d77a3a44fb894966c7968d97ce5dbe8` clean이다.
변경은 PROJECT_STATUS·Backlog·workflow research·이 검증 문서 네 곳이다. 제품 source/UI·Contract·설정·의존성·
branch·보존 portfolio artifact를 변경하지 않았다. [조사와 wireframe](research/file-review-workflow.md#equipment-visual-discovery)은
제안이며 구현·사용성 통과·릴리스 근거가 아니다.

- 공개 자료: Grafana node graph/선택 메뉴/state timeline, Cognite Search preview의 공식 게시 이미지 원본을 직접 열었다.
  게시된 데스크톱 화면 관찰이며 제품 로그인·실제 조작·모바일 동작 확인은 아니다. 출처·관찰/공급자 설명/가설은 조사 owner에 있다.
- 로컬 데이터: 번들 CSV를 Python `csv.DictReader`·`Counter`·`hashlib.sha256`으로 직접 읽어
  21,432행, 설비 이름 1개, 세 항목 각 7,144개, 원본 시각 범위·품질 미제공과 provenance hash 일치를 확인했다.
  사용자 원본이나 런타임 DB를 외부로 보내지 않았다.
- `make setup`: PASS, 기존 lock의 39 packages 확인. `make test`: **255 passed / 17 skipped**, 53.78초.
  기존 FastAPI/Starlette deprecation warning 2개. optional runtime skip을 실행 성공으로 세지 않는다.
- `make verify`: PASS. `.cache/telemetry-runs/run-YTuX78aS/`의 5개 fixture 판정과
  `runtime_identity.json`·`readback.json`·current → manifest → 9개 실제 event를 확인했다.
  source/test tree SHA-256 `0e14665094088a7ed07c02744c4273947ab3e11fed074790724a24407c1856fa`로 기존 구현과 같다.
  local OPC UA fixture 검증이며 새 지도나 웹 브라우저 검증이 아니다.
- 최종 문서 상대 경로/anchor 59개·공개 경계·`git diff --check`·변경 경로 검사 PASS. source/UI 변경이 없어 새 브라우저·
  컨테이너·preview 서버는 실행하지 않았다. 기존 MFG-12 화면 검증과 실제 검토자의 미완료 과제 관찰을 구분한다.

새 commit·push·PR·merge·Release·배포·외부 AI 호출은 없다. 다음은 MFG-13 구현 후보에 대한 작성자의 선택이다.

## 기본 환경

Linux, Python 3.10, uv, Bash, Make를 사용한다. OPC UA는 loopback 주소에서만 재생한다.
기본 경로에는 Java, Docker, Kafka, cloud credentials, 전체 MetroPT CSV가 필요하지 않다.

```bash
make setup
make test
make verify
```

- `make setup`: base + OPC UA의 직접·간접 버전을 `requirements-dev.lock`에서 설치한다.
  기존 `.venv`를 지우지 않고 필요한 버전을 맞춘다. 별도로 설치한 optional package는 남으므로
  환경이 달라지면 테스트 collection·skip 수를 다시 확인한다.
- `make test`: 전체 unit/contract suite. Spark·Airflow 등 설치하지 않은 runtime은 skip이다.
- `make verify`: 저장소의 3-row fixture로 OPC UA normal·quality·interrupted collection과
  event-time 5개 시나리오를 실행한다. 매번 새 output root를 만들고 디스크의 trust chain을 다시 읽는다.

uv 없이 설치하려면 Python의 venv/pip를 사용해 같은 lock을 설치할 수 있다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
make test
make verify
```

의존성을 의도적으로 변경할 때만 lock을 다시 만든다. `make setup`은 lock을 갱신하지 않는다.
[uv의 locking/constraints 동작](https://docs.astral.sh/uv/pip/compile/)에 따라 기존 requirement 파일을
입력으로 사용하며 base CI도 같은 lock을 constraint로 적용한다.

```bash
uv pip compile requirements.txt requirements-opcua.txt \
  --python-version 3.10 --universal --output-file requirements-dev.lock
```

## 결과를 직접 확인하기

`make verify`가 출력한 `.cache/telemetry-runs/run-*` 한 곳을 사용한다.

| 파일 | 확인하는 사실 |
|---|---|
| `runtime_identity.json` | 실행 시작 시점의 Git HEAD, dirty 여부, code/test tree hash, 실제 Python/package 버전 |
| `source_collection/reports/` | normal 9/9 Good, quality 9/9 중 Uncertain 1·Bad 1, interrupted 3/9 관측 |
| `source_collection/spool/` | 관측값과 seal; expected/observed identity의 근거 |
| `event_time_verification.json` | 정상·중복/역순·지연·누락·품질의 판정과 버전 |
| `event_time/current_trusted.json` | 현재 manifest를 가리키는 로컬 pointer |
| `event_time/trusted_versions/` | manifest와 실제 trusted JSONL |
| `readback.json` | 저장된 report digest와 current → manifest → data를 재계산한 결과 |

정상과 같은 수집 결과의 중복/역순은 9개 accepted와 같은 version이어야 한다. too-late는
accepted 6·missing 3, missing은 accepted 8·missing 1, quality는 9개가 있어도 차단이다.
실패한 세 시나리오가 기존 current를 바꾸지 않았는지도 검증한다.

기존 실행을 다시 수집하지 않고 읽기만 하려면 `--output-root`를 실제 경로로 지정한다.

```bash
MFG_RUN_DIR=.cache/telemetry-runs/run-XXXXXXXX
PYTHONPATH=src .venv/bin/python scripts/verify_retained_event_time_evidence.py \
  --source-csv tests/fixtures/metropt3/MetroPT3_first_3_rows.csv \
  --expected-sha256 9863d4cdb7fe84bc74458a90e306fb384d9741be389329ddc434a3eacde5e21a \
  --output-root "$MFG_RUN_DIR" --without-spark
```

`--without-spark`는 Spark가 없던 실행을 Python 판정 범위에서 확인하는 옵션이다. 이를 생략하면
기존 명령대로 Spark parity까지 요구한다. 새 replay는 server/collection time이 바뀌므로 이전
실행과 다른 dataset version일 수 있다. 원본 재수집의 멱등성과 혼동하지 않는다.

실패 시 명령은 nonzero로 종료한다. 누락된 의존성은 `make setup`, OPC UA 연결·수집 실패는
출력 로그와 해당 collection evidence, 무결성 실패는 current/manifest/data와 read-back 오류를 본다.
기존 current를 손으로 고쳐 성공시키지 않는다. 생성된 run은 디버깅을 위해 보존하며 자동 삭제하지 않는다.
확인한 run만 경로를 특정해 정리하고, 다음 검증 때 원래 디렉터리를 재사용하지 않는다.

## CI와 optional runtime

| 경로 | 실제 설치·실행 범위 | 증명하지 않는 것 |
|---|---|---|
| base CI | Python 3.10/3.12, `requirements.txt -c requirements-dev.lock`, 전체 suite | skip된 OPC UA·Spark·Airflow 등의 runtime |
| telemetry CI job | Python 3.10, `requirements-dev.lock`, current contract/report tests와 `make verify`에 해당하는 명령 | Spark·Kafka·Iceberg·production |
| 기본 로컬 환경 | base + OPC UA, 전체 suite와 보존된 fixture read-back | optional runtime·실제 공장·외부 사용자 수용 |
| optional Spark | 아래 별도 환경, Spark 3.5.8 file micro-batch parity | Kafka source·Iceberg streaming sink·cluster correctness |

Workflow 파일을 작성했다는 사실은 원격 CI 성공이 아니다. 실제 push된 revision의 job 결과를 별도로
확인한다. 로컬 검사와 독립 reviewer, 외부 사용자 피드백도 서로 대체하지 않는다.

source contract만 별도 실행할 수 있다. 이 기존 명령은 생성한 임시 output을 종료 시 제거한다.

```bash
PYTHON_BIN=.venv/bin/python ./scripts/verify_industrial_source_contract.sh
```

Spark는 기존 base 환경을 유지하려고 별도 optional 환경에서 실행한다. Java 17이 필요하며,
기존 환경이 있다면 삭제·재생성하지 않고 설치 범위부터 확인한다.

```bash
uv venv --python 3.10 .cache/venvs/spark
uv pip install --python .cache/venvs/spark/bin/python \
  -r requirements-dev.lock -r requirements-event-time.txt
PYTHON_BIN=.cache/venvs/spark/bin/python ./scripts/verify_event_time_trust.sh
```

## 보존된 공개 결과와 새 실행

[Trust Report](portfolio/industrial-telemetry-trust/README.md)의 JSON·HTML·PNG는 과거 실행 근거다.
기본 `make verify`는 해당 파일을 바꾸거나 현재 검증 날짜를 덧씌우지 않는다. 보고서 builder는
전체 CSV의 별도 hash와 행 수, retained OPC UA/Spark evidence를 요구한다. fixture 검증만으로
그 보고서를 새로 만들었다고 할 수 없다. 개선은 [MFG-03](BACKLOG.md#mfg-03--public-report-reproduction-without-the-authors-cache)에서 다룬다.

소스 계약·실패 판정·로컬 무결성은 재현 가능한 주장이다. 실제 제조 운영자의 반복 사용,
재처리 실행, downstream 분석 결과, 처리량·SLA·HA·실제 공장 연결은 해당 근거가 생기기 전
미검증으로 둔다. 보존된 full CSV의 행 수를 처리 실적으로 사용하지 않는다.

## Source and consumer research probes

[CSV 원본·업무 조사](research/file-review-workflow.md)의 결과를 제품 코드와 독립적으로 확인하는
선택적 명령이다. Python 표준 라이브러리만 사용하며 현재 trusted dataset을 수정하지 않는다.
전체 source 점검을 위해 [UCI 배포 archive](https://archive.ics.uci.edu/static/public/791/metropt%2B3%2Bdataset.zip)를
`.cache/source-research/metropt3.zip`에 둔다. 다운로드는 약 218 MB이며 기본 setup·test·verify에는 필요 없다.
CSV를 별도로 압축 해제하거나 Git에 추가할 필요도 없다. CC BY 4.0 출처는 [fixture 설명](../tests/fixtures/metropt3/README.md)을 따른다.

다음 명령은 byte identity를 먼저 확인한 뒤 physical order의 인접 시간 차이를 센다. 간격의 원인이나
현실의 관측 완전성은 판정하지 않는다. 숫자가 달라지면 source hash와 계산 범위를 먼저 확인한다.

```bash
python3 - <<'PY'
import collections, csv, datetime, hashlib, io, json, math, zipfile

with zipfile.ZipFile('.cache/source-research/metropt3.zip') as archive:
    name = 'MetroPT3(AirCompressor).csv'
    digest = hashlib.sha256()
    with archive.open(name) as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    expected = 'db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24'
    if digest.hexdigest() != expected:
        raise SystemExit('Different source bytes; do not reuse the recorded profile')
    intervals = collections.Counter()
    invalid = collections.Counter()
    count, previous, largest = 0, None, None
    with archive.open(name) as source:
        for row in csv.DictReader(io.TextIOWrapper(source)):
            timestamp = datetime.datetime.fromisoformat(row['timestamp'])
            count += 1
            if previous is None:
                first = row['timestamp']
            else:
                seconds = int((timestamp - previous).total_seconds())
                intervals[seconds] += 1
                if largest is None or seconds > largest[0]:
                    largest = (seconds, str(previous), str(timestamp))
            for tag in ('TP2', 'Oil_temperature', 'Motor_current'):
                try:
                    finite = math.isfinite(float(row[tag]))
                except (ValueError, TypeError):
                    finite = False
                if not finite:
                    invalid[tag] += 1
            previous = timestamp
print(json.dumps({
    'csv_sha256': digest.hexdigest(), 'rows': count,
    'first': first, 'last': str(previous), 'largest_gap': largest,
    'intervals_9s': intervals[9], 'intervals_10s': intervals[10],
    'intervals_above_60s': sum(n for gap, n in intervals.items() if gap > 60),
    'nonpositive_intervals': sum(n for gap, n in intervals.items() if gap <= 0),
    'nonfinite_selected_values': dict(invalid)
}, indent=2))
PY
```

소비자 기준선은 committed fixture만 사용한다. sample mean과 전달 전 기본 검사만 비교하며 제품의
event-time 정책·멱등성·발행·복구를 재구현하는 검증은 아니다. 중복 행은 이 기준선에서 보수적으로 거부한다.
추가한 quality·누락·중복은 실험 입력이다. 출력의 평균은 소수 셋째 자리로 반올림한다.

```bash
python3 - <<'PY'
import csv, json, sqlite3
from pathlib import Path

fixture = Path('tests/fixtures/metropt3/MetroPT3_first_3_rows.csv')
with fixture.open() as source:
    base = [(i, float(row['Oil_temperature']), 'GOOD')
            for i, row in enumerate(csv.DictReader(source), 1)]
cases = {
    'normal': base,
    'missing_middle': [base[0], base[2]],
    'uncertain_middle': [base[0], (2, base[1][1], 'UNCERTAIN'), base[2]],
    'duplicate_middle': base + [base[1]],
}
for name, observations in cases.items():
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE obs (row_id INTEGER, temperature REAL, quality TEXT)')
        db.executemany('INSERT INTO obs VALUES (?, ?, ?)', observations)
        count, mean = db.execute('SELECT COUNT(*), ROUND(AVG(temperature), 3) FROM obs').fetchone()
        identities = {row[0] for row in db.execute('SELECT DISTINCT row_id FROM obs')}
        bad = db.execute("SELECT COUNT(*) FROM obs WHERE quality != 'GOOD' OR temperature IS NULL").fetchone()[0]
        fit = identities == {1, 2, 3} and count == len(identities) and bad == 0
        print(json.dumps({'case': name, 'count': count, 'sample_mean_c': mean,
                          'basic_checks': 'PASS' if fit else 'REFUSE'}))
PY
```

정상 평균은 `53.625`, 가운데 관측 누락은 `53.600`, 가운데 행 중복은 `53.638`이다.
Uncertain 변형은 평균이 정상이더라도 거부해야 한다. 기본 검사로도 이 차이를 판정할 수 있다는 사실이
새 데이터 플랫폼의 필요성을 입증하지는 않는다. 제품 후보의 복구·전달 업무를 별도로 검증한다.

<a id="file-service-verification"></a>

## File service verification — 2026-09-08

| 검사 | 관측 결과 |
|---|---|
| 전체 Python 3.10.12 suite | 247 passed / 17 skipped. 파일 계약·공개 capability·schema/version·reader-facing claim 포함 |
| 새 clean clone / Python 3.12.3 | `make setup → make test → make verify-service → make verify-container` PASS. 247 passed / 17 skipped; source clean, 작성자 venv/cache 불필요 |
| 파일 서비스 API·저장 반례 | 정상/거부/수정, 동일 원본 재시도, timezone duplicate·quality·unit, 조회 구간, export 전체 행, CSRF·공간 분리, 용량 rollback, 동시 재검사, 만료·삭제, 변조 거부 |
| 실제 HTTP와 서버 재시작 | PASS. Oil_temperature 7,144개 평균 55.74811730123181; 원본을 독립 계산한 값과 일치. ZIP digest·같은 복구 version·재시작 후 이력 확인 |
| release container | clean `1f1a8c1`: Python 3.12.13, 141,710,269 bytes. HTTP/OCI license·release identity, sample upload 거부, UID 10001·read-only root, 21,432개 sample과 volume restart 동일 version PASS; 관측 메모리 49.04MiB |
| 실제 Compose / Chromium 140 | WSL `--env-file` sample mode와 container health 확인. full 11개·sample 7개 UI 시나리오, 1440/390 px, browser isolation, page error 0 |
| dependency advisory | `requirements-service.lock` 13개 package를 `pip-audit 2.10.1`로 조회해 알려진 취약점 0건. base OS scan은 Docker Scout 인증 부재로 미실행 |
| 독립 내부 코드 검토 | 기초 service slice에서 손상 파일이 목록을 막는 문제, 빈 export version, 비 ASCII CSRF 500을 발견·수정. 이번 release runtime 변경의 별도 독립 검토는 미실행 |
| 기존 OPC UA 실제 replay | PASS. 5개 판정 및 current → manifest → data digest chain 확인. `run-SQG1T2la` |
| 외부 CI / 실제 사용자 / 배포 / 장기 운영 | merged `main@2e8e58c`의 [run 34187959052](https://github.com/junhyun-dev/manufacturing-data-platform/actions/runs/34187959052)에서 Python 3.10·3.12, OPC UA read-back, sample container 네 check PASS. 실제 사용자·배포·장기 운영은 미실행 |

당시 clean-checkout 묶음은 `.cache/release-cold-check/8c8868d/receipt.json`이 HTTP와 container receipt를 연결한다.
기존 실행 근거는 `.cache/file-review-tests.log`, `.cache/file-review-final-focused.log`,
`.cache/file-review-verification/<run>/receipt.json`, `.cache/file-review-browser/receipt.json`,
`.cache/file-review-legacy-replay.log`에 있다. 새 체크아웃의 명령·revision·clean 여부는
`.cache/file-review-cold-check/receipt.json`, 실제 HTTP 수치와 source 파일 hash는 같은 디렉터리의
`http-receipt.json`, 전체 출력은 `run.log`에 보존했다. 검증 전용 임시 clone은 근거 보존과 clean 확인 뒤 제거했다. 원본/결과 변조·저장 실패·quota·동시 재시도는 자동 테스트가 실행한다.
브라우저 실행기는 자신이 생성한 파일만 삭제한다. 기존 공개 보고서 JSON/HTML/PNG는 보존했다.

기존 정비 기준 `fbda33d`의 새 clone 검증(210 pass / 17 skipped, OPC UA read-back)은 이전 환경 정비의 근거다.
해당 서비스 결과와 합쳐 과거에 제품 사용까지 검증한 것처럼 쓰지 않는다. 과거 간헐 collection timeout은
[MFG-07](BACKLOG.md#mfg-07--intermittent-local-collection-timeout)에 남아 있다. 이번 replay 성공은 원인 해결이 아니다.
웹 서비스는 해당 OPC UA 수집 경로를 사용하지 않는다.


## Documentation verification — 2026-09-09

조사안 통합 `dd82b75`에서 source/UI 변경 없이 `make setup`, `make test`(248 passed / 17 skipped),
`make verify`를 통과했다. 기존 OPC UA fixture의 5개 판정과 9개 event의 current → manifest → data read-back이다.
명령·시간·출력은 `.cache/chat-discovery-checks/20260909/receipt.json`, read-back은
`.cache/telemetry-runs/run-szNw37UW/readback.json`이다. chat 구현·AI 품질의 검증이 아니며 브라우저/컨테이너를 재실행하지 않았다.

<a id="source-ownership-verification"></a>

## Source ownership verification — 2026-09-09

문서 통합 기준 `ea2c6a6016df6b47e44b42f8b4afa29ae74be0e8`에 Architecture의 Dockerfile/Compose 책임 위치와
current가 없는 거부 상태 설명만 보정한 diff에서 필수 검사를 실행했다. 이후 PROJECT_STATUS·Backlog와 이 절에 종료 결과를 기록했다.
정비 전 `dd82b751df7bc8b2ecfe1953d3778610518ca65f` 대비 변경은 문서 8개와 기존 안내 테스트 1개다.
제품 계약·application code·runtime 설정·보존된 공개 report/JSON/PNG는 동일하다.

| 검사 | 관측 결과와 한계 |
|---|---|
| `make setup` | PASS. 기존 pinned environment의 39개 package 확인 |
| `make test` | 248 passed / 17 skipped, 2개 dependency deprecation warning. 제외된 optional runtime을 성공으로 세지 않음 |
| `make verify` | PASS. OPC UA fixture의 5개 판정과 9개 event; current → manifest → data digest chain 일치 |
| 문서 직접 검토 | 현재 CSV 흐름 → 계약 → app/model/store/query/static → 테스트·날짜별 근거를 추적. Dockerfile/Compose 책임 오기 1건 수정, 이전 current가 없을 때의 결과 없음 명시 |
| 이동·독자 경계 | 상대 링크·문서 fragment 확인, 기존 조사 출처·hash 보존, 공개 주장·라이선스·보존 artifact 접근 검사 유지. 새로운 독립 독자의 이해·실사용 성공을 검증한 것은 아님 |

통합 전 별도 변경분에서 연구 문서 두 개가 없어 실패한 상대 링크 검사는 통합한 전체 suite에서 통과했다.
필수 검사는 통합 뒤 한 번 실행했다. 명령·시각·원본 출력은 `.cache/doc-ownership-checks/20260909/receipt.json`,
실제 read-back은 `.cache/telemetry-runs/run-Nv0Rti14/readback.json`에 보존했다. trusted version은
`14f9517711ca8a9becab147ca74670a2451dadbcc59b2f181e2254c4df59ff82`다.

이번 실행은 문서 통합과 기존 fixture의 근거다. 새 HTTP/브라우저/container·원격 CI·chat/AI·사용자 수용·공개 배포는
확인하지 않았다. 기존 서비스 runtime의 마지막 관측은 위 2026-09-08 절과 구분한다.

<a id="guided-explanation-verification"></a>

## Guided explanation verification — 2026-09-09

MFG-12는 실제 검토 결과에 대해 선택한 세 질문을 규칙으로 설명하는 로컬 기능이다. 계약 `e9e11c0`,
구현 통합 `5d3bceae9a7685a671d73b0b8925f93847d88fda`에 아래 직접 검토 보정을 적용한 source에서 실행했다.
각 receipt에 당시 HEAD·dirty와 파일 SHA-256을 남겼다. 표시된 runtime revision만으로 clean artifact라고 주장하지 않는다.
검증 뒤의 상태·backlog·이 기록과 촬영본 추가는 runtime 변경이 아니다.

| 검사 | 관측 결과와 한계 |
|---|---|
| `make setup` | PASS, pinned 39개 package 확인. 새 제품 의존성·AI 공급자 없음 |
| `make test` | 255 passed / 17 skipped, 50.52초 pytest. 기존 optional runtime 17개 제외와 dependency 경고 2개를 보존 |
| `make verify` | PASS. 기존 OPC UA fixture 5개 판정·9개 event; current → manifest → data를 실제로 읽고 세 digest 대조 |
| `make verify-service` | PASS. 실제 HTTP·잘못된 교체·보관 입력 복구·ZIP read-back·재시작 보존. Oil_temperature 7,144개와 독립 평균 대조 |
| 새 설명 API | 기존 snapshot/query 재사용과 숫자의 독립 기대값, 원본/버전, 조회 상태 불변, 빈 구간·이전 결과·stale latest·다른 공간·삭제/만료·손상 거부. [API 검사](../tests/test_file_review_explanation.py)가 전체 suite에 포함됨 |
| 새 설명 브라우저 | Chromium 140.0.7339.16, full 18개 / sample 12개 시나리오 PASS. 1440/390/320px, 질문/근거 이동, 미제출 필터, inert label, 교체 실패, 다른 탭 변화, 삭제, 새로고침, 취소/시간 초과/재시도와 늦은 응답 거부 |
| 기존 브라우저 회귀 | 같은 최종 application source에서 full 11개 / sample 7개 시나리오 PASS. 두 프로필 모두 page error·외부 HTTP 요청 0건 |

직접 diff·브라우저 검토에서 질문 버튼 비활성화 시 모바일 포커스가 패널 밖으로 빠지는 결함을 보정했다.
시간 초과는 transport abort와 별도로 요청 세대를 무효화하도록 수정했으며, abort가 실제로 작동하지 않도록 주입한
브라우저 검사에서도 늦은 답변을 거부했다. 기존 삭제 확인창의 Escape를 먼저 처리하고, 차단된 파일은 완료된 거부 판정임을
설명 문구에 반영했다. 반환된 구현 요약이나 같은 API 테스트 재실행만으로 수용하지 않았다.

고정 패널 화면은 full-page 캡처의 위치 왜곡을 피하기 위해 실제 viewport로 촬영하고 눈으로 확인했다.
[데스크톱](assets/file-review-explanation-desktop.png)과 [모바일](assets/file-review-explanation-mobile.png)은 아래 최종
sample 실행에서 복사한 동일 bytes의 공개 샘플 화면이다. 독립 사용자의 이해·보조기술·모바일 실기기 검증은 아니다.

로컬 원본 실행 근거:

- 필수 검사: `.cache/review-explanation-final/20260909T082330536312Z/receipt.json` 및 명령별 log.
- 설명 최종 화면/반례: `.cache/review-explanation-checks/20260909T082210446042Z/receipt.json`과
  각 `full-explanation`/`sample-explanation`의 responses·ZIP·화면·receipt.
- 기존 브라우저와 첫 보정 후 설명: `.cache/review-explanation-checks/20260909T081551529359Z/receipt.json`.
  이후 application source는 동일하며 새 설명 verifier의 삭제 Escape 검사·viewport 촬영만 보완했다.
- 최초 실패: `.cache/review-explanation-checks/20260909T081310332448Z/receipt.json`의 모바일 포커스 오류.
- HTTP·재시작: `.cache/file-review-verification/20260909T082430582585Z/receipt.json`.
- OPC UA: `.cache/telemetry-runs/run-s7eLULEu/readback.json`, trusted version
  `c83fd83810d4afebc783edff0de3216683d091eb52e39c6282ab59b0713529e3`.

위 검증 시점의 source는 로컬 branch에만 있었다. 이후 승인된 작업 브랜치 백업과 제품 배포를 구분한다.
새 container·remote CI·tag·Release·배포는 이 검증에서 실행하지 않았다.
브라우저는 loopback의 새 DB와 자기 workspace를 사용했고 생성한 파일을 지운 뒤 해당 서버를 종료했다.
실제 AI 호출·자유 대화·공급자 보관/원가·AI 답변 품질은 이번 검사 범위 밖이다.

<a id="map-fullscreen-verification"></a>
## Dedicated map fullscreen — 2026-09-10

**LOCAL VERIFIED / NOT RELEASED.** Source `d33ed90b33b10c5c222f00e8dc20a499f304c440`, accepted scope
`aa4469e`, Worker preservation `ee38485`. [Contract](FILE_REVIEW_CONTRACT.md#dedicated-map-fullscreen) owns
the display rules. Main reviewed the actual diff and corrected browser findings before the final runs.
No API/schema/dependency or graph meaning changed; no push, Release or deployment was performed.

Evidence root: `.cache/map-fullscreen-checks/20260910T085310661532Z/`. The final
`full-native-final4/receipt.json` and `sample-final2/receipt.json` verify the four served static files against
the integrated source bytes. `final-checks.json` links these results; earlier failed runs remain visible.

| Actual check | Result |
|---|---|
| Dedicated map browser, full / sample | **9 / 7 groups PASS**, Chromium 140.0.7339.16; independent public CSV count/mean and same-version ZIP/digests |
| Real map viewport, 1440×900 | **1402×627px**, 97.4% width / 69.7% height; previous document fullscreen was only 38.7% width |
| Real map viewport with desktop scrollbars, 390×844 / 320×844 | **361×464 / 291×464px**, 92.6% / 90.9% width, both 55.0% height; ordinary headless view has more usable width |
| Native window | Actual entry/button exit/system Esc, prior wide/native state, open explanation answer/focus, 200% browser zoom and actual exit click PASS |
| Static boundary | Both JS syntax checks, whitespace, 127 unique DOM IDs / 94 literal app references and safe text rendering PASS |
| Documentation | Reader tests **43 passed / 0.07s**; relative file targets and added private-path/secret-pattern checks PASS |

The browser oracle is [verify_map_fullscreen_browser.py](../scripts/verify_map_fullscreen_browser.py).
Run it against an owned full or sample loopback server with `python3 -B scripts/verify_map_fullscreen_browser.py
--url http://127.0.0.1:8000 --output .cache/map-fullscreen-check-<fresh-name>`. The optional native run uses
`MFG_NAV_X11_TEST=1 xvfb-run -a -s '-screen 0 1920x1080x24'` before that command and adds `--native-desktop`.
It needs the existing Playwright/Chromium, Xvfb/XTest and Pillow test environment, not an application dependency.
Native window bounds were set explicitly; Xvfb has no window manager, so automatic OS sizing and all real devices
remain unverified. At 200%, the final oracle captures the settled owned display before browser surface capture,
which could crop/repaint the frame. `native-map-200-percent-display.png` shows the reachable exit and evidence actions.

The same map and question-launcher DOM return to their original parents. Camera/mode actions preserve draft and
submitted ranges, result/version and ZIP without an API request. Tests hold a genuine query while entering/exiting;
inject unsupported/denied/exit-failure and delayed entry; check modal Escape, guided/source focus, and delete only
their own fixture through the actual confirmation handler while an entry is pending. A late Promise cannot leave
the map or transition lock behind. Actual 3-item MetroPT data and synthetic 200-item/128-character labels are distinct.

Main's browser findings were a covered skip link, a scrolled-away exit, clipped 320px canvas, and a floating question
button blocking the review return. The fixes hide the covered shortcut, keep the header sticky, account for scrollbars,
and place the same question launcher in the map header. Oracle corrections addressed function injection, the existing
delete-button ID and CSP-safe wait predicates; none relaxed data identity or the viewport thresholds.
The earlier full repository/OPC UA checks were not repeated for this display-only change. MFG-02's historical
intermittent failures and MFG-09/12's independent human task observations remain OPEN.

Collaboration evidence: Worker ran 08:53:07–09:27:55 UTC (34m48s), then returned the bounded pre-review fixes by
09:33:04. Main owned the contract, independent browser checks and integration. Static CSS arithmetic did not expose
scrollbar/focus/overlay defects; direct browser review added different evidence. Main verification spans the morning
and a 12:30 UTC resumption; the former fixture processes were no longer running and were replaced with owned local
servers. The cause and pure working time are unmeasured; elapsed wall time includes waiting and cannot be treated as
execution time or a speed comparison. Token/cost usage is UNKNOWN. A useful next trial is an earlier frozen UI return
followed by one batched browser review, to reduce waiting and handoff retries; the common method is unchanged.

Final preview read-back at **12:43:33 UTC** uses the preserved sample database and source `d33ed90` at
`http://127.0.0.1:8000`. `.cache/map-fullscreen-preview/20260910T124229287203Z/readback.json` verifies health,
commit/served bytes, map bounds, source focus and the independent 7,144-value Oil_temperature ZIP. Only the check's
own workspace fixture was deleted. [Desktop](assets/file-review-map-fullscreen-desktop.png) and
[390px](assets/file-review-map-fullscreen-mobile.png) are actual public-sample captures; [Project Status](../PROJECT_STATUS.md)
owns the current pointer. Local process survival after a PC/environment restart is not guaranteed.

<a id="graph-canvas-verification"></a>
## Graph canvas local verification — 2026-09-10

**LOCAL VERIFIED / NOT RELEASED.** 수용 계약 `2214e5b`, 의도 정정 보존 `c6e3b5e`, 이전 UI
`743bebd`/closeout `984d875`에서 이어졌다. Worker의 네 정적 파일을 `c6cf793`에 보존한 뒤 Main이
직접 diff·화면·반례를 검토하고 통합했다. 최종 source는 `b18366bb37a34e0c7fdc03e21cc30ac5bb11f1c3`이며
[현재 작업](../PROJECT_STATUS.md)이 preview read-back을 연결한다. 원격 push/merge/Release/배포는 하지 않았다.

검증 루트는 `.cache/graph-canvas-checks/20260910T070532326883Z/`다. 아래 이름은 그 하위 경로이며
브라우저별 `receipt.json`과 스크린샷을 보존한다. `browser-matrix.json`은 실제 PASS 영수증을 읽고
제공된 정적 파일의 SHA-256을 최종 checkout bytes와 대조한 결과다. 당시 HEAD는 `2214e5b` + dirty였다.

| 실제 실행 | 결과·근거 |
|---|---|
| `make setup` | PASS, 기존 lock 기준 39 packages 확인; 새 그래프 dependency 없음 |
| `make test` | **255 passed / 17 skipped**, 45.21s. optional runtime 건너뜀과 기존 deprecation warning 2개 유지 |
| `make verify-service` | PASS, 실제 HTTP·독립 CSV/ZIP·전달 누락/복구·재시작; `.cache/file-review-verification/20260910T075214618604Z/receipt.json` |
| `make verify` | PASS, `.cache/telemetry-runs/run-S99AS9qQ/`; 5개 판정과 current → manifest → 9개 event의 세 파일 digest를 직접 재계산 |
| 새 canvas full/sample | **9/6개 묶음 PASS**, `canvas-full-final3/`, `canvas-sample-final2/` |
| 기존 navigation full/sample | **13/10개 묶음 PASS**, `navigation-full-final/`, `navigation-sample/` |
| 기존 map full/sample | **14/11개 묶음 PASS**, `map-full-final3/`, `map-sample/` |
| 기존 explanation full/sample | **18/12개 묶음 PASS**, `explanation-full/`, `explanation-sample/` |
| 기존 file browser full/sample | **11/7개 묶음 PASS**, `file-full/`, `file-sample/` |
| 정적·문서 경계 | 두 JS의 `node --check`, diff 공백 검사 PASS. 변경 문서의 상대 링크 190개 존재 확인·private path/secret 형식 검사, reader tests **43 passed / 0.06s** |

[Canvas oracle](../scripts/verify_graph_canvas_browser.py)은 1440/390/320px·가로 화면, 실제 키보드 선택,
배경 drag/Escape/pointercancel, 미니맵 실제 click 좌표, 최대 확대 후 선택 위치, 전체 맞춤, 접고 펼치기와
그룹/항목 페이지를 확인한다. 늦게 도착한 실제 query를 보류했다가 반환해도 카메라·그룹·검색 조작은 그 결과를
취소하거나 다른 요청을 만들지 않는다. 같은 이름의 다른 설비 선택과 내부 group key 충돌 문자열도 대조했다.

실제 MetroPT 샘플은 1묶음/3항목·21,432행이며 Oil_temperature 7,144개의 평균·극값·source hash와 ZIP을
독립 CSV에서 재계산했다. 합성 8/11/50/200/205항목, 25묶음, 128자/markup 이름은 별도 업로드다.
최대 200개 노드 표시와 페이지 전체 접근을 확인했으며, 이는 production 처리량·실제 공장 규모가 아니다.
실제 공개 샘플의 전달 누락/복구·기존 버전 보호와 실제 workspace 권한 거부를 확인했다. 주입한 503/무결성
응답은 영수증에서 주입 사례로 표시하며 실제 서버 장애가 발생한 것으로 기록하지 않는다.

navigation의 별도 Xvfb 창에서는 Chromium 140의 native fullscreen/Escape, 설명·삭제 dialog 포커스와 inert,
실제 browser zoom 200%를 확인했다. 창 크기는 CDP로 명시 조정했다. 창 관리자가 없는 Xvfb이므로 OS의 자동
전체화면 크기 조정이나 모든 브라우저·모바일 기기의 동작까지 검증했다고 주장하지 않는다.

직접 화면 검토 후 선택 복귀는 기본 100%로 읽게 했고, 320px에서 이전 200% 배율 때문에 노드가 잘리면
그 노드가 들어오는 배율로 낮춘다. 미니맵의 SVG 영역과 버튼 border를 분리해 좌표를 맞췄으며 작은 3항목은
세로로 배치했다. [공개 샘플](assets/file-review-canvas-desktop.png) · [390px](assets/file-review-canvas-mobile.png) ·
[합성 200항목 확대](assets/file-review-canvas-synthetic-200.png)는 실제 로컬 캡처다. 마지막 그림은 별도 합성
400행/200항목 파일이며 `temperature-042`의 두 값 24.2/26.2, 평균 25.2를 보여준다. `screens/receipt.json`에 경계를 남겼다.

검증 도중 oracle 자체의 프레임 간 좌표 혼합, float의 완전 일치 비교, route callback 인자, 반응형 접힘 대기와
MouseEvent 좌표 반올림을 수정했다. 실제 DOM의 같은 프레임/전달된 click을 기준으로 판정하고 독립 CSV 값,
오차 허용과 거부 조건은 유지했다. 실패 영수증은 같은 루트에 보존하며 마지막 PASS로 과거 실패를 지우지 않는다.

분담 관찰: Worker는 별도 checkout의 네 파일만 작성했고 Main은 계약·독립 oracle·직접 통합을 맡았다.
Worker 실행은 UTC 06:55:57–07:27:48이며 쓰기 동결 후 통합했다. Main의 pre-review는 key 충돌, drag 취소,
페이지 끝 포커스와 같은 설비의 검색 유지 보완으로 이어졌다. Main 브라우저 검토는 좁은 화면의 선택 크기와
미니맵 좌표를 추가로 보완했다. 이 방식은 소유 경계를 분명히 했지만 oracle 조정·화면 재검토 시간이 들었다.
첫 보존 commit 06:52:47부터 preview read-back 08:00:25까지 확인 가능한 경과는 **67분 38초**다.
실제 작업 시작 계측은 없고 Worker와 Main 시간은 겹치므로 합산하지 않는다. 정확한 token/금액 사용량은
UNKNOWN이다. 모델별 비용/속도 우월성이나 분담의 순수 시간 절감을 입증하는 비교 실험은 아니다.
다음 검토에서는 실패 시 실제 DOM 좌표·전달된 입력을 바로 기록해 oracle 진단의 왕복을 줄이는 것을 권한다.
공통 방법을 변경하지 않고 이번 구체적 검토 근거와 제안만 보존한다.

최종 로컬 샘플 preview는 `.cache/graph-canvas-preview/20260910T075938407126Z/`에 기록했다.
기존 DB를 유지하고 `b18366b`/sample health, 네 정적 파일 bytes, 실제 지도/넓게 보기, 독립 온도 집계와 ZIP을
새 브라우저 작업 공간에서 확인했다. `readback.json`의 시각은 08:00:25 UTC이며 그 검수용 데이터만 삭제했다.
공개 서비스·OS 재시작 후 생존을 보장하는 배포가 아니다.

**남은 한계:** 이번 전체 검사 성공은 과거 OPC UA timestamp-order 검사 2건의 간헐 실패 원인을 해결한 것이
아니다(MFG-02 OPEN). MFG-09/12의 독립 사용자 과제도 그대로 미완료다. 합성 200항목에서는 선이 많이 겹치고
전체 맞춤은 이름을 읽는 화면이 아니다. 검색·목록·선택 위치가 실제 사용자에게 유용한지, 표시 예산을 바꿔야
하는지는 실제 과제로 확인한다. 현장 topology·설비 건강·사용성 향상·Production 용량·공개 제공을 주장하지 않는다.


<a id="opcua-time-order-investigation"></a>
## OPC UA time order — 2026-09-10 investigation

**LOCAL VERIFIED — diagnostic correction; clock/host repair remains unverified. NOT RELEASED.** Baseline `5d2428243b62707daea33717d9657982b81d9f32`,
local branch `fix/opcua-time-order`, source `a86195b33f37391d2c04ff43b74642f65bdae5d2`, Worker preservation `87a9548`. This maintenance is separate from the CSV/map preview and MFG-09/12 human observation.
The accepted boundary is the existing strict `collected_at >= server_timestamp` check; source timestamps, arrival order,
canonical observation bytes and replay identity are unchanged. The bounded correction improves diagnostics without accepting previously refused observations.

Evidence root: `.cache/time-order-checks/20260910T141713020479Z/`. `baseline.json` and `investigation-summary.json` retain
source/dependency hashes and the SHA-256 of the earlier `make-test-serial.log`; that earlier log contains no failed clock pair.
The unchanged dependencies are Python 3.10.12 and asyncua 2.0.1. `probe.py` observes runtime clock calls and delegates to
the original spool/validator unchanged. It writes only fresh fixture evidence; no system clock, service or database settings change.

| Observation | Evidence and interpretation |
|---|---|
| Original two tests, three bounded runs | `probe.log`, `second.log`, `third.log`: **2 passed** each, 42 collected observations per run, 20.97/20.16/19.44 seconds respectively. These passes do not erase the earlier failure. |
| Execution clocks | `observed.json`, `second/observed.json`, `third/observed.json`: wall time changed by roughly -0.48 to -0.51 s relative to monotonic elapsed intervals. The readings are observations, not an OS/WSL diagnosis. |
| One longer normal replay | `stress.log`, `stress/{observed,summary}.json`: a **synthetic 600-row repeated-value fixture**, not additional real plant data. The unmodified collector failed at row 32: 94 accepted, two refused. No seal or last-good report was created. |
| Exact failure boundary | Runtime wall time changed from `14:20:48.087203` to `14:20:42.225999` while monotonic time advanced 17.288569 ms. Refused server/collection pairs were `14:20:48.083669Z` / `14:20:42.225999Z` and `.083830Z` / `.226190Z` on 2026-09-10. |

The reproduced failure is an actual backward execution-clock reading across delivery. It is not a guessed CSV timezone,
lexicographic comparison or serialization-rounding error. The validator parses aware datetimes; the installed asyncua
FILETIME conversion uses integer microseconds, and the server can replace ServerTimestamp with its own wall-clock read.
The four captured timestamps also round-trip exactly through the installed asyncua binary DateTime codec
(`serialization.json`). The historical two failures have the same error path, but their missing timestamp values prevent
attribution of each past occurrence. The source of the host clock jumps remains UNKNOWN and is outside this task's environment permissions.

The narrow correction retains exact validated server/collection timestamps and a signed integer microsecond difference
in the existing error, plus deterministic regression cases. It must keep equality valid and refuse even a 1 μs inversion;
it must not manufacture UTC from monotonic time, clamp values, widen tolerances or skip a failing case.
The independent read-only investigation identified the non-monotonic execution clock as a hazard. Main distinguishes this
from a defective validator: refusal is correct for the accepted raw timestamp contract. A monotonic-derived replacement UTC
would change observation meaning and is not accepted. The raw clock regression is reproduced; host synchronization behavior
and a host repair are not investigated here.

Main's `baseline-readback.json` rechecks the retained real 3-row replay's five decisions, 9 trusted events and current →
manifest → data hashes. Two captured invalid events are refused at the downstream arrival boundary as well; all 37 retained
files remain byte-identical. This is a read-only integrity check, not a new collection success or a recovery implementation.
Main reviewed the frozen two-file diff directly and integrated identical bytes (`worker-final.patch`, `integration.json`).
The source change is only the existing rejection message in `industrial_source/contracts.py`; integer timedelta arithmetic
adds `delta_microseconds` with the original timestamp strings. The strict comparison, producer, schema, serializer and
successful observation bytes are unchanged. The prior negative test is replaced by stronger -1 μs and captured-pair cases.

| Integrated verification | Result |
|---|---|
| Worker deterministic regressions | Reported RED on original code: 4 failed / 4 passed; GREEN: 8 passed. Its wider non-network selection: 17 passed / 2 deselected. These are Worker-reported execution results; Main reviewed the actual test oracles. |
| Main affected modules | `integrated-tests.log`: **37 passed in 32.78 s**, including both original real-loopback scenarios, exact diagnostic cases, actual callback refusal and existing spool failure propagation. Fresh fixture root `integrated-tests/`. |
| Main independent captured-pair and read-back | `integrated-readback.json`: both invalid arrivals remain refused with exact -5,857,670 / -5,857,640 μs diagnostics; all 37 retained files and 9-event trusted chain match `baseline-readback.json`. |
| Documentation and scope | Reader checks: **43 passed in 0.08 s** (`reader.log`); changed-link targets, source diff and whitespace checked. No web service, UI, dependency, preview process or user database changes. |

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  --basetemp .cache/time-order-checks/20260910T141713020479Z/integrated-tests \
  tests/test_industrial_source_contract.py tests/test_event_time_trust.py
```

The command above records the executed directory; use a fresh `--basetemp` for another run so pytest cannot remove this
retained evidence. No whole repository, browser, setup/install or extra replay loop was required for an error-message-only
change. The real clock remains capable of producing valid refusal: a passing bounded replay is not a clock repair or a
closed historical whole-suite gate. Future failures now expose the operands; deciding why a clock moved still requires
separate observed clock evidence. No routine monotonic telemetry or new raw-data logging was added to the product.

Collaboration record: Worker read-only investigation reported 14:17:16–14:24:52 UTC, addendum completed 14:28:11, and
bounded implementation 14:30:12–14:34:59. Clarification and implementation rework were 0. Main independently captured the
real failure, adjudicated timestamp meaning, reviewed the diff and verified the integration. Three queued task/evidence
messages were processed sequentially; the useful technical work overlapped, but intermediate returns added handoff waiting.
Recommendation: send the completed reproducer with one bounded implementation request when available, keeping a separate
read-only review only when it adds a different counterexample. This is a local recommendation, not a common-method change.
Main's first retained checkpoint is 14:17:13 UTC; `closeout.json` records the end. UTC moved backwards during this work,
so their wall-time difference is not a reliable active-work duration. Pytest durations above are command measurements;
model token/compute usage and monetary cost are UNKNOWN. Existing session/model settings were preserved.

Remaining decision: host clock diagnosis/repair needs a separately authorized environment task. This result does not alter
MFG-02 source-recollection identity, MFG-07's earlier timeout investigation, or MFG-09/12 independent user observation.
No Docker/WSL/system settings, other project services, remote Git, public release or deployment were changed.
