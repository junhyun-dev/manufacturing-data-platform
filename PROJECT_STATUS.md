# Manufacturing — 현재 작업

현재 단계·기준 revision·다음 행동은 이 파일이 소유한다. 제품 약속은 [File Review Contract](docs/FILE_REVIEW_CONTRACT.md),
작업별 범위는 [Backlog](docs/BACKLOG.md), 실행 방법·날짜별 근거는 [Verification](docs/VERIFICATION.md)이 소유한다.

| 항목 | 현재 값 |
|---|---|
| 현재 작업 | LOCAL VERIFIED — MFG-12 결과 설명 preview 구현·직접 검토·HTTP/브라우저 검증 완료 |
| 수용한 범위 | 2026-09-09 현재 CSV 결과 설명 방향으로 계속 진행 수용. 첫 로컬 구현은 선택형 질문과 실제 서버 근거; 외부 AI·자유 대화·유료 호출·배포는 포함하지 않음 |
| Git 기준 | `feat/review-explanation`; 정비 완료 `defbacd452257ff626ffa1888005fbf7135940e9` → 계약 `e9e11c0` → 구현 통합 `5d3bcea`와 검토 보정. 최종 HEAD·dirty는 Git으로 확인; 원격 반영 없음 |
| 기존 제품 | CSV 검토·구간 분석·교체·근거 ZIP과 공개 샘플 보관 입력 복구. 코드 병합 `2e8e58c346d0eaec0722cdaba83f9a576e70d68e` |
| 외부 확인 | 마지막 확인 2026-09-08: [PR #1](https://github.com/junhyun-dev/manufacturing-data-platform/pull/1) squash MERGED; `main@c4b3814` [CI 4/4 PASS](https://github.com/junhyun-dev/manufacturing-data-platform/actions/runs/34188251022). 이번 정비에서 원격 재조회 없음 |
| Release·운영 | NOT TAGGED / NOT RELEASED / NOT DEPLOYED. tag·GitHub Release·배포는 별도 최종 승인 대상 |
| 다음 한 행동 | 공개 샘플의 전달 누락 → 결과 설명 → 같은 버전 근거 찾기를 실제 검토자 한 명에게 안내 없이 사용하게 하고, 막힌 질문 한 가지를 기록한다 |

## 실행과 근거

```bash
make setup
make serve
# http://127.0.0.1:8000
```

[사용법](docs/FILE_REVIEW_GUIDE.md)은 full/sample 실행과 첫 사용자 흐름을 안내한다. `full`은 자기 CSV를 받는 로컬 흐름,
`sample`은 임의 업로드를 서버에서 거부하는 체험 후보다. 한 프로세스·SQLite이고 계정·팀 공유·현장 연결은 없다.
[Architecture](docs/ARCHITECTURE.md)에서 현재 서비스와 별도 OPC UA 실험의 책임 경계를 확인한다.

- 기존 서비스: [2026-09-08 검사·실제 HTTP/브라우저·clean checkout·컨테이너 기록](docs/VERIFICATION.md#file-service-verification).
- 이번 설명 기능: [MFG-12 검증](docs/VERIFICATION.md#guided-explanation-verification). 255 passed / 17 skipped,
  실제 HTTP·재시작·ZIP과 full/sample Chromium 검증. [데스크톱](docs/assets/file-review-explanation-desktop.png) ·
  [모바일](docs/assets/file-review-explanation-mobile.png)은 실제 공개 샘플 화면이다. 별도 API key 설정은 없다.
- 직전 조사 반영: [2026-09-09 검사](docs/VERIFICATION.md#documentation-verification--2026-09-09).
- 이번 문서 정비: [MFG-11 통합 검사](docs/VERIFICATION.md#source-ownership-verification). `make setup/test/verify` PASS,
  248 passed / 17 skipped와 OPC UA 5개 판정·9개 event의 hash read-back. 링크·공개 주장·코드 책임 위치를 대조했다.
  기존 제품 계약·source·런타임 설정·보존 artifact는 변경하지 않았으며 새 브라우저/컨테이너 실행은 없다.

## 유지하는 후속 판단

[MFG-10](docs/BACKLOG.md#mfg-10--context-bound-review-assistant-discovery)은 공개 조사·코드 대조까지 마쳤다.
[추천안](docs/research/review-assistant.md)은 마지막으로 확인한 결과의 버전·구간을 설명하는 읽기 전용 도우미다.
2026-09-09 역할 방향을 수용했다. 첫 로컬 preview는 [파일 계약](docs/FILE_REVIEW_CONTRACT.md#guided-result-explanation--first-local-preview), 실행 범위는 MFG-12가 소유한다. 자유 대화·외부 AI의 설계와 권한은 계속 미수용이다.

[MFG-09](docs/BACKLOG.md#mfg-09--independent-use-release-and-feedback)는 기존 `v0.1.0` Release와 독립 사용·공개 운영 경계를 소유한다.
문서 정비나 새 기능 조사를 Release의 새 선행조건으로 만들지 않는다. 실제 업무 파일로 설명 없는 사용과 기존 도구 대비 가치는 미검증이다.

공개 설명은 구현·검증한 파일 서비스와 별도 OPC UA 실험의 근거까지다. 공장 도입·반복 사용·생산 운영·처리량/비용 절감과
원본 OPC UA 재수집의 멱등성은 주장하지 않는다. 제품 source·문서는 Apache-2.0, MetroPT 발췌본은 별도 CC BY 4.0 경계를 유지한다.
