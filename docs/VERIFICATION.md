# Verification — 재현과 증거의 범위

현재 변경의 exact baseline·결과·다음 gate는 [PROJECT_STATUS](../PROJECT_STATUS.md)가 소유한다.
이 문서는 새 checkout의 실행 방법과 각 검증의 범위, [날짜별 파일 서비스 검증 기록](#file-service-verification)을 소유한다.
기록된 검증은 당시 revision의 근거이며 현재 배포·실사용을 자동으로 주장하지 않는다.

현재 CSV 웹 서비스는 [사용·검증 guide](FILE_REVIEW_GUIDE.md)의 `make serve`·`make verify-service`로
실행한다. 이 문서의 OPC UA·Spark·historical report 검증은 별도의 기존 실험이며 웹 실행의 선행조건이 아니다.

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
