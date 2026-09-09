# Manufacturing — 현재 작업

현재 단계·기준 revision·다음 행동은 이 파일이 소유한다. 제품 약속은 [File Review Contract](docs/FILE_REVIEW_CONTRACT.md),
작업별 범위는 [Backlog](docs/BACKLOG.md), 실행 방법·날짜별 근거는 [Verification](docs/VERIFICATION.md)이 소유한다.

| 항목 | 현재 값 |
|---|---|
| 현재 작업 | WORK — MFG-11 제품 문서의 역할·읽는 경로·변경 책임 정비. 기존 서비스와 MFG-10 조사 상태 보존 |
| 수용한 범위 | 2026-09-09 문서 구조와 관련 안내 테스트 정비 승인. chat 역할·Data/API·외부 전송·보관·비용 정책은 미수용 |
| Git 기준 | `docs/mfg-09-scenario-gates`; 정비 전 복원점 `dd82b751df7bc8b2ecfe1953d3778610518ca65f`. 실제 HEAD·dirty는 Git으로 확인 |
| 기존 제품 | CSV 검토·구간 분석·교체·근거 ZIP과 공개 샘플 보관 입력 복구. 코드 병합 `2e8e58c346d0eaec0722cdaba83f9a576e70d68e` |
| 외부 확인 | 마지막 확인 2026-09-08: [PR #1](https://github.com/junhyun-dev/manufacturing-data-platform/pull/1) squash MERGED; `main@c4b3814` [CI 4/4 PASS](https://github.com/junhyun-dev/manufacturing-data-platform/actions/runs/34188251022). 이번 정비에서 원격 재조회 없음 |
| Release·운영 | NOT TAGGED / NOT RELEASED / NOT DEPLOYED. tag·GitHub Release·배포는 별도 최종 승인 대상 |
| 다음 한 행동 | MFG-11의 정리된 문서·기존 테스트를 통합 검토하고 필수 검사 뒤 로컬 변경을 닫는다 |

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
- 직전 문서 변경: [2026-09-09 검사](docs/VERIFICATION.md#documentation-verification--2026-09-09). 코드 변경 없이 248 passed / 17 skipped와 fixture read-back을 확인했다.
- 새로운 문서 통합 검증은 MFG-11 closeout에서 기록한다. 과거 성공을 새 통합 검증으로 취급하지 않는다.

## 유지하는 후속 판단

[MFG-10](docs/BACKLOG.md#mfg-10--context-bound-review-assistant-discovery)은 공개 조사·코드 대조까지 마쳤다.
[추천안](docs/research/review-assistant.md)은 마지막으로 확인한 결과의 버전·구간을 설명하는 읽기 전용 도우미다.
사용자 역할 선택 뒤 질문·근거·허용 데이터·실패 동작을 작은 계약으로 닫는다. 새 chat code·AI 호출·제품 수용은 없다.

[MFG-09](docs/BACKLOG.md#mfg-09--independent-use-release-and-feedback)는 기존 `v0.1.0` Release와 독립 사용·공개 운영 경계를 소유한다.
문서 정비나 새 기능 조사를 Release의 새 선행조건으로 만들지 않는다. 실제 업무 파일로 설명 없는 사용과 기존 도구 대비 가치는 미검증이다.

공개 설명은 구현·검증한 파일 서비스와 별도 OPC UA 실험의 근거까지다. 공장 도입·반복 사용·생산 운영·처리량/비용 절감과
원본 OPC UA 재수집의 멱등성은 주장하지 않는다. 제품 source·문서는 Apache-2.0, MetroPT 발췌본은 별도 CC BY 4.0 경계를 유지한다.
