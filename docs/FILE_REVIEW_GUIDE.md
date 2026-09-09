# Telemetry Review 사용과 실행

설비 CSV를 전달받은 데이터 엔지니어·분석가가 파일 상태를 확인하고, 필요한 구간을 분석해
관측값과 검토 근거를 함께 전달하는 도구다. 공개 배포 전의 로컬 서비스 후보이며 실제 사용자 수용은 별도 검증한다.

## 시작

저장소 루트에서 Python 3.10+와 uv로 실행한다.

```bash
make setup
make serve
```

브라우저에서 `http://127.0.0.1:8000`을 연다. `Ctrl+C`로 서버를 중지한다. 같은 저장소에서
다시 실행하면 유효한 브라우저 작업 공간의 파일과 검사 이력이 복원된다. 설치 후 샘플 사용에는
네트워크나 원본 208 MiB archive가 필요 없다. 웹 실행에 MongoDB, Spark, OPC UA는 사용하지 않는다.

## 컨테이너 실행과 모드

Docker Compose의 기본 서비스도 같은 웹 제품이다. `full`은 loopback에서 자기 CSV 업로드·교체까지
제공한다.

```bash
docker compose up --build

curl http://127.0.0.1:8000/healthz
```

외부 독자가 비민감 샘플만 체험할 후보는 `sample`로 실행한다. 이 모드에서는 화면만 숨기는 데 그치지 않고
새 CSV와 교체 CSV를 HTTP 403 `UPLOADS_DISABLED`로 거부한다. 샘플 분석·전달 누락 체험·복구·삭제는 유지된다.
명시적인 env file은 WSL의 Windows Docker CLI를 포함해 shell 환경 전달 방식이 다른 곳에서도 같은 설정을 만든다.

```bash
docker compose --env-file .env.example up --build
```

`.env.example`을 `.env`로 복사해 named artifact의 `MFG_REVIEW_RELEASE`와 full Git SHA
`MFG_REVIEW_REVISION`을 넣을 수 있다. 둘은 image label과 실행 환경에 함께 들어가며 `/healthz`에서 read-back한다.

컨테이너는 UID/GID `10001:10001`, 읽기 전용 root filesystem과 제한된 `/tmp`로 실행된다. SQLite는
`telemetry_review_data` volume에 저장되므로 `docker compose down` 뒤에도 남는다. 저장된 작업 공간을 실제로
버릴 때만 `docker compose down --volumes`를 사용한다. DB의 schema version이 현재 코드보다 새로우면 기동을
거부한다. volume 재시작은 검증했지만 online backup·이전 version downgrade는 제공하지 않는다.

기존 MongoDB 실험이 필요할 때만 `docker compose --profile historical up mongo`를 사용한다. 이 MongoDB는
Telemetry Review의 저장소가 아니다.

## 첫 사용 흐름

1. **공개 샘플 열기** 또는 **CSV 업로드**를 누른다. 양식을 내려받아 자기 파일을 맞출 수 있다.
   필수 열은 `timestamp,equipment,tag,value,unit`이며 한 행이 한 관측이다. `quality`는 선택 열이다.
2. 파일 검사 결과를 확인한다. 중복·단위 혼합·잘못된 값·시간대 혼합·제공된 Bad/Uncertain은
   분석 결과 생성을 막는다. 품질을 생략하면 미제공으로 남으며 센서가 정상이라고 판정하지 않는다.
3. 설비·측정 항목·시간 구간을 선택하고 **조회**한다. 시작은 포함하고 종료는 포함하지 않는다.
   시각이 비어 있으면 전체 기간이다. 시간대가 없는 파일은 원본 벽시각을 유지하며, 시간대가 있으면 UTC로 조회한다.
4. 표본 통계와 실제 관측을 확인하고 **결과 내려받기**를 누른다. ZIP의 `observations.csv`는
   조회 구간 전체이며 화면 표 100행·그래프 500점 제한의 영향을 받지 않는다.
5. **수정 파일로 교체**한다. 잘못된 파일이면 이전 정상 결과와 최신 실패를 함께 보여준다.
   올바른 수정 파일은 새 버전이 된다. 같은 원본의 재검사는 같은 버전을 유지한다.

샘플의 **전달 누락 체험**은 보관한 21,432개 관측 중 2,143개를 전달에서 실제 제외한다.
최신 시도는 미완료가 되고 기존 결과는 유지된다. **보관 원본으로 복구**하면 전체 원본을 다시 검사해
같은 버전을 확인한다. 실제 센서의 결측을 만들거나 복원하는 기능은 아니다.

샘플 Oil_temperature 전체 구간의 관측 수는 7,144개, 표본 평균은 약 `55.7481173012°C`다.
각 태그에서 60초보다 긴 원본 시간 간격은 2곳이며 최대 12,929초다. 이는 공개 기록의 간격이지
설비 중단·서비스 장애·추정 결측 개수가 아니다. 원본과 변환·라이선스는
[샘플 출처](../src/manufacturing_data_platform/file_review/sample/README.md)가 소유한다.

## 결과 설명으로 근거 확인하기

우측 하단의 **이 결과에 질문**을 열면 지금 보고 있는 결과에 대해 세 가지 질문을 선택할 수 있다.
검토 데이터와 정해진 규칙으로 답하는 첫 설명 기능이다. AI 자유 대화나 파일을 수정하는 자동 실행 기능은 아니다.
설명 때문에 파일이 외부 AI로 전송되거나 별도 AI 호출 비용이 발생하지 않는다.

| 질문 | 확인할 것 |
|---|---|
| 왜 이 결과가 보이나요? | 최근 검사의 성공/실패와 통계에 사용한 원본·버전을 구분한다. |
| 전달할 때 무엇을 적어야 하나요? | 분석 구간·관측 수·표본 평균·품질 한계와 같은 결과의 근거를 확인한다. |
| 시간 공백은 설비 중단인가요? | 관측 간격을 확인하고, 이를 설비 중단이나 센서 결측 수로 단정할 수 없는 이유를 읽는다. |

공개 샘플로 확인하려면:

1. **공개 샘플 열기** → `Oil_temperature` 선택 → **조회**한다.
2. **샘플 체험**을 열어 **전달 누락 체험**을 누른다. 최신 시도는 미완료지만 이전 평균이 남는다.
3. **이 결과에 질문** → **왜 이 결과가 보이나요?**에서 실패한 최신 시도와 유지된 원본·버전을 확인한다.
4. **전달할 때 무엇을 적어야 하나요?**와 근거 버튼으로 같은 조회·파일·검사 기록을 확인한다.
5. 기존 **결과 내려받기**로 그 버전의 관측값과 manifest를 확인한다. 설명이 파일 전달을 승인하거나 센서 정상 여부를 보증하지는 않는다.

설명은 **마지막으로 조회한 결과**를 기준으로 한다. 시간이나 측정 항목을 입력만 바꿨다면 조회를 눌러야 새 조건을 사용한다.
다른 탭에서 최근 검사가 바뀌면 다시 파일 상태를 확인하도록 안내한다. 실패·취소·시간 초과 때 이전 답변을 새 답변으로 대신하지 않는다.
작은 화면에서는 설명을 전체 화면으로 읽고 닫기나 Escape로 돌아간다. 파일 전환·삭제·새로고침 후 다른 파일의 설명을 재사용하지 않는다.
설명 기록은 계정이나 서버의 대화 이력으로 저장되지 않는다.

2026-09-09 공개 샘플로 촬영한 실제 [데스크톱 설명 화면](assets/file-review-explanation-desktop.png)과
[모바일 설명 화면](assets/file-review-explanation-mobile.png)을 먼저 볼 수 있다. 로컬 검증 화면이며 공개 배포 주소는 아니다.

## 보관·삭제·실패

- 원본과 검토 결과는 **실행 서버**에 저장된다. 브라우저만의 처리가 아니다.
- 임시 작업 공간은 브라우저 쿠키로 구분한다. 공유 링크·계정 복구·팀 공유는 제공하지 않는다.
  쿠키를 지우면 이전 공간을 다시 찾을 수 없다. 같은 원본을 다른 브라우저에서 보게 해 주는 접근 경로도 없다.
- 비활성 공간은 24시간 뒤 다음 세션 생성 또는 서버 시작 시 정리한다. 정확히 24시간에 실행되는 예약 삭제는 아니다.
  **삭제**는 그 파일의 원본·버전·이력을 함께 제거한다. 이미 내려받은 파일에는 영향을 주지 않는다.
- 파일당 8 MiB/50,000행, 공간당 파일 10개·원본/정규화 결과 32 MiB, 서버 전체 256 MiB를 제한한다.
  시도 이력은 파일당 100건을 보관하고 최근 12건을 화면에 표시한다. SQLite 파일의 물리 크기는 이 논리 용량과 다를 수 있다.
- 잘못된 입력은 수정해서 교체한다. 재검사만으로 잘못된 CSV가 고쳐지지는 않는다.
  저장 원본/결과 손상은 분석·내려받기를 차단한다. 해당 파일을 삭제하고 원본을 새로 올릴 수 있다.
  정상인 다른 파일은 계속 사용할 수 있다.
- 기본 저장소는 `.cache/file-review/review.sqlite3`다. 경로를 바꾸려면 서버 시작 전 `MFG_REVIEW_DB`를 지정한다.
  원본 파일은 보관소 밖에도 따로 유지한다. 서버가 실행 중일 때 DB 파일만 임의로 복사하지 않는다.

## 검증

```bash
make test
make verify-service
make verify-container
make audit-service
make verify
```

`make test`는 기존 모듈과 새 파일 서비스 검사를 실행한다. `make verify-service`는 별도 임시 저장소·
loopback 서버에서 실제 HTTP 업로드, 실패한 교체, 수정, 샘플 SQL 정답, 누락·복구, ZIP read-back,
서버 재시작을 확인한다. `.cache/file-review-verification/<run>/receipt.json`은 Git identity와 실행
source hash, 실제 수치·검사 결과를 기록한다. `make verify`는 별개의 기존 OPC UA 수집 실험이다.
`make verify-container`는 고유한 임시 image/container/volume을 만들고 sample-only 업로드 거부, release identity,
비루트·읽기 전용 실행, 샘플 SQL 수치와 같은 volume 재시작을 확인한 뒤 자신이 만든 자원만 정리한다.
영수증은 `.cache/release-container/<run>/receipt.json`에 남는다.
`make audit-service`는 고정된 Python runtime package를 현재 advisory database와 대조한다. 이 결과는 실행 시점의
Python package 범위이며 base OS image scan이나 미래 취약점 부재를 보장하지 않는다.

실제 브라우저 검사는 Playwright와 Chromium이 있는 Python으로 실행한다. 서비스 실행 환경에는 필요 없다.

```bash
# 별도 터미널: make serve
# Playwright가 이미 설치된 Python을 사용할 때:
python3 scripts/verify_file_review_browser.py
# sample 모드 서버를 확인할 때:
python3 scripts/verify_file_review_browser.py --mode sample
# 결과 설명: 실제 서버 근거·맥락 변경·취소·모바일을 확인할 때:
python3 scripts/verify_review_explanation_browser.py --mode full
# sample 서버에서는 --mode sample을 사용한다.
# 없으면 별도 검증 환경을 만들 수 있다:
uv venv .cache/browser-venv
uv pip install --python .cache/browser-venv/bin/python playwright
.cache/browser-venv/bin/python -m playwright install chromium
.cache/browser-venv/bin/python scripts/verify_file_review_browser.py
```

검사는 자신의 별도 브라우저 공간만 사용하고 자신이 만든 파일만 삭제한다. 기존 사용자 파일은 건드리지 않는다.
`.cache/file-review-browser/`에 정상·이전 결과·모바일 화면, 실제 다운로드와 receipt를 남긴다.
수동으로는 키보드 파일 선택, 오류 메시지, 긴 파일명, 작은 화면, 빈 구간에서 이전 그래프가 남지 않는지도 확인한다.
결과 설명 검사는 고유한 `.cache/review-explanation-browser/<run>/`에 화면·서버 응답·ZIP·receipt를 남긴다.
늦은 응답 검사는 브라우저에서 지연과 무효한 transport abort를 주입해, 서버 응답이 도착해도 취소된 내용을 표시하지 않는지 확인한다.

## 공개 서비스로 넘어갈 다음 gate

현재 제공하는 것은 작동하는 로컬 후보와 검증 수단이다. 서버 배포나 사용자 확보를 완료했다고 기록하지 않는다.
외부 공개를 위한 다음 작업은 [MFG-09](BACKLOG.md#mfg-09--independent-use-release-and-feedback)가 소유한다.

대상 호스트·TLS 종료 방식·저장 볼륨·삭제 일정·업로드 허용 범위·운영 책임을 정한 실제 배포 설정을 먼저 만들고 검증한다.
환경 변수 `MFG_REVIEW_HOSTS`는 허용할 호스트 이름, `MFG_REVIEW_SECURE_COOKIE=1`은 HTTPS 쿠키를 제어한다.
Compose의 loopback bind와 host port는 `MFG_REVIEW_BIND`, `MFG_REVIEW_PORT`로 바꿀 수 있다.
프록시를 쓴다면 신뢰하는 프록시와 원본 Host/scheme 전달을 함께 확인해야 한다. 이 두 환경 변수만으로 공개 운영 준비가
끝나는 것은 아니다. 익명 업로드의 요청 제한·세션 생성량·디스크/WAL·동시 요청 메모리·정리 동작을 해당 호스트에서 측정한다.
공개 샘플 모드는 임의 파일 노출 위험을 줄이지만 익명 workspace·샘플 생성 요청 자체의 남용을 막지는 않는다.
edge 요청 제한, runtime log/alert와 폐기 가능한 volume 정책을 후보 host에서 확인한다. 그 결과를 검토하고
작성자가 승인한 뒤 push·원격 CI·배포를 진행한다.

첫 독립 사용자는 자신의 CSV로 설명 없이 업로드→문제 수정→구간 조회→ZIP 근거 확인을 해본다.
기존 SQL/스프레드시트 작업보다 도움이 된 지점과 막힌 지점을 기록하고, 반복 사용 여부로 다음 기능을 고른다.
실제 공장 운영, 성능 개선율, 비용 절감, 제품 채택은 그 근거가 생긴 뒤 이력서에 쓴다.
