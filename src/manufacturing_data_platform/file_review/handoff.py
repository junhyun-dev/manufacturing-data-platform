"""Human-readable rendering of the exact portable export manifest."""

import json


LIMITATIONS_KO = {
    "File validation does not certify physical sensor accuracy.":
        "파일 검증은 물리 센서의 정확도나 설비 상태를 보증하지 않습니다.",
    "Unspecified source quality is not Good quality.":
        "원본에서 품질이 미제공인 관측값은 Good 품질로 간주하지 않습니다.",
    "Intervals above 60 seconds are descriptive gaps, not inferred outages.":
        "60초 초과 간격은 원본 시각의 설명이며 누락 행 수나 설비 중단을 뜻하지 않습니다.",
    "Sample mean over selected observations; no interpolation or time weighting.":
        "평균은 선택 관측값의 표본 평균이며 보간하거나 시간 가중하지 않았습니다.",
}


def _literal(value):
    """Render manifest data without rounding, and quote untrusted text visibly."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _stat(value):
    return "없음" if value is None else _literal(value)


def _bound(value, missing):
    return f"없음 — {missing}" if value is None else value


def render_review_text(manifest):
    """Return UTF-8 text derived only from the manifest written beside it."""
    summary = manifest["summary"]
    quality = summary["quality_counts"]
    count = summary["count"]
    latest_status = manifest["latest_status"]
    previous_result = manifest["previous_result"]
    status_label = {"ready": "파일 검증 완료", "incomplete": "전달 미완료", "blocked": "파일 수정 필요"}[latest_status]

    if not previous_result:
        result_note = "내보내는 버전은 준비 시 확인한 최신 성공 결과입니다."
    elif latest_status == "ready":
        result_note = "내보내는 버전은 준비 시 확인한 최신 성공 결과와 다른, 명시적으로 고른 이전 버전입니다."
    else:
        result_note = "최근 검사가 완료되지 않아, 이 ZIP에는 이전에 검증해 보관한 결과를 내보냅니다."

    if count < 2:
        gap_note = "관측값이 2개 미만이므로 간격을 판단할 수 없습니다."
    else:
        gap_note = (
            f"60초 초과 원본 간격: {_literal(summary['gap_count'])}곳\n"
            f"최대 원본 간격(초): {_stat(summary['max_gap_seconds'])}"
        )

    limitations = [LIMITATIONS_KO.get(item, _literal(item)) for item in manifest["limitations"]]
    escaped = manifest["spreadsheet_escape"]
    text = f"""Telemetry Review · 검토 요약

읽는 순서
1. review.txt — 이 조회의 범위, 결과, 출처와 한계를 먼저 읽습니다.
2. observations.csv — 선택 구간의 전체 관측값을 재분석합니다.
3. manifest.json — 같은 내용을 기계가 읽을 수 있는 출처·hash 기록으로 확인합니다.

검토 대상
원본 파일: {_literal(manifest['source_name'])}
설비: {_literal(manifest['equipment'])}
측정 항목: {_literal(manifest['tag'])}
단위: {_literal(manifest['unit'])}

조회 조건
시각 기준: {'UTC로 정규화' if manifest['time_basis'] == 'utc' else '원본 시각 · 시간대 미제공'} ({manifest['time_basis']})
시작(포함): {_bound(manifest['filter']['start'], '하한 필터 없음')}
종료(미포함): {_bound(manifest['filter']['end'], '상한 필터 없음')}
범위 규칙: 시작 포함, 종료 미포함 [start, end)

선택 결과
관측값 수: {_literal(count)}
표본 평균: {_stat(summary['mean'])}
최솟값: {_stat(summary['min'])}
최댓값: {_stat(summary['max'])}
품질 수: Good {_literal(quality['good'])}, 미제공 {_literal(quality['unspecified'])}, Uncertain {_literal(quality['uncertain'])}, Bad {_literal(quality['bad'])}
{gap_note}

내보내기 준비 시점의 결과 상태
최근 검사: {status_label}
내보내는 결과: {'이전 검증 결과' if previous_result else '최신 검증 결과'}
{result_note}
이 상태는 ZIP을 준비할 때 확인한 값이며 이후 바뀔 수 있습니다.

출처와 무결성
파일 버전 SHA-256: {manifest['version']}
원본 파일 SHA-256: {manifest['source_sha256']}
observations.csv SHA-256: {manifest['observations_sha256']}
서버가 ZIP을 준비한 시각(UTC): {manifest['generated_at']}
이 생성 시각은 observations.csv의 관측 시각이 아닙니다.

스프레드시트 안전 처리
observations.csv의 텍스트 셀 {escaped['escaped_text_cells']}개에는 수식 실행을 막기 위해 {_literal(escaped['prefix'])} 접두 문자를 붙였습니다.
수치 값과 CSV 스키마는 바꾸지 않았으며 위 observations.csv hash는 ZIP 안의 실제 바이트 기준입니다.

해석 한계
"""
    text += "\n".join(f"- {item}" for item in limitations)
    text += """
- 이 검토 결과는 물리 고장 진단이 아닙니다.
"""
    return text.encode("utf-8")
