# Manufacturing — 현재 작업

현재 진행 위치는 이 파일이 소유한다. 파일 서비스 의미는 [File Review Contract](docs/FILE_REVIEW_CONTRACT.md),
기존 OPC UA 실험은 [Contract](docs/CONTRACT.md), 작업별 완료 조건은 [Backlog](docs/BACKLOG.md)가 소유한다.

| 항목 | 현재 값 |
|---|---|
| 단계 | PR OPEN — [#1](https://github.com/junhyun-dev/manufacturing-data-platform/pull/1)의 current-head remote CI read-back과 merge gate |
| 사용자 결정 | 2026-09-08 Apache-2.0 경계, branch push, PR 공개와 원격 CI 확인을 승인. merge·tag·Release·배포는 아직 승인하지 않음 |
| Integration target | `main`; 원격 기준 `0a3dfb81a8d6341b6e456e0aec72303018da93aa` |
| 구현 시작점 | `6a7c71e` — 기존 로컬 환경·source 조사·제품 방향 정비 위에서 시작 |
| 검증한 서비스 revision | `1f1a8c1cf486480508b41ac3f7f966abf97d36df` — service + sample-only release runtime + Apache-2.0 image label |
| 작업 branch | `feat/telemetry-file-review` |
| 현재 결과 | `full`: 자기 CSV 검토·분석·근거 ZIP·교체. `sample`: 임의 업로드 거부·공개 기록 분석·전달 실패/복구 |
| Candidate 확인 | `.cache/release-container/20260908T042840284903Z/receipt.json`; clean `1f1a8c1`의 HTTP/container/OCI identity read-back PASS |
| 외부 상태 | branch push 및 PR #1 OPEN. 구현 head `1f1a8c1`의 원격 run `34187169061` 시작. NOT MERGED / NOT RELEASED / NOT DEPLOYED |
| 다음 한 행동 | PR #1의 최종 head에서 네 remote check를 green으로 read-back한 뒤 merge 여부를 사용자에게 확인한다 |

## 실행과 이어가기

```bash
make setup
make serve
# http://127.0.0.1:8000

# bounded sample-only container
docker compose --env-file .env.example up --build
```

[사용법](docs/FILE_REVIEW_GUIDE.md)의 공개 샘플이나 CSV 양식으로 시작한다. 웹 서비스는 MongoDB·OPC UA·
Spark나 작성자의 원본 cache 없이 동작한다. `make test`, `make verify-service`, `make verify-container`가 검증 입구다.
기존 OPC UA 실험은 `make verify`로 별도 실행한다.

새 세션은 `AGENTS.md → 이 파일 → File Review Contract → MFG-09` 순서로 복원한다. 환경 정비나 Discovery를
처음부터 반복하지 않는다. 첫 파일 계약은 수용·구현됐고, 다음은 실제 파일 사용에서 드러난 한 문제를 검증하는 일이다.
로컬 판단·구현·검증·독립 검토·closeout을 같은 흐름으로 진행한다. 특정 모델이나 private 문서에 의존하지 않는다.

## 구현한 범위와 중요한 선택

- MetroPT/OPC UA의 출처·상태 의미를 일반 업로드에 부여하지 않도록 파일 계약을 분리했다.
  기존 OPC UA trusted JSONL을 이 웹 화면으로 연결한 것은 아니다.
- 검토 결과와 최신 시도는 분리한다. 잘못된 파일·저장 실패는 이전 결과를 바꾸지 않는다.
  다운로드는 사용자가 확인한 version과 query를 고정하고 CSV digest·source hash·품질 한계를 함께 남긴다.
- 원본·정규화 버전·시도·현재 포인터는 SQLite transaction으로 관리한다. 읽기 때 원본과 버전을 재검증한다.
  다른 브라우저의 파일은 열 수 없고, 수정 요청에는 CSRF 검증을 적용한다.
- 공개 샘플은 MetroPT-3 하루치 7,144 source rows / 21,432 observations다. 센서 품질과 시간대는 미제공으로 남긴다.
  누락 체험은 2,143개 관측을 전달에서 제외한다. 보관 전체 입력의 복구·반복 재검사는 같은 version으로 수렴한다.
- 웹 클라이언트는 실제 업로드·교체·분석·다운로드·이력·삭제를 제공한다. 화면 수치를 하드코딩한 데모가 아니다.
- 기본 Compose 정문은 현재 Telemetry Review를 실행한다. 과거 MongoDB는 `historical` profile로 격리했다.
  공개 체험 후보는 server-side `sample` mode로 upload/replace를 거부하고 UI도 그 capability에 맞춘다.
- 실행 artifact는 `/healthz`와 OCI label로 release·full Git revision·mode를 노출한다. Python 3.12.13 base digest와
  runtime-only dependency lock을 고정하고 UID 10001, read-only root, SQLite volume으로 실행한다.
- 원본 코드·문서는 Apache-2.0으로 공개하고, 포함한 MetroPT-3 발췌본·파생 샘플의 CC BY 4.0 범위는 별도 출처 문서에 유지한다.
- 계정은 넣지 않았다. 현재 24시간 익명 workspace와 공개 sample에는 필요가 없으며, 기기 간 복원·장기 보관·팀 공유가
  실제 사용자 gate에서 확인될 때 identity/authorization/retention 계약을 함께 연다.

## 2026-09-08 검증과 한계

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
| 외부 CI / 실제 사용자 / 배포 / 장기 운영 | PR #1의 구현 head 원격 CI 네 check가 실행 중이며 최종 head read-back은 아직이다. 실제 사용자·배포·장기 운영은 미실행 |

이번 clean-checkout 묶음은 `.cache/release-cold-check/8c8868d/receipt.json`이 HTTP와 container receipt를 연결한다.
기존 실행 근거는 `.cache/file-review-tests.log`, `.cache/file-review-final-focused.log`,
`.cache/file-review-verification/<run>/receipt.json`, `.cache/file-review-browser/receipt.json`,
`.cache/file-review-legacy-replay.log`에 있다. 새 체크아웃의 명령·revision·clean 여부는
`.cache/file-review-cold-check/receipt.json`, 실제 HTTP 수치와 source 파일 hash는 같은 디렉터리의
`http-receipt.json`, 전체 출력은 `run.log`에 보존했다. 검증 전용 임시 clone은 근거 보존과 clean 확인 뒤 제거했다. 원본/결과 변조·저장 실패·quota·동시 재시도는 자동 테스트가 실행한다.
브라우저 실행기는 자신이 생성한 파일만 삭제한다. 기존 공개 보고서 JSON/HTML/PNG는 보존했다.

기존 정비 기준 `fbda33d`의 새 clone 검증(210 pass / 17 skipped, OPC UA read-back)은 이전 환경 정비의 근거다.
이번 서비스 결과와 합쳐 과거에 제품 사용까지 검증한 것처럼 쓰지 않는다. 과거 간헐 collection timeout은
[MFG-07](docs/BACKLOG.md#mfg-07--intermittent-local-collection-timeout)에 남아 있다. 이번 replay 성공은 원인 해결이 아니다.
웹 서비스는 해당 OPC UA 수집 경로를 사용하지 않는다.

## 다음 제품 gate와 Portfolio 경계

[MFG-09](docs/BACKLOG.md#mfg-09--independent-use-release-and-feedback): 열린 PR #1의 최종 head에서 원격 CI를 확인하고
merge·tag·GitHub Release를 각각 별도 gate로 닫는다. 이후 실제 CSV 검토자 한 명이 자신의 비민감 파일로 설명 없이
업로드·오류 수정·구간 조회·근거 전달을 수행하는 짧은 검증을 준비한다.
열 매핑, 공유, 큰 파일 같은 기능은 그 사용에서 드러난 한 문제에 맞춰 고른다. 기존 SQL/스프레드시트보다
유용한 지점과 도움 요청을 기록한다. 접근 가능한 사람이 없으면 공개 체험 배포안을 구체화하되 사용자 채택으로 기록하지 않는다.

공개 배포 후보의 host/TLS·보관 또는 폐기 volume·정리·edge 요청/세션 제한·runtime log/alert·OS image scan·
동시 메모리·운영 책임은 아직 정하지 않았다.
설정과 실제 검증 결과를 먼저 준비하고 사용자 최종 승인 뒤 외부 반영한다. 로컬 서비스 완성을 그 승인 대기로 오해하지 않는다.

현재 새로 설명할 수 있는 것은 CSV 검토·분석·교체·보관 입력 복구·근거 전달 서비스를 구현하고 로컬에서 검증한 범위다.
실제 공장 도입, 분석가의 반복 사용, 처리량·비용 절감·production 성과, OPC UA 원본 재수집의 멱등성은 주장하지 않는다.
이력서·사이트의 공개 문구는 이 검증과 실제 원격 반영 여부를 확인한 후 Portfolio 흐름에서 별도로 갱신한다.
