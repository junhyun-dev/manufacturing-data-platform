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
