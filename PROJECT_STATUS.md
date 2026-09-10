# Manufacturing — 현재 작업

현재 단계·기준 revision·다음 행동은 이 파일이 소유한다. 제품 약속은 [File Review Contract](docs/FILE_REVIEW_CONTRACT.md),
작업별 범위는 [Backlog](docs/BACKLOG.md), 실행 방법·날짜별 근거는 [Verification](docs/VERIFICATION.md)이 소유한다.

| 항목 | 현재 값 |
|---|---|
| 현재 작업 | MFG-13 지도 canvas 의도 정정·공식 조사/설계 제안 완료, 첫 로컬 범위 선택 대기. 기존 넓게 보기·전체화면·검색은 LOCAL VERIFIED인 부분 결과. 전체 검사 gate OPEN·실제 사용자 수용 미검증 |
| 수용한 범위 | 설비 선택 → 한 파일 버전의 항목 지도 → 관측·출처·같은 버전 ZIP. 여기에 [넓게 보기·전체화면·이름 검색](docs/FILE_REVIEW_CONTRACT.md#review-navigation--wide-view-fullscreen-and-item-search)을 추가. 기존 8개 지도/전체 목록·CSV·이전 결과·설명 유지. 줌/이동·물리 관계/건강 추정·외부 AI·공개 배포는 포함하지 않음 |
| Git 기준 | `feat/review-navigation`, 구현 `743bebd`(수용 계약 `3686f5d` 이후 정적 UI 3파일·browser oracle·관련 문서/화면). 검증한 UI digest는 [실행 근거](docs/VERIFICATION.md#review-navigation-verification). 기존 조사 3문서는 `51b66ad` 보존. 정확한 HEAD·dirty는 실제 Git에서 확인. 로컬 작업이며 원격 조회/반영 없음 |
| 기존 제품 | CSV 검토·구간 분석·교체·근거 ZIP과 공개 샘플 보관 입력 복구. 코드 병합 `2e8e58c346d0eaec0722cdaba83f9a576e70d68e` |
| 외부 확인 | 2026-09-09 원격 `main@c4b3814` 유지 확인. 2026-09-08 [PR #1](https://github.com/junhyun-dev/manufacturing-data-platform/pull/1) squash MERGED와 [CI 4/4 PASS](https://github.com/junhyun-dev/manufacturing-data-platform/actions/runs/34188251022)는 기존 근거. 작업 브랜치 백업은 새 PR·원격 CI 통과·Release·배포를 의미하지 않음 |
| Release·운영 | NOT TAGGED / NOT RELEASED / NOT DEPLOYED. tag·GitHub Release·배포는 별도 최종 승인 대상 |
| 다음 한 행동 | [탐색형 지도 canvas 제안](docs/research/file-review-workflow.md#map-canvas-intent-correction)의 줌/이동·그룹 펼치기와 8개 고정 표시 대체를 첫 로컬 범위로 수용할지 결정한다. 제안은 미구현. MFG-02 시각 실패 조사와 MFG-09/12 사용자 관찰은 남은 작업으로 보존 |

## 실행과 근거

- 로컬 샘플 미리보기: **http://127.0.0.1:8000**. 기존 탭은 새로고침한다. 2026-09-10 실제 health/source revision
  `743bebd0baaabdd1006ca3607bc11963c430185b`, 제공된 UI bytes·이름 검색·넓게 보기·온도 7,144개와 같은 버전 ZIP을 확인했다.
  기존 preview DB를 유지했다. 로컬 실행 기록은 `.cache/review-navigation-preview/20260910T035019572965Z/server.json`과 `readback.json`.
- 새 탐색: [수용 범위·검증과 한계](docs/VERIFICATION.md#review-navigation-verification). full/sample 13/10개 묶음,
  기존 지도 14/11·설명 18/12·파일 화면 11/7 PASS. 실제 browser Esc·200% 확대·모바일/키보드·동일 ZIP 확인.
  [넓게 보는 화면](docs/assets/file-review-navigation-desktop.png) · [390px 검색/목록](docs/assets/file-review-navigation-mobile.png).
- 전체 검사: 초기 255 passed / 17 skipped 뒤, 마지막 단독 전체는 기존 laboratory 시각 검사 2 failed / 253 passed / 17 skipped.
  원인 미확인으로 전체 PASS를 주장하지 않는다. 웹 HTTP·browser 결과와 기존 OPC UA 한 실행의 성공 근거를 구분한다.
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
이번에는 조사 문서·backlog·이 현재 포인터만 갱신했다. 새 계약·UI 구현·Worker 작업·실행 환경 변경은 없다.

이전 지도 탐색 UX는 [MFG-13 후속 검토](docs/research/file-review-workflow.md#map-navigation-review)에 근거를 보존했다.
`45512b6`의 구현·보존 화면과 공식 문서를 대조한 뒤 수용한 **넓게 보기·선택적 전체화면 + 전체 항목 이름 검색**은 로컬 UI 검증을 마쳤다.
[탐색 계약](docs/FILE_REVIEW_CONTRACT.md#review-navigation--wide-view-fullscreen-and-item-search)을 따른다. 이 부분 결과와 최신 canvas 제안의 수용 여부를 구분한다.
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
