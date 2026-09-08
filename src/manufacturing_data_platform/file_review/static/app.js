"use strict";

const $ = (id) => document.getElementById(id);
const state = { csrf: null, datasets: [], active: null, query: null, busy: false, queryGeneration: 0, limits: { upload_bytes: 8 * 1024 * 1024, rows: 50000, datasets: 10 } };
const statusNames = { ready: "파일 검증 완료", incomplete: "전달 미완료", blocked: "파일 수정 필요" };
const qualityNames = { good: "Good 제공", unspecified: "미제공", uncertain: "Uncertain 제공", bad: "Bad 제공" };
const kindNames = { import: "파일 검사", sample: "샘플 검사", replace: "수정 파일 검사", retry: "보관 원본 재검사", "delivery-check": "전달 누락 체험", delivery_check: "전달 누락 체험", recovery: "보관 원본 복구" };
const number = (value) => value === null || value === undefined || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 4, notation: Math.abs(value) >= 1e9 || (value !== 0 && Math.abs(value) < .0001) ? "scientific" : "standard" }).format(value);
const shortHash = (value) => value ? value.slice(0, 12) : "—";
const node = (tag, text, className) => { const item = document.createElement(tag); if (text !== undefined) item.textContent = text; if (className) item.className = className; return item; };
let toastTimer;

function showToast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4500);
}

function showError(message, target = "global-error") {
  $(target).textContent = message || "";
  $(target).hidden = !message;
}

function setBusy(busy, message = "처리 중…") {
  state.busy = busy;
  $("loading").hidden = !busy;
  $("loading-text").textContent = message;
  for (const id of ["upload-button", "welcome-upload", "sample-button", "welcome-sample", "replace-button", "delete-button", "query-button", "reset-range", "retry-button", "delivery-button", "recover-button", "export-button"]) $(id).disabled = busy;
  for (const item of document.querySelectorAll(".dataset-item")) item.disabled = busy;
  $("equipment-filter").disabled = busy;
  $("tag-filter").disabled = busy;
  $("main").setAttribute("aria-busy", String(busy));
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && !["GET", "HEAD"].includes(options.method)) headers.set("X-Review-CSRF", state.csrf || "");
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  if (!response.ok) {
    let description;
    try { const payload = await response.json(); description = payload.error?.message || payload.detail; } catch (_) { /* Preserve a useful error for non-JSON failures. */ }
    if (response.status === 401 || response.status === 403) description = "작업 공간이 만료되었거나 요청을 확인할 수 없습니다. 페이지를 새로고침한 뒤 다시 시도하세요.";
    throw new Error(typeof description === "string" ? description : `요청을 완료하지 못했습니다 (${response.status}). 잠시 후 다시 시도하세요.`);
  }
  return options.binary ? response : response.json();
}

async function action(message, work) {
  if (state.busy) return;
  showError("");
  setBusy(true, message);
  try { await work(); } catch (error) { showError(error.message || "작업을 완료하지 못했습니다."); } finally { setBusy(false); }
}

function dateLabel(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").replace(/\.0+(?=Z|\+00:00|$)/, "").replace(/(?:Z|\+00:00)$/, "");
}

function attemptDate(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return dateLabel(value);
  return new Intl.DateTimeFormat("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(parsed);
}

function currentDataset() { return state.datasets.find((dataset) => dataset.id === state.active); }

function upsert(dataset) {
  const position = state.datasets.findIndex((item) => item.id === dataset.id);
  if (position < 0) state.datasets.unshift(dataset); else state.datasets[position] = dataset;
}

function renderList() {
  $("dataset-list").replaceChildren();
  $("dataset-count").textContent = `${state.datasets.length} / ${state.limits.datasets}`;
  $("list-empty").hidden = state.datasets.length > 0;
  for (const dataset of state.datasets) {
    const button = node("button", undefined, "dataset-item");
    button.type = "button";
    button.setAttribute("aria-current", String(dataset.id === state.active));
    button.setAttribute("aria-label", `${dataset.name}, ${statusNames[dataset.latest?.status] || "검사 대기"}`);
    button.title = dataset.name;
    button.disabled = state.busy;
    const text = node("span", undefined, "dataset-item-text");
    text.append(node("strong", dataset.name), node("small", `${dataset.source_kind === "sample" ? "공개 샘플" : "내 CSV"} · ${statusNames[dataset.latest?.status] || "검사 대기"}`));
    button.append(node("span", "CSV", "file-icon"), text, node("span", undefined, `dataset-dot ${dataset.latest?.status || ""}`));
    button.addEventListener("click", () => action("파일을 불러오는 중…", async () => {
      const payload = await request(`/api/datasets/${encodeURIComponent(dataset.id)}`);
      upsert(payload.dataset);
      await selectDataset(payload.dataset.id, true);
    }));
    $("dataset-list").append(button);
  }
}

function addMetadata(label, value, mono = false) {
  const term = node("dt", label);
  const definition = node("dd", value || "—", mono ? "mono" : undefined);
  $("source-metadata").append(term, definition);
}

function renderHistory(dataset) {
  const history = dataset.history?.length ? dataset.history : dataset.latest ? [dataset.latest] : [];
  $("history-count").textContent = `${history.length}건`;
  $("history-list").replaceChildren();
  for (const attempt of history) {
    const item = node("li", undefined, "history-item");
    const time = node("time", attemptDate(attempt.at));
    if (attempt.at) time.dateTime = attempt.at;
    item.append(node("strong", `${kindNames[attempt.kind] || "파일 검사"} · ${statusNames[attempt.status] || attempt.status}`), time);
    const result = attempt.status === "ready" ? `버전 ${shortHash(attempt.version)} · ${attempt.version_changed ? "결과 갱신" : "같은 결과 유지"}` : `전달 ${number(attempt.observed_rows)} / 기대 ${number(attempt.expected_rows)}행 · 분석 결과 갱신 안 함`;
    item.append(node("span", result, "history-result"));
    $("history-list").append(item);
  }
}

function populateTags(dataset, preferredTag) {
  const equipment = $("equipment-filter").value;
  const series = dataset.current?.series.filter((item) => item.equipment === equipment) || [];
  $("tag-filter").replaceChildren();
  for (const item of series) {
    const option = node("option", `${item.tag}${item.unit ? ` · ${item.unit}` : ""}`);
    option.value = item.tag;
    $("tag-filter").append(option);
  }
  if (series.some((item) => item.tag === preferredTag)) $("tag-filter").value = preferredTag;
}

function renderDataset(dataset, resetFilters) {
  const latest = dataset.latest;
  const current = dataset.current;
  const previousEquipment = resetFilters ? "" : $("equipment-filter").value;
  const previousTag = resetFilters ? "" : $("tag-filter").value;
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  $("dataset-title").textContent = dataset.name;
  document.title = `${dataset.name} · Telemetry Review`;
  $("source-kind").textContent = dataset.source_kind === "sample" ? "PUBLIC SAMPLE / METROPT-3" : "YOUR CSV / FILE REVIEW";
  $("dataset-subtitle").textContent = `최근 검사 ${attemptDate(latest?.at)} · ${dataset.source_kind === "sample" ? "공개 압축기 기록" : "업로드한 파일"}`;
  $("attempt-banner").className = `attempt-banner ${latest?.status || "blocked"}`;
  $("attempt-symbol").textContent = latest?.status === "ready" ? "✓" : "!";
  $("attempt-status").textContent = statusNames[latest?.status] || "검사 대기";
  $("attempt-title").textContent = latest?.status === "ready" ? "파일 검증을 마쳤습니다." : latest?.status === "incomplete" ? "최근 전달이 완료되지 않았습니다." : "최근 파일에서 수정할 항목이 발견됐습니다.";
  $("attempt-description").textContent = latest?.status === "ready"
    ? `${number(latest.observed_rows)}개 관측값을 분석할 수 있습니다. 제공되지 않은 품질 정보는 ‘미제공’으로 남습니다.`
    : latest?.status === "incomplete"
      ? `기대 ${number(latest.expected_rows)}행 중 ${number(latest.missing_rows)}행이 전달되지 않았습니다. ${current ? "아래에는 이전에 검증한 결과를 유지합니다." : "아직 분석할 수 있는 결과가 없습니다."}`
      : `${current ? "아래에는 이전에 검증한 파일의 결과를 유지합니다. " : ""}표시된 항목을 수정한 CSV로 교체해 주세요.`;
  const issues = latest?.issues || [];
  $("attempt-issues").replaceChildren(...issues.slice(0, 8).map((issue) => node("li", `${issue.row ? `데이터 ${issue.row}행: ` : ""}${issue.message || issue.code}`)));
  if (issues.length > 8) $("attempt-issues").append(node("li", `외 ${issues.length - 8}개 항목. 먼저 표시된 오류를 수정해 주세요.`));
  $("attempt-issues").hidden = !issues.length;
  if (dataset.current_error) {
    $("attempt-banner").className = "attempt-banner blocked";
    $("attempt-symbol").textContent = "!";
    $("attempt-status").textContent = "저장 결과 확인 필요";
    $("attempt-title").textContent = "저장된 결과의 무결성을 확인할 수 없습니다.";
    $("attempt-description").textContent = `${dataset.current_error.message} 이 결과는 분석하거나 내려받을 수 없습니다. 원본 파일을 확인해 다시 올리거나 파일을 삭제해 주세요.`;
  }
  $("analysis-area").hidden = !current;
  $("no-current").hidden = !!current;
  $("query-results").hidden = true;
  showError("", "query-error");
  state.query = null;
  $("source-metadata").replaceChildren();
  addMetadata("최근 입력", latest?.source_name);
  addMetadata("입력 SHA-256", latest?.source_sha256, true);
  if (current) {
    addMetadata("분석 파일", current.source_name);
    addMetadata("분석 버전", current.version, true);
    addMetadata("분석 원본 SHA", current.source_sha256, true);
    addMetadata("전체 관측값", `${number(current.rows)}행`);
    addMetadata("원본 시각 범위", `${dateLabel(current.range?.start)} – ${dateLabel(current.range?.end)}`);
    addMetadata("시각 기준", current.time_basis === "unspecified" ? "원본 시각 · 시간대 미제공" : "UTC로 정규화");
    $("result-basis").textContent = `${latest?.status === "ready" ? "분석 중인 파일" : "유지된 이전 파일"} · ${current.source_name}`;
    $("result-version").textContent = `버전 ${shortHash(current.version)}`;
    $("result-version").title = current.version;
    $("time-basis").textContent = current.time_basis === "unspecified" ? "원본 시각 · 시간대 미제공 · 빈 시각은 전체 기간" : "입력과 표시는 UTC 기준 · 빈 시각은 전체 기간";
    const equipment = [...new Set((current.series || []).map((item) => item.equipment))];
    $("equipment-filter").replaceChildren(...equipment.map((value) => { const option = node("option", value); option.value = value; return option; }));
    if (equipment.includes(previousEquipment)) $("equipment-filter").value = previousEquipment;
    populateTags(dataset, previousTag);
    if (resetFilters) { $("start-filter").value = ""; $("end-filter").value = ""; }
    const start = dateLabel(current.range?.start);
    const end = dateLabel(current.range?.end);
    $("start-filter").title = `원본 첫 시각: ${start}`;
    $("end-filter").title = `원본 마지막 시각: ${end}. 종료 시각과 같은 관측값은 포함하지 않습니다.`;
  }
  $("sample-attribution").hidden = dataset.source_kind !== "sample";
  $("sample-exercise").hidden = dataset.source_kind !== "sample";
  renderHistory(dataset);
}

async function selectDataset(id, resetFilters = false) {
  const changed = state.active !== id;
  state.active = id;
  const dataset = currentDataset();
  state.queryGeneration += 1;
  renderList();
  if (!dataset) {
    state.query = null;
    $("workspace").hidden = true;
    $("welcome").hidden = false;
    document.title = "Telemetry Review · 설비 데이터 검토";
    return;
  }
  renderDataset(dataset, resetFilters || changed);
  if (dataset.current) await loadQuery();
}

function selectedParameters(dataset) {
  const params = new URLSearchParams({ equipment: $("equipment-filter").value, tag: $("tag-filter").value, version: dataset.current.version });
  for (const side of ["start", "end"]) {
    let value = $(`${side}-filter`).value;
    if (value && value.length === 16) value += ":00";
    if (value && dataset.current.time_basis !== "unspecified") value += "Z";
    if (value) params.set(side, value);
  }
  return params;
}

async function loadQuery() {
  const dataset = currentDataset();
  if (!dataset?.current) return;
  const generation = ++state.queryGeneration;
  state.query = null;
  $("query-results").hidden = true;
  showError("", "query-error");
  try {
    const params = selectedParameters(dataset);
    const result = await request(`/api/datasets/${encodeURIComponent(dataset.id)}/query?${params}`);
    if (generation !== state.queryGeneration || dataset.id !== state.active) return;
    state.query = { result, datasetId: dataset.id, params: new URLSearchParams(params) };
    state.query.params.set("version", result.version);
    renderQuery(result);
  } catch (error) {
    if (generation === state.queryGeneration) showError(error.message, "query-error");
  }
}

function svgElement(tag, attributes = {}, text) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, String(value));
  if (text !== undefined) element.textContent = text;
  return element;
}

function timestampMs(value) {
  const text = String(value);
  return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/.test(text) ? text : `${text}Z`);
}

function renderChart(result) {
  const root = $("chart");
  root.replaceChildren();
  const points = (result.points || []).filter((point) => Number.isFinite(point.value) && Number.isFinite(timestampMs(point.timestamp)));
  if (!points.length) {
    const empty = node("div", undefined, "chart-empty");
    empty.append(node("strong", "이 구간에는 관측값이 없습니다."), node("span", "조회 시각을 조정하거나 전체 기간을 확인하세요."));
    root.append(empty);
    return;
  }
  const width = Math.max(290, root.clientWidth - (window.innerWidth <= 850 ? 10 : 28));
  const height = Math.max(200, root.clientHeight);
  const box = { left: 59, right: 24, top: 24, bottom: 41 };
  const plotWidth = width - box.left - box.right;
  const plotHeight = height - box.top - box.bottom;
  const times = points.map((point) => timestampMs(point.timestamp));
  const values = points.map((point) => point.value);
  const minTime = Math.min(...times), maxTime = Math.max(...times);
  const magnitude = Math.max(...values.map((value) => Math.abs(value))) || 1;
  const lowest = Math.min(...values) / magnitude, highest = Math.max(...values) / magnitude;
  const padding = (highest - lowest) * .12 || .01;
  const bottom = lowest - padding, top = highest + padding;
  const x = (time) => box.left + (maxTime === minTime ? plotWidth / 2 : (time - minTime) / (maxTime - minTime) * plotWidth);
  const y = (value) => box.top + (top - value / magnitude) / (top - bottom) * plotHeight;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-labelledby": "plot-accessible-title plot-accessible-description", preserveAspectRatio: "xMidYMid meet" });
  svg.append(svgElement("title", { id: "plot-accessible-title" }, `${result.tag} 관측값 추이`), svgElement("desc", { id: "plot-accessible-description" }, `선택한 ${result.summary.count}개 중 ${points.length}개의 실제 관측값. 최솟값 ${number(result.summary.min)}, 최댓값 ${number(result.summary.max)} ${result.unit || ""}. 아래 표에서 관측값을 확인할 수 있습니다.`));
  for (let i = 0; i < 5; i += 1) {
    const value = bottom + (top - bottom) * i / 4;
    const pos = box.top + (top - value) / (top - bottom) * plotHeight;
    const label = Math.max(-Number.MAX_VALUE / magnitude, Math.min(Number.MAX_VALUE / magnitude, value)) * magnitude;
    svg.append(svgElement("line", { x1: box.left, y1: pos, x2: width - box.right, y2: pos, stroke: "#edf1ed", "stroke-width": 1 }), svgElement("text", { x: box.left - 12, y: pos + 4, "text-anchor": "end", fill: "#8b9b8c", "font-size": 11 }, number(label)));
  }
  const sampled = result.summary.count > points.length;
  const hasGapFlags = points.every((point) => typeof point.gap_before === "boolean");
  let path = "";
  points.forEach((point, index) => {
    const gap = index > 0 && (hasGapFlags ? point.gap_before : sampled || (times[index] - times[index - 1]) / 1000 > 60);
    path += `${index === 0 || gap ? "M" : "L"}${x(times[index]).toFixed(2)},${y(point.value).toFixed(2)} `;
  });
  svg.append(svgElement("path", { d: path, fill: "none", stroke: "#13857b", "stroke-width": 1.8, "stroke-linejoin": "round", "stroke-linecap": "round" }));
  // Dots keep isolated observations visible without inventing interpolated values.
  points.forEach((point, index) => {
    const dot = svgElement("circle", { cx: x(times[index]), cy: y(point.value), r: points.length < 30 ? 3 : 1.55, fill: "#13857b" });
    dot.append(svgElement("title", {}, `${dateLabel(point.timestamp)} · ${number(point.value)} ${result.unit || ""} · ${qualityNames[point.quality] || point.quality}`));
    svg.append(dot);
  });
  const labelIndices = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])];
  for (const index of labelIndices) {
    const timestamp = dateLabel(points[index].timestamp);
    const label = timestamp.slice(5, 16);
    svg.append(svgElement("text", { x: x(times[index]), y: height - 15, "text-anchor": index === 0 ? "start" : index === points.length - 1 ? "end" : "middle", fill: "#8b9b8c", "font-size": 11 }, label));
  }
  root.append(svg);
}

function renderQuery(result) {
  $("query-results").hidden = false;
  $("previous-query").hidden = !result.previous_result;
  $("previous-query").textContent = `${result.latest_status === "ready" ? "최신 검사와 다른 버전을 조회하고 있습니다." : "최근 검사가 완료되지 않아 이전 검증 결과를 유지합니다."} 표시와 내려받기 모두 버전 ${shortHash(result.version)}을 사용합니다.`;
  const start = result.filter?.start ? `${dateLabel(result.filter.start)}부터` : "첫 관측부터";
  const end = result.filter?.end ? `${dateLabel(result.filter.end)} 전까지` : "마지막 관측까지";
  $("query-selection").textContent = `${result.equipment} / ${result.tag} · ${start} ${end} · ${result.time_basis === "unspecified" ? "시간대 미제공" : "UTC"}`;
  for (const field of ["count", "mean", "min", "max"]) $(`metric-${field}`).textContent = number(result.summary[field]);
  for (const element of document.querySelectorAll(".metric-unit")) element.textContent = result.unit || "단위 없음";
  $("chart-title").textContent = `${result.tag} 추이`;
  $("chart-description").textContent = `${number(result.displayed_points ?? result.points?.length ?? 0)}개 실제 값 표시${result.summary.count > (result.points?.length || 0) ? ` · 통계는 전체 ${number(result.summary.count)}개 기준` : ""}`;
  const maximumGap = result.summary.max_gap_seconds;
  $("gap-description").textContent = result.summary.count < 2 ? "간격을 비교할 관측값이 부족합니다." : `60초 초과 원본 간격 ${number(result.summary.gap_count)}곳 · 최대 ${number(maximumGap)}초${result.summary.gap_count ? " · 공백 구간은 선을 잇지 않습니다" : ""}`;
  const qualities = result.summary.quality_counts || {};
  $("quality-description").textContent = `제공된 품질: Good ${number(qualities.good || 0)}행, 미제공 ${number(qualities.unspecified || 0)}행. ${qualities.unspecified ? "미제공은 정상 품질을 뜻하지 않습니다. " : ""}파일 검증은 센서 정확도를 보증하지 않으며, 시간 공백은 설비 중단이나 누락 행 수로 해석하지 않습니다.`;
  renderChart(result);
  const rows = result.rows || [];
  $("preview-description").textContent = `${number(rows.length)} / ${number(result.summary.count)}행`;
  $("preview-body").replaceChildren();
  if (!rows.length) { const row = node("tr"); const cell = node("td", "선택 구간에 관측값이 없습니다."); cell.colSpan = 6; row.append(cell); $("preview-body").append(row); }
  for (const item of rows) {
    const row = node("tr");
    for (const [value, className] of [[dateLabel(item.timestamp)], [item.equipment ?? result.equipment], [item.tag ?? result.tag], [number(item.value), "numeric"], [item.unit ?? result.unit]]) row.append(node("td", value, className));
    const qualityCell = node("td");
    qualityCell.append(node("span", qualityNames[item.quality] || item.quality || "미제공", `quality-pill ${["good", "bad", "uncertain"].includes(item.quality) ? item.quality : ""}`));
    row.append(qualityCell);
    $("preview-body").append(row);
  }
}

async function upload(file, replace) {
  if (!file || state.busy) return;
  if (file.size > state.limits.upload_bytes) { showError(`파일이 업로드 한도 ${number(state.limits.upload_bytes / 1024 / 1024)} MiB를 초과합니다. 필요한 구간만 나누어 업로드해 주세요.`); return; }
  if (!file.size) { showError("빈 파일입니다. CSV 내용이 있는 파일을 선택해 주세요."); return; }
  const dataset = currentDataset();
  if (replace && !dataset) return;
  await action(replace ? "수정 파일을 검사하는 중…" : "파일을 업로드하고 검사하는 중…", async () => {
    const path = replace ? `/api/datasets/${encodeURIComponent(dataset.id)}/replace` : "/api/datasets";
    const payload = await request(`${path}?${new URLSearchParams({ name: file.name })}`, { method: "POST", body: file, headers: { "Content-Type": "text/csv; charset=utf-8" } });
    upsert(payload.dataset);
    await selectDataset(payload.dataset.id, !replace || payload.dataset.latest?.status === "ready");
    showToast(payload.dataset.latest?.status === "ready" ? "파일 검증을 완료했습니다." : "검사 결과를 확인하고 파일을 수정해 주세요.");
  });
}

async function openSample() {
  await action("공개 샘플을 준비하고 검사하는 중…", async () => {
    const payload = await request("/api/datasets/sample", { method: "POST" });
    upsert(payload.dataset);
    await selectDataset(payload.dataset.id, true);
    showToast("공개 샘플을 열었습니다. 측정 항목과 시간 구간을 골라보세요.");
  });
}

async function runAttempt(route, message, resultMessage) {
  const dataset = currentDataset();
  if (!dataset) return;
  await action(message, async () => {
    const payload = await request(`/api/datasets/${encodeURIComponent(dataset.id)}/${route}`, { method: "POST" });
    upsert(payload.dataset);
    await selectDataset(payload.dataset.id);
    showToast(resultMessage);
  });
}

async function downloadResult() {
  const selected = state.query;
  if (!selected) return;
  await action("선택한 버전의 결과를 준비하는 중…", async () => {
    const response = await request(`/api/datasets/${encodeURIComponent(selected.datasetId)}/export?${selected.params}`, { binary: true });
    const blob = await response.blob();
    const link = node("a");
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = `telemetry-review-${shortHash(selected.result.version)}.zip`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    showToast("관측값 CSV와 검토 기록을 ZIP으로 내려받습니다.");
  });
}

function installEvents() {
  let resizeFrame;
  window.addEventListener("resize", () => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => { if (state.query) renderChart(state.query.result); });
  });
  for (const id of ["upload-button", "welcome-upload"]) $(id).addEventListener("click", () => $("upload-input").click());
  $("replace-button").addEventListener("click", () => $("replace-input").click());
  for (const [id, replace] of [["upload-input", false], ["replace-input", true]]) $(id).addEventListener("change", (event) => { const file = event.target.files?.[0]; event.target.value = ""; upload(file, replace); });
  for (const id of ["sample-button", "welcome-sample"]) $(id).addEventListener("click", openSample);
  $("equipment-filter").addEventListener("change", () => { const dataset = currentDataset(); if (dataset) populateTags(dataset); });
  $("query-form").addEventListener("submit", (event) => { event.preventDefault(); action("선택 구간을 분석하는 중…", loadQuery); });
  $("reset-range").addEventListener("click", () => { $("start-filter").value = ""; $("end-filter").value = ""; action("전체 기간을 분석하는 중…", loadQuery); });
  $("export-button").addEventListener("click", downloadResult);
  $("retry-button").addEventListener("click", () => runAttempt("retry", "보관 원본을 다시 검사하는 중…", "보관 원본의 재검사를 마쳤습니다. 최근 검사 결과를 확인해 주세요."));
  $("delivery-button").addEventListener("click", () => runAttempt("delivery-check", "샘플의 일부 행을 제외하고 전달하는 중…", "전달 누락을 기록했습니다. 이전 검증 결과는 유지됩니다."));
  $("recover-button").addEventListener("click", () => runAttempt("retry", "보관된 전체 원본으로 복구하는 중…", "보관 원본을 다시 검사했습니다. 결과 버전과 최근 기록을 확인해 주세요."));
  $("delete-button").addEventListener("click", () => { $("delete-dialog").returnValue = "cancel"; $("delete-dialog").showModal(); });
  $("delete-dialog").addEventListener("close", () => {
    if ($("delete-dialog").returnValue !== "delete") return;
    const dataset = currentDataset();
    if (!dataset) return;
    action("파일과 검사 기록을 삭제하는 중…", async () => {
      await request(`/api/datasets/${encodeURIComponent(dataset.id)}`, { method: "DELETE" });
      state.datasets = state.datasets.filter((item) => item.id !== dataset.id);
      await selectDataset(state.datasets[0]?.id || null, true);
      showToast("파일과 검사 기록을 삭제했습니다.");
    });
  });
  const dropzone = $("dropzone");
  for (const eventName of ["dragenter", "dragover"]) dropzone.addEventListener(eventName, (event) => { event.preventDefault(); if (!state.busy) dropzone.classList.add("dragover"); });
  for (const eventName of ["dragleave", "drop"]) dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.remove("dragover"); });
  dropzone.addEventListener("drop", (event) => {
    const files = event.dataTransfer?.files;
    if (files?.length > 1) { showError("한 번에 CSV 파일 하나를 올려주세요."); return; }
    upload(files?.[0], false);
  });
  // Dropping a file outside the upload area must not navigate away from the workspace.
  document.addEventListener("dragover", (event) => { if (Array.from(event.dataTransfer?.types || []).includes("Files")) event.preventDefault(); });
  document.addEventListener("drop", (event) => { if (event.dataTransfer?.files?.length) event.preventDefault(); });
}

async function initialize() {
  installEvents();
  await action("작업 공간을 불러오는 중…", async () => {
    const session = await request("/api/session");
    state.csrf = session.csrf_token;
    state.limits = { ...state.limits, ...session.limits };
    $("format-hint").textContent = `UTF-8 · 최대 ${number(state.limits.upload_bytes / 1024 / 1024)} MiB · ${number(state.limits.rows)}행`;
    const payload = await request("/api/datasets");
    state.datasets = payload.datasets;
    await selectDataset(state.datasets[0]?.id || null, true);
  });
}

initialize();
