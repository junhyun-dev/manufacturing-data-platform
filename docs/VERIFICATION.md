# Verification — 재현과 증거의 범위

현재 변경의 exact baseline·결과·다음 gate는 [PROJECT_STATUS](../PROJECT_STATUS.md)가 소유한다.
이 문서는 새 checkout의 실행 방법과 각 검증으로 말할 수 있는 범위를 설명한다.

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

[MFG-08](BACKLOG.md#mfg-08--product-value-and-source-reality)의 조사 결과를 제품 코드와 독립적으로 확인하는
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
