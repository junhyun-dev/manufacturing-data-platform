# Manufacturing — 현재 작업

현재 진행 위치는 이 파일 한 곳에서 찾는다. 제품 의미는 [README](README.md)·[Contract](docs/CONTRACT.md),
작업별 범위와 완료 조건은 [Backlog](docs/BACKLOG.md), 정확한 변경 identity는 Git이 소유한다.

| 항목 | 현재 값 |
|---|---|
| 단계 | CLOSEOUT — 로컬 정비 완료, 알려진 재현성 공백을 남긴 검토 후보 |
| 결정자 | 프로젝트 작성자. 대표 프로젝트 선정과 외부 반영은 사용자 판단 |
| Integration target | `main` |
| 기존 기준점 | `0a3dfb81a8d6341b6e456e0aec72303018da93aa`; 시작 시 clean checkout |
| 새 checkout 검증 revision | `fbda33d13477c9bd5c8ad8354ec3d085e8e89283`; 아래 검증 뒤 상태 설명만 보완 |
| 작업 branch | `chore/reproducible-telemetry-handoff` |
| 이번 변경 | [MFG-00](docs/BACKLOG.md#mfg-00--reproducible-local-entry), 로컬 결과 준비 완료 |
| Candidate 확인 | `git log -1 --oneline`·`git status --short --branch`; 검증 당시 code/test hash는 각 run의 receipt |
| 외부 상태 | NOT RELEASED. push·PR·merge·배포 미실행; 새 원격 CI job도 미실행 |
| 다음 한 행동 | 기능 확장 전에 [MFG-07](docs/BACKLOG.md#mfg-07--intermittent-local-collection-timeout)의 수집 timeout 재현을 좁힌다 |

## 이번에 닫은 범위

기존 code와 공개 보고서를 보존하고 버전이 고정된 local env, setup/test/verify 명령, 보존된 결과의
read-back, 현재 계약과 작업 입구를 만들었다. OPC UA CI job을 추가하고 callback 실패가 원인을
숨긴 timeout으로 바뀌는 경로를 수정했다. 새 데이터 제품이나 복구 기능을 구현한 것은 아니다.
과거 작업을 이 변경 이후의 전달 방식으로 진행했다고 사후 포장하지 않는다.

## 2026-09-08 로컬 검증

| 검증 | 결과·한계 |
|---|---|
| `.venv`, Python 3.10.12, base + OPC UA | 전체 suite 210 passed / 17 skipped. Optional Spark·Airflow 등은 실행하지 않음 |
| 격리된 base 환경, Python 3.10.12 / 3.12.3 | 각각 181 passed / 19 skipped; OPC UA 모듈 2개도 skip |
| 저장 실패 주입 | 원래 spool 오류를 노출하고 last-good·seal을 만들지 않는 회귀 테스트 통과 |
| 실제 OPC UA replay | 정상·품질 이상·중단 collection과 event-time 5개 판정, 디스크 current/manifest/data read-back 성공 |
| 캐시 없는 새 local clone | `make setup → make test → make verify` 성공; 210 passed / 17 skipped, clean revision의 replay·read-back. 임시 clone은 제거 |
| 추가 반례 | trusted JSONL을 변조한 복사본은 `CURRENT_DATA_DIGEST`로 거부. 원본은 계속 검증 가능. Spark evidence 없이 기본 read-back을 하면 거부 |
| 원본 재수집 비교 | 두 실행의 event ID 9개는 같고 server/collection time과 dataset version은 다름. 원본 수준 멱등성을 주장하지 않음 |
| 구조 확인 | CI YAML, shell syntax, diff whitespace, project 문서 링크와 private 경로 의존성 확인 |
| 독립 AI review / 외부 사용자 수용 | 미실행. 자동 테스트·로컬 실행과 구분 |

전체 suite의 중간 반복에서 interrupted collection 첫 3개 관측을 기다리다 timeout이 한 번 있었다.
실패 output에는 TP2 한 건만 있었고 seal은 없었다. 이후 6회 연속 collection 검증과 최종 전체 suite는
통과했지만 근본 원인은 미확정이다. 진단 개선을 그 간헐 실패의 해결로 읽지 않는다. MFG-07이 이 공백을 소유한다.

로컬 실행 로그는 `.cache/adoption-tests.log`와 `.cache/adoption-replay.log`다. 새 checkout 검증 요약은
`.cache/adoption-cold-check.json`, 로그는 `.cache/adoption-cold-check.log`에 있다. 요약 안의 임시
checkout 경로는 검증 당시 위치이며 정리 후 존재하지 않는다. 보존된 정상 실행은
`.cache/telemetry-runs/`에서 각 `runtime_identity.json`·`readback.json`으로 식별한다. 실패 관측은
`.cache/telemetry-failure-observation/`에 있다. 이 생성물은 Git에 넣지 않으며 새 checkout은
[Verification](docs/VERIFICATION.md)의 명령으로 자체 근거를 만든다. 보존된 public JSON/HTML/PNG는 변경하지 않았다.

## 새 세션에서 이어가기

```text
AGENTS.md → 이 파일 → MFG-07 → 해당 code/test와 실제 Git
```

환경이 없으면 `make setup`, 로컬 정상 경로 확인은 `make test`, `make verify`다. 도구 설치나 진단은
로컬 범위에서 진행할 수 있다. MFG-07을 먼저 조사한 뒤, 제품 보강은 MFG-01의 분석 질문·grain·시간·
실패 의미를 작성자와 정하고 작은 consumer 하나로 시작한다. 나머지 backlog를 자동으로 모두 열지 않는다.

현재 이력서 주장은 로컬 source·품질·발행·무결성 검증에 한정한다. 실제 분석 결과, 복구 완료,
처리 규모, 외부 사용자 가치, production 성과는 아직 근거가 필요하다. 공개 반영이 필요할 때는
이 branch의 실제 diff를 검토하고 사용자 승인 뒤 push·PR·CI 확인으로 이어간다.
