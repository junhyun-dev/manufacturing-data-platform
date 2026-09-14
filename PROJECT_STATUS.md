# Manufacturing — 현재 작업

현재 단계·기준 revision·다음 행동은 이 파일이 소유한다. 제품 약속은 [File Review Contract](docs/FILE_REVIEW_CONTRACT.md),
작업별 범위는 [Backlog](docs/BACKLOG.md), 실행 방법·날짜별 근거는 [Verification](docs/VERIFICATION.md)이 소유한다.

| 항목 | 현재 값 |
|---|---|
| 현재 작업 | MFG-14 결과 전달 경험 LOCAL VERIFIED, 2026-09-14. 같은 조회의 한국어 요약과 CSV/JSON 근거를 함께 전달한다. MFG-02 공유 시계 교정은 승인 대기로 보존 |
| 수용한 범위 | [MFG-14](docs/BACKLOG.md#mfg-14--portable-review-handoff), [전달 계약](docs/FILE_REVIEW_CONTRACT.md#portable-review-handoff). 기존 버전·선택·구간·계산·권한을 유지하는 표시/첨부 요약. 공유 시계·환경·외부 행동은 변경하지 않는다 |
| Git 기준 | `feat/review-handoff`, 계약 `9524bde`, 구현·검사 `99e2454c192ac23129e38a53921bc5300506c526`; 기존 시계 진단 `a86195b`/지도 `d33ed90`. 2026-09-14 사용자 승인 백업 ref는 `origin/feat/review-handoff`. 실제 HEAD/dirty·원격 SHA는 Git에서 확인. merge/Release/배포 없음 |
| 기존 제품 | CSV 검토·구간 분석·교체·근거 ZIP과 공개 샘플 보관 입력 복구. 코드 병합 `2e8e58c346d0eaec0722cdaba83f9a576e70d68e` |
| 외부 확인 | 2026-09-09 원격 `main@c4b3814` 유지 확인. 2026-09-08 [PR #1](https://github.com/junhyun-dev/manufacturing-data-platform/pull/1) squash MERGED와 [CI 4/4 PASS](https://github.com/junhyun-dev/manufacturing-data-platform/actions/runs/34188251022)는 기존 근거. 작업 브랜치 백업은 새 PR·원격 CI 통과·Release·배포를 의미하지 않음 |
| Release·운영 | NOT TAGGED / NOT RELEASED / NOT DEPLOYED. tag·GitHub Release·배포는 별도 최종 승인 대상 |
| 다음 한 행동 | 실제 검토자가 전달 누락 체험 뒤 ZIP만 보고 온도 결과의 구간·이전 버전·원본 근거를 설명할 수 있는지 관찰한다(MFG-09/12). [MFG-02 교정안](docs/VERIFICATION.md#clock-layer-diagnosis)은 별도 승인 대기 |

## 실행과 근거

- 2026-09-14 [전달 경험 검증](docs/VERIFICATION.md#portable-review-handoff-verification): 한국어 `review.txt`와 전달 카드 추가.
  API/무결성 **41 passed**, 실제 browser full/sample **8/5개 묶음 PASS**. 독립 CSV·요약·manifest 대조, 날짜 초안·이전/빈 결과,
  1440/390/320px·키보드·긴 이름·실제 삭제 후 다운로드 거부를 확인했다. [데스크톱](docs/assets/file-review-handoff-desktop.png) ·
  [390px](docs/assets/file-review-handoff-mobile.png). 사용자 전달 시간·과제 성공은 미측정이다.
- 2026-09-11 KST [커널 호출·시각 보정 대조와 교정안](docs/VERIFICATION.md#clock-layer-diagnosis):
  별도 C 프로세스 두 개에서도 같은 UTC 역행을 확인했다. 커널 `tick=11000`과 보정 전 시계 대비 약 1.1배의 속도가 일치하며,
  네 번의 뒤로 이동은 NTP 보정량과 각각 1μs 이내로 맞았다. 앞으로 이동하는 경로는 호스트 동기화가 유력하지만 호출 주체는 미확정이다.
  공유 시계 설정을 바꾸거나 과거 실패·전체 검사·사용자 효용을 완료 처리하지 않았다.
- 2026-09-11 KST 격리 진단: 앱·site packages·Python 환경 변수를 배제한 Python 3.10/3.12 두 프로세스의
  20초 관측에서 각각 네 번의 UTC 역행을 같은 경과 시간 구간에 확인했다. [격리 경계와 근거](docs/VERIFICATION.md#clock-process-isolation).
  개별 가상환경만으로 공유 UTC 시계가 분리되지 않음을 확인한 것이며, 호스트 근본 원인이나 교정 완료는 아니다.
- 시각 실패 조사·진단 보강: [MFG-02 실행 근거와 한계](docs/VERIFICATION.md#opcua-time-order-investigation).
  실제 UTC가 약 5.86초 역행한 수집 실패를 재현했다. 기존 순서 검증은 유지하고 오류에 두 시각·정수 μs 차이를 추가했다.
  통합 후 industrial-source/event-time 검사 **37 passed**(32.78초), 기존 발행 파일 37개·9개 event의 hash read-back은 동일하다.
  전체 저장소/브라우저 재검사를 반복하지 않았으며 과거 두 실패의 정확한 시각·호스트 근본 원인은 미확인이다.
- 로컬 샘플 미리보기 **http://127.0.0.1:8000**. **공개 샘플 열기 → Oil_temperature 선택·조회 → 이 조회를 전달하기**에서 ZIP을 연다.
  2026-09-14 `sample`/source `99e2454`로 기동했다. 이전 preview 프로세스가 없는 것을 확인하고 이번 작업의 새 DB를 사용했으며
  기존 사용자 DB는 변경하지 않았다. 실행/검수 기록은 `.cache/handoff-checks/20260914/sample-server-final.json`과
  `preview-readback.json`. 이 주소는 로컬 프로세스이며 PC/환경 재시작 뒤 자동 복구를 보장하지 않는다.
- 지도 전용 전체화면: [검증·직접 보완·분담 관찰](docs/VERIFICATION.md#map-fullscreen-verification).
  full/sample **9/7개 묶음 PASS**. 실제 지도 폭은 1440px에서 97.4%, 스크롤바가 있는 320px에서도 90.9%다.
  실제 native Esc·200% 확대와 종료 클릭, 설명/삭제 dialog, 지연 응답·진입 실패·동일 버전 ZIP을 확인했다.
  [공개 샘플 전체화면](docs/assets/file-review-map-fullscreen-desktop.png) · [390px](docs/assets/file-review-map-fullscreen-mobile.png).
- 새 graph canvas: [검증·분담 관찰·한계](docs/VERIFICATION.md#graph-canvas-verification).
  canvas full/sample 9/6, navigation 13/10, map 14/11, explanation 18/12, file browser 11/7개 묶음 PASS.
  실제 3항목 샘플과 합성 50/200/205항목·25묶음을 구분했다. 모바일/키보드·native Esc·200% browser zoom,
  선택/버전/제출 구간/동일 ZIP과 실패 경로를 확인했다.
  [공개 샘플 화면](docs/assets/file-review-canvas-desktop.png) · [390px](docs/assets/file-review-canvas-mobile.png) ·
  [합성 200항목 확대](docs/assets/file-review-canvas-synthetic-200.png).
- 새 탐색: [수용 범위·검증과 한계](docs/VERIFICATION.md#review-navigation-verification). full/sample 13/10개 묶음,
  기존 지도 14/11·설명 18/12·파일 화면 11/7 PASS. 실제 browser Esc·200% 확대·모바일/키보드·동일 ZIP 확인.
  [넓게 보는 화면](docs/assets/file-review-navigation-desktop.png) · [390px 검색/목록](docs/assets/file-review-navigation-mobile.png).
- 전체 검사: 직전 canvas의 단독 `make test`는 **255 passed / 17 skipped**. 당시 실제 HTTP·재시작 및 OPC UA 한 replay도 PASS.
  이전 navigation의 2 failed / 253 passed / 17 skipped는 간헐 시각 문제의 원인이 밝혀지지 않아 MFG-02 OPEN으로 유지한다.
  그 한 실행의 성공을 과거 실패 해결이나 전체 Release gate 종료로 바꾸지 않는다. 이번 표시 개선에서는 영향 범위의
  브라우저·정적·문서 검사를 수행했으며 전체 저장소 검사를 반복하지 않았다.
- 이전 지도 구현(`45512b6`) 기록: [MFG-13](docs/BACKLOG.md#mfg-13--equipment-data-map-discovery), [당시 지도 검증](docs/VERIFICATION.md#equipment-map-verification).
  당시 필수 검사 PASS, 255 passed / 17 skipped, 지도 full/sample 14/11개 묶음·기존 설명 18/12·기존 화면 11/7 PASS.
  실제 [데스크톱](docs/assets/file-review-equipment-map-desktop.png) · [모바일](docs/assets/file-review-equipment-map-mobile.png).
- 방향 근거: [공개 화면·wireframe·데이터 제약](docs/research/file-review-workflow.md#equipment-visual-discovery), [문서 검사](docs/VERIFICATION.md#visual-discovery-verification).

```bash
make setup
make serve
# http://127.0.0.1:8000
# 공개 샘플만 여는 별도 로컬 서버는 대신:
# MFG_REVIEW_MODE=sample MFG_REVIEW_DB=.cache/equipment-map-preview/review.sqlite3 make serve
```

[사용법](docs/FILE_REVIEW_GUIDE.md)은 full/sample 실행과 첫 사용자 흐름을 안내한다. `full`은 자기 CSV를 받는 로컬 흐름,
`sample`은 임의 업로드를 서버에서 거부하는 체험 후보다. 한 프로세스·SQLite이고 계정·팀 공유·현장 연결은 없다.
[Architecture](docs/ARCHITECTURE.md)에서 현재 서비스와 별도 OPC UA 실험의 책임 경계를 확인한다.
지도는 같은 파일 버전의 설비 이름–측정 항목 소속만 표현한다. 온톨로지·공장 topology·고장 진단으로 주장하지 않는다.

- 기존 서비스: [2026-09-08 검사·실제 HTTP/브라우저·clean checkout·컨테이너 기록](docs/VERIFICATION.md#file-service-verification).
- 이번 설명 기능: [MFG-12 검증](docs/VERIFICATION.md#guided-explanation-verification). 255 passed / 17 skipped,
  실제 HTTP·재시작·ZIP과 full/sample Chromium 검증. [데스크톱](docs/assets/file-review-explanation-desktop.png) ·
  [모바일](docs/assets/file-review-explanation-mobile.png)은 실제 공개 샘플 화면이다. 별도 API key 설정은 없다.
- 직전 조사 반영: [2026-09-09 검사](docs/VERIFICATION.md#documentation-verification--2026-09-09).
- 이번 문서 정비: [MFG-11 통합 검사](docs/VERIFICATION.md#source-ownership-verification). `make setup/test/verify` PASS,
  248 passed / 17 skipped와 OPC UA 5개 판정·9개 event의 hash read-back. 링크·공개 주장·코드 책임 위치를 대조했다.
  기존 제품 계약·source·런타임 설정·보존 artifact는 변경하지 않았으며 새 브라우저/컨테이너 실행은 없다.

## 유지하는 후속 판단

2026-09-10 작성자는 복잡한 지도 자체를 UiPath처럼 확대·이동하는 작업면을 의도했다고 정정했다.
[최신 공식 조사·화면 구상·추천](docs/research/file-review-workflow.md#map-canvas-intent-correction)은 접고 펼치는
그래프 캔버스와 연결된 상세다. 기존 8개 상한은 이전 설계 선택이며 새 필요성을 부정하는 근거로 쓰지 않는다.
이후 작성자가 이 탐색형 canvas 첫 로컬 구현을 수용했다. 현행 [canvas 계약](docs/FILE_REVIEW_CONTRACT.md#graph-canvas--file-local-membership-exploration)에 반영했고 기존 Main/Worker 분담으로 구현·직접 검증했다.

이전 지도 탐색 UX는 [MFG-13 후속 검토](docs/research/file-review-workflow.md#map-navigation-review)에 근거를 보존했다.
`45512b6`의 구현·보존 화면과 공식 문서를 대조한 뒤 수용한 **넓게 보기·선택적 전체화면 + 전체 항목 이름 검색**은 로컬 UI 검증을 마쳤다.
[탐색 계약](docs/FILE_REVIEW_CONTRACT.md#review-navigation--wide-view-fullscreen-and-item-search)을 따른다. 이 부분 결과와 최신 canvas 검증의 범위를 구분한다.
작성자의 긍정적 첫 인상을 과제 수행 성공으로 기록하지 않는다. 기존 사용자 관찰은 유지하며 Release의 새 선행조건이 아니다.

[MFG-10](docs/BACKLOG.md#mfg-10--context-bound-review-assistant-discovery)은 공개 조사·코드 대조까지 마쳤다.
[추천안](docs/research/review-assistant.md)은 마지막으로 확인한 결과의 버전·구간을 설명하는 읽기 전용 도우미다.
2026-09-09 역할 방향을 수용했다. 첫 로컬 preview는 [파일 계약](docs/FILE_REVIEW_CONTRACT.md#guided-result-explanation--first-local-preview), 실행 범위는 MFG-12가 소유한다. 자유 대화·외부 AI의 설계와 권한은 계속 미수용이다.

[MFG-09](docs/BACKLOG.md#mfg-09--independent-use-release-and-feedback)는 기존 `v0.1.0` Release와 독립 사용·공개 운영 경계를 소유한다.
문서 정비나 새 기능 조사를 Release의 새 선행조건으로 만들지 않는다. 실제 업무 파일로 설명 없는 사용과 기존 도구 대비 가치는 미검증이다.
공개 샘플 화면에 대한 작성자의 첫 인상은 긍정적이었지만 과제 수행·버전 선택·소요 시간은 관찰되지 않았다.
전달 누락 → 결과 설명 → 같은 버전 근거 찾기의 실제 검토자 관찰은 MFG-09/MFG-12의 남은 검증으로 보존한다.

공개 설명은 구현·검증한 파일 서비스와 별도 OPC UA 실험의 근거까지다. 공장 도입·반복 사용·생산 운영·처리량/비용 절감과
원본 OPC UA 재수집의 멱등성은 주장하지 않는다. 제품 source·문서는 Apache-2.0, MetroPT 발췌본은 별도 CC BY 4.0 경계를 유지한다.
