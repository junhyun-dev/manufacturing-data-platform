"""Deterministic explanations of one integrity-checked query snapshot."""


EVIDENCE = {
    "previous_result": ["history", "source", "query"],
    "handoff_limits": ["query", "source"],
    "gap_limits": ["query", "source"],
}
STATUS = {"ready": "검증 완료(ready)", "incomplete": "전달 미완료(incomplete)", "blocked": "파일 수정 필요(blocked)"}
KIND = {"import": "파일 검사", "sample": "샘플 검사", "replace": "수정 파일 검사",
        "retry": "보관 원본 재검사", "delivery-check": "전달 누락 체험"}


def _number(value):
    if value is None:
        return "없음"
    return f"{value:,}"


def _range(result):
    start = result["filter"]["start"] or "첫 관측"
    end = result["filter"]["end"] or "마지막 관측"
    return f"{start}부터 {end}{' 전까지' if result['filter']['end'] else '까지'}"


def _previous_result(result, stored, latest):
    version = stored["version"][:12]
    source = stored["source_name"]
    if latest["status"] != "ready":
        status = STATUS.get(latest["status"], latest["status"])
        kind = KIND.get(latest["kind"], latest["kind"])
        return (
            "유지된 결과를 표시하는 이유",
            [
                f"최근 입력 {latest['source_name']}의 {kind} 시도는 {status} 상태로 완료되지 않았습니다. 그 시도의 관측은 새 분석 결과로 발행하지 않았습니다.",
                f"현재 조회는 이전에 검증을 통과한 {source}의 버전 {version}을 사용합니다. 그래서 최근 시도와 조회 결과의 출처가 다를 수 있습니다.",
                "최근 검사 기록에서 완료되지 않은 시도를, 파일과 검증 근거 및 선택 구간 분석에서 실제 조회에 사용한 출처와 버전을 확인하세요.",
            ],
        )
    if result["previous_result"]:
        return (
            "명시한 이전 버전을 표시하고 있습니다",
            [
                f"최근 입력 {latest['source_name']}의 검사는 완료되었지만, 이 조회는 명시적으로 선택한 {source}의 이전 버전 {version}을 사용합니다.",
                "통계와 미리보기는 이 버전에서 계산했습니다. 최근 결과로 자동 전환하지 않았습니다.",
                "파일과 검증 근거에서 조회 출처와 버전을, 최근 검사 기록에서 최신 성공 시도를 함께 확인하세요.",
            ],
        )
    return (
        "현재 검증 결과를 표시하고 있습니다",
        [
            f"최근 입력 {latest['source_name']}의 파일 검사가 완료되었고, 이 조회는 {source}의 현재 버전 {version}을 사용합니다.",
            "선택 구간의 통계와 미리보기는 같은 검증 결과에서 계산했습니다.",
            "파일과 검증 근거에서 출처와 버전을, 선택 구간 분석에서 조회 조건과 수치를 확인하세요.",
        ],
    )


def _handoff_limits(result, stored, latest):
    summary = result["summary"]
    count = summary["count"]
    mean = summary["mean"]
    unspecified = summary["quality_counts"].get("unspecified", 0)
    if count == 0:
        values = "선택 구간의 관측값은 0개이며 표본 평균은 없습니다. 이전 조회의 평균을 사용하지 마세요."
    else:
        values = f"선택 구간의 관측값은 {_number(count)}개이고 표본 평균은 {_number(mean)} {result['unit']}입니다."
    return (
        "이 조회를 전달할 때 함께 적을 내용",
        [
            values,
            f"출처는 {stored['source_name']}, 결과 버전은 {stored['version'][:12]}, 조회 범위는 {_range(result)}이며 시각 기준은 {'시간대 미제공' if result['time_basis'] == 'unspecified' else 'UTC'}입니다.",
            f"품질이 제공되지 않은 관측값은 {_number(unspecified)}개입니다. 품질 미제공은 Good을 뜻하지 않으며 파일 검증은 센서 정확도를 인증하지 않습니다.",
            f"이 설명은 최근 시도 {latest['id']}의 상태 {latest['status']}를 함께 고정한 조회 결과입니다. 선택 구간 분석과 파일 근거를 같이 전달하세요.",
        ],
    )


def _gap_limits(result, stored, latest):
    summary = result["summary"]
    if summary["count"] < 2:
        observed = "선택 구간에는 관측값이 2개보다 적어 관측 간격을 계산할 수 없습니다."
    else:
        observed = (f"선택 구간에서 60초를 초과한 관측 간격은 {_number(summary['gap_count'])}곳이고 "
                    f"가장 긴 관측 간격은 {_number(summary['max_gap_seconds'])}초입니다.")
    return (
        "시간 공백만으로 설비 중단을 판단할 수 없습니다",
        [
            observed,
            "이 수치는 검증된 파일에 기록된 관측 시각 사이의 설명적 간격입니다. 설비 중단 시간, 잃어버린 행 수 또는 원인을 추정하지 않습니다.",
            "값과 간격만으로 설비가 정상인지 진단할 수도 없습니다. 선택 구간 분석에서 실제 범위와 관측값 수를 함께 확인하세요.",
        ],
    )


BUILDERS = {
    "previous_result": _previous_result,
    "handoff_limits": _handoff_limits,
    "gap_limits": _gap_limits,
}


def explain(dataset_id, question, result, stored, latest):
    """Build a JSON-safe response containing no observation rows or chart points."""
    title, paragraphs = BUILDERS[question](result, stored, latest)
    return {
        "mode": "guided",
        "question": question,
        "context": {
            "dataset_id": dataset_id,
            "version": result["version"],
            "source_name": stored["source_name"],
            "source_sha256": stored["source_sha"],
            "latest_attempt_id": latest["id"],
            "latest_status": latest["status"],
            "equipment": result["equipment"],
            "tag": result["tag"],
            "unit": result["unit"],
            "time_basis": result["time_basis"],
            "filter": result["filter"],
        },
        "latest": {key: latest[key] for key in (
            "id", "kind", "status", "at", "source_name", "expected_rows", "observed_rows", "missing_rows"
        )},
        "previous_result": result["previous_result"],
        "summary": result["summary"],
        "title": title,
        "paragraphs": paragraphs,
        "evidence": EVIDENCE[question],
    }
