# Manufacturing — 현재 작업

현재 단계·기준 revision·다음 행동은 이 파일이 소유한다. 제품 약속은 [File Review Contract](docs/FILE_REVIEW_CONTRACT.md),
작업별 범위는 [Backlog](docs/BACKLOG.md), 실행 방법·날짜별 근거는 [Verification](docs/VERIFICATION.md)이 소유한다.

| 항목 | 현재 값 |
|---|---|
| 현재 작업 | MFG-13 지도 전용 전체화면 / LOCAL VERIFIED, 2026-09-10. 로컬 미리보기 갱신·read-back 완료. 과거 간헐 검사 gate OPEN·실제 사용자 수용 미검증 |
| 수용한 범위 | [지도 전용 전체화면](docs/FILE_REVIEW_CONTRACT.md#dedicated-map-fullscreen): 지도 도구 안 진입/복귀, 실제 화면 점유, 미지원 대체와 상세/근거 복귀. 기존 canvas·카메라·선택·버전·조회·동일 ZIP·모달 경계를 유지하는 표시 개선이며 새 API/DB/graph 의미 없음 |
| Git 기준 | `feat/map-fullscreen`, source `d33ed90b33b10c5c222f00e8dc20a499f304c440`, 수용 계약 `aa4469e`, Worker 보존 `ee38485`. 실제 HEAD/dirty는 Git에서 확인. push/merge/Release/배포 없음 |
| 기존 제품 | CSV 검토·구간 분석·교체·근거 ZIP과 공개 샘플 보관 입력 복구. 코드 병합 `2e8e58c346d0eaec0722cdaba83f9a576e70d68e` |
| 외부 확인 | 2026-09-09 원격 `main@c4b3814` 유지 확인. 2026-09-08 [PR #1](https://github.com/junhyun-dev/manufacturing-data-platform/pull/1) squash MERGED와 [CI 4/4 PASS](https://github.com/junhyun-dev/manufacturing-data-platform/actions/runs/34188251022)는 기존 근거. 작업 브랜치 백업은 새 PR·원격 CI 통과·Release·배포를 의미하지 않음 |
| Release·운영 | NOT TAGGED / NOT RELEASED / NOT DEPLOYED. tag·GitHub Release·배포는 별도 최종 승인 대상 |
| 다음 한 행동 | 실제 검토자가 지도 전체화면에서 온도 항목을 찾고 관측·같은 버전 근거로 돌아가는 과제를 관찰한다. 작성자의 화면 검수와 MFG-09/12의 독립 사용 관찰을 구분하며 새 구현은 자동 개시하지 않는다 |

## 실행과 근거

- 로컬 샘플 미리보기 **http://127.0.0.1:8000**. 새로고침 후 지도 안의 **지도 전체화면**을 누른다.
  2026-09-10 12:43 UTC 실제 health가 `sample`/source `d33ed90`이며 네 UI 파일의 commit bytes·지도 전용 화면,
  출처 복귀·온도 7,144개·평균 55.74811730123181·동일 ZIP을 확인했다. 기존 preview DB를 유지했다.
  실행/검수 기록은 `.cache/map-fullscreen-preview/20260910T124229287203Z/server.json`과
  `readback.json`. 이 주소는 로컬 프로세스이며 PC/환경 재시작 뒤 자동 복구를 보장하지 않는다.
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
