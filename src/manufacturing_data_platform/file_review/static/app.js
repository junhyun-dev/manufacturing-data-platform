"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  csrf: null, datasets: [], active: null, query: null, busy: false, queryGeneration: 0,
  capabilities: { uploads: true, sample: true, accounts: false }, limits: { upload_bytes: 8 * 1024 * 1024, rows: 50000, datasets: 10 },
  explanation: { generation: 0, controller: null, timeout: null, loading: false, question: null, requestKey: null, answerKey: null, retryVisible: false, returnFocus: null },
  map: { expanded: false, unavailable: null },
  mapFullscreen: {
    active: false, generation: 0, acquiredNative: false, nativeRequested: false,
    enteredWithNative: false, priorWide: false, priorExpanded: false,
    scrollX: 0, scrollY: 0, originalParent: null, originalNext: null,
    launcherParent: null, launcherNext: null,
    inertRecords: [], focusAfterExit: true, cancelledNativeEntry: false,
    lateExitPending: false, nativeExitPending: false
  },
  search: { page: 0 },
  view: { wide: false, fullscreenPending: false, returningToBase: false, baseScrollX: 0, baseScrollY: 0, suppressFullscreenFocusUntil: 0 }
};
const explanationNarrow = window.matchMedia("(max-width: 850px)");
const EXPLANATION_TIMEOUT_MS = 10000;
const TAG_SEARCH_PAGE_SIZE = 20;
const statusNames = { ready: "파일 검증 완료", incomplete: "전달 미완료", blocked: "파일 수정 필요" };
const qualityNames = { good: "Good 제공", unspecified: "미제공", uncertain: "Uncertain 제공", bad: "Bad 제공" };
const kindNames = { import: "파일 검사", sample: "샘플 검사", replace: "수정 파일 검사", retry: "보관 원본 재검사", "delivery-check": "전달 누락 체험", delivery_check: "전달 누락 체험", recovery: "보관 원본 복구" };
const number = (value) => value === null || value === undefined || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 4, notation: Math.abs(value) >= 1e9 || (value !== 0 && Math.abs(value) < .0001) ? "scientific" : "standard" }).format(value);
const shortHash = (value) => value ? value.slice(0, 12) : "—";
const node = (tag, text, className) => { const item = document.createElement(tag); if (text !== undefined) item.textContent = text; if (className) item.className = className; return item; };
let toastTimer;
let mapCanvas;

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
  for (const id of ["upload-button", "welcome-upload", "sample-button", "welcome-sample", "replace-button", "delete-button", "query-button", "reset-range", "retry-button", "delivery-button", "recover-button", "export-button", "explanation-launcher"]) $(id).disabled = busy;
  for (const item of document.querySelectorAll(".dataset-item")) item.disabled = busy;
  for (const item of document.querySelectorAll("[data-map-tag]")) item.disabled = busy;
  for (const item of document.querySelectorAll("[data-search-tag]")) item.disabled = busy;
  $("equipment-filter").disabled = busy;
  $("tag-filter").disabled = busy;
  $("map-refresh").disabled = busy;
  $("map-source-link").disabled = busy || !!state.map.unavailable || !currentDataset()?.current;
  mapCanvas?.setBusy(busy);
  $("main").setAttribute("aria-busy", String(busy));
  updateQueryControls();
  updateExplanationControls();
  updateMapFullscreenControls();
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && !["GET", "HEAD"].includes(options.method)) headers.set("X-Review-CSRF", state.csrf || "");
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  if (!response.ok) {
    let description, code;
    try { const payload = await response.json(); description = payload.error?.message || payload.detail; code = payload.error?.code; } catch (_) { /* Preserve a useful error for non-JSON failures. */ }
    if (response.status === 401 || response.status === 403) description = "작업 공간이 만료되었거나 요청을 확인할 수 없습니다. 페이지를 새로고침한 뒤 다시 시도하세요.";
    const error = new Error(typeof description === "string" ? description : `요청을 완료하지 못했습니다 (${response.status}). 잠시 후 다시 시도하세요.`);
    error.status = response.status;
    error.code = code;
    throw error;
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

function isReviewContextError(error) {
  return [401, 403, 404].includes(error?.status) || ["INTEGRITY", "CONTEXT_CHANGED"].includes(error?.code);
}

function nativeFullscreenActive() {
  return Boolean(document.fullscreenElement);
}

function reviewViewAvailable() {
  return !!currentDataset()?.current && !state.map.unavailable;
}

function modalOwnsFocus() {
  return !!document.querySelector("dialog:modal") || !$("explanation-panel").hidden;
}

function mapEntryBlockedByModal() {
  return !!document.querySelector("dialog:modal") || (!$("explanation-panel").hidden && explanationNarrow.matches) || $("application-shell").inert;
}

function redrawReviewChart() {
  requestAnimationFrame(() => {
    if (state.query) renderChart(state.query.result);
    mapCanvas?.resize();
  });
}

function updateMapFullscreenControls() {
  const active = state.mapFullscreen.active;
  const available = reviewViewAvailable();
  const cancellableEntry = active && state.mapFullscreen.nativeRequested && !state.mapFullscreen.nativeExitPending;
  const toggle = $("map-fullscreen-toggle");
  toggle.textContent = active ? "지도 보기 나가기" : "지도 전체화면";
  toggle.setAttribute("aria-pressed", String(active));
  toggle.disabled = (state.view.fullscreenPending && !cancellableEntry) || (!active && !available);
  $("map-review-link").disabled = !active || (state.view.fullscreenPending && !cancellableEntry);
  $("map-source-link").disabled = state.busy || (state.view.fullscreenPending && !cancellableEntry) || !!state.map.unavailable || !currentDataset()?.current;
}

function syncMapFullscreenStatus(message) {
  updateMapFullscreenControls();
  if (message) {
    $("map-fullscreen-status").textContent = message;
  } else if (state.mapFullscreen.active && nativeFullscreenActive()) {
    $("map-fullscreen-status").textContent = "브라우저 전체화면에서 지도를 보고 있습니다. Esc 또는 지도 보기 나가기로 돌아갈 수 있습니다.";
  } else if (state.mapFullscreen.active) {
    $("map-fullscreen-status").textContent = "브라우저 화면 안에서 지도를 크게 보고 있습니다. 지도 보기 나가기로 돌아갈 수 있습니다.";
  } else if (reviewViewAvailable()) {
    $("map-fullscreen-status").textContent = "지도를 화면에 크게 펼쳐 살펴볼 수 있습니다.";
  } else {
    $("map-fullscreen-status").textContent = "분석할 수 있는 현재 결과가 있어야 지도를 크게 볼 수 있습니다.";
  }
}

function setMapBackgroundInert() {
  const records = [document.querySelector(".sidebar"), $("main")].filter(Boolean).map((element) => ({ element, inert: element.inert }));
  for (const record of records) record.element.inert = true;
  state.mapFullscreen.inertRecords = records;
}

function restoreMapBackgroundInert() {
  for (const record of state.mapFullscreen.inertRecords) record.element.inert = record.inert;
  state.mapFullscreen.inertRecords = [];
}

function restoreDedicatedMap({ focus = true, preserveCancelledEntry = false } = {}) {
  const mapState = state.mapFullscreen;
  if (!mapState.active || !mapState.originalParent) return;
  const section = $("equipment-map-section");
  const parent = mapState.originalParent;
  const next = mapState.originalNext;
  mapState.active = false;
  mapState.generation += 1;
  document.body.classList.remove("map-fullscreen-open");
  if (next?.parentNode === parent) parent.insertBefore(section, next); else parent.append(section);
  const launcher = $("explanation-launcher");
  if (mapState.launcherNext?.parentNode === mapState.launcherParent) mapState.launcherParent.insertBefore(launcher, mapState.launcherNext);
  else mapState.launcherParent.append(launcher);
  mapState.launcherParent = null;
  mapState.launcherNext = null;
  $("map-fullscreen-layer").hidden = true;
  restoreMapBackgroundInert();
  state.map.expanded = mapState.priorExpanded;
  state.view.wide = mapState.priorWide;
  const scrollX = mapState.scrollX;
  const scrollY = mapState.scrollY;
  mapState.acquiredNative = false;
  mapState.nativeRequested = false;
  mapState.nativeExitPending = false;
  mapState.enteredWithNative = false;
  mapState.originalParent = null;
  mapState.originalNext = null;
  if (!preserveCancelledEntry) mapState.cancelledNativeEntry = false;
  applyMapVisibility();
  syncReviewViewStatus();
  syncMapFullscreenStatus();
  requestAnimationFrame(() => {
    window.scrollTo(scrollX, scrollY);
    redrawReviewChart();
    if (focus && !modalOwnsFocus() && !section.hidden) {
      const target = $("map-fullscreen-toggle").disabled ? $("main") : $("map-fullscreen-toggle");
      target.focus({ preventScroll: true });
    }
  });
}

async function exitLateMapNativeEntry() {
  const mapState = state.mapFullscreen;
  if (mapState.lateExitPending) return;
  if (!nativeFullscreenActive()) {
    mapState.cancelledNativeEntry = false;
    state.view.fullscreenPending = false;
    syncReviewViewStatus();
    syncMapFullscreenStatus();
    return;
  }
  mapState.lateExitPending = true;
  state.view.fullscreenPending = true;
  updateReviewViewControls();
  try {
    await document.exitFullscreen();
  } catch (_) {
    if (nativeFullscreenActive()) {
      mapState.cancelledNativeEntry = false;
      $("review-view-status").textContent = "지도 전환 뒤 시작된 전체화면을 종료하지 못했습니다. 전체화면 나가기나 Esc를 다시 사용해 주세요.";
    }
  } finally {
    mapState.lateExitPending = false;
    if (!nativeFullscreenActive()) mapState.cancelledNativeEntry = false;
    state.view.fullscreenPending = false;
    updateReviewViewControls();
    if (!mapState.cancelledNativeEntry) syncMapFullscreenStatus();
  }
}

async function enterDedicatedMap() {
  const mapState = state.mapFullscreen;
  if (mapState.active || state.view.fullscreenPending) return;
  if (!reviewViewAvailable() || mapEntryBlockedByModal()) {
    syncMapFullscreenStatus(!reviewViewAvailable() ? "분석할 수 있는 현재 결과가 있어야 지도를 크게 볼 수 있습니다." : "열린 모달 대화 상자를 닫은 뒤 지도를 크게 볼 수 있습니다.");
    return;
  }
  const section = $("equipment-map-section");
  mapState.generation += 1;
  const generation = mapState.generation;
  mapState.active = true;
  mapState.acquiredNative = false;
  mapState.nativeRequested = false;
  mapState.nativeExitPending = false;
  mapState.enteredWithNative = nativeFullscreenActive();
  mapState.priorWide = state.view.wide;
  mapState.priorExpanded = state.map.expanded;
  mapState.scrollX = window.scrollX;
  mapState.scrollY = window.scrollY;
  mapState.originalParent = section.parentNode;
  mapState.originalNext = section.nextSibling;
  const launcher = $("explanation-launcher");
  mapState.launcherParent = launcher.parentNode;
  mapState.launcherNext = launcher.nextSibling;
  mapState.focusAfterExit = true;
  mapState.cancelledNativeEntry = false;
  const layer = $("map-fullscreen-layer");
  layer.hidden = false;
  layer.append(section);
  section.querySelector(".map-heading-actions").append(launcher);
  layer.scrollTop = 0;
  setMapBackgroundInert();
  document.body.classList.add("map-fullscreen-open");
  if (explanationNarrow.matches) state.map.expanded = true;
  applyMapVisibility();
  syncMapFullscreenStatus(mapState.enteredWithNative ? "현재 브라우저 전체화면에서 지도를 크게 보고 있습니다." : "지도를 화면에 맞춘 뒤 브라우저 전체화면을 확인하는 중입니다.");
  requestAnimationFrame(() => {
    mapCanvas?.resize();
    if (mapState.active && !modalOwnsFocus()) {
      const target = $("map-fullscreen-toggle").disabled ? $("equipment-map") : $("map-fullscreen-toggle");
      target.focus({ preventScroll: true });
    }
  });
  if (mapState.enteredWithNative) return;
  if (typeof document.documentElement.requestFullscreen !== "function") {
    syncMapFullscreenStatus("이 브라우저는 전체화면을 지원하지 않아 화면 안에서 지도를 크게 표시합니다.");
    return;
  }
  mapState.nativeRequested = true;
  state.view.fullscreenPending = true;
  updateReviewViewControls();
  updateMapFullscreenControls();
  try {
    await document.documentElement.requestFullscreen();
    if (generation !== mapState.generation || !mapState.active) {
      if (nativeFullscreenActive()) exitLateMapNativeEntry();
      return;
    }
    if (nativeFullscreenActive()) {
      mapState.acquiredNative = true;
      syncMapFullscreenStatus();
    } else {
      syncMapFullscreenStatus("전체화면 상태를 확인할 수 없어 화면 안에서 지도를 크게 표시합니다.");
    }
  } catch (_) {
    if (generation === mapState.generation && mapState.active) {
      syncMapFullscreenStatus(nativeFullscreenActive() ? undefined : "브라우저 전체화면을 시작하지 못해 화면 안에서 지도를 크게 표시합니다.");
    }
  } finally {
    if (generation === mapState.generation && mapState.active) {
      mapState.nativeRequested = false;
      state.view.fullscreenPending = false;
      updateReviewViewControls();
      updateMapFullscreenControls();
    } else if (!nativeFullscreenActive() && !mapState.lateExitPending) {
      mapState.cancelledNativeEntry = false;
      state.view.fullscreenPending = false;
      syncReviewViewStatus();
      syncMapFullscreenStatus();
    }
  }
}

async function leaveDedicatedMap({ focus = true } = {}) {
  const mapState = state.mapFullscreen;
  if (!mapState.active) return true;
  if (state.view.fullscreenPending) {
    if (!mapState.nativeRequested || mapState.nativeExitPending) return false;
    mapState.cancelledNativeEntry = true;
    restoreDedicatedMap({ focus, preserveCancelledEntry: true });
    $("map-fullscreen-status").textContent = "지도 보기를 닫았습니다. 진행 중이던 전체화면 전환을 정리하고 있습니다.";
    return true;
  }
  mapState.focusAfterExit = focus;
  if (!mapState.acquiredNative || !nativeFullscreenActive()) {
    restoreDedicatedMap({ focus });
    return true;
  }
  state.view.fullscreenPending = true;
  mapState.nativeExitPending = true;
  updateReviewViewControls();
  syncMapFullscreenStatus("브라우저 전체화면을 종료하고 검토 화면으로 돌아가는 중입니다.");
  try {
    await document.exitFullscreen();
    if (mapState.active && !nativeFullscreenActive()) restoreDedicatedMap({ focus });
    if (mapState.active && nativeFullscreenActive()) syncMapFullscreenStatus("전체화면 종료 상태를 확인하지 못했습니다. 지도 보기 나가기나 Esc를 다시 사용해 주세요.");
  } catch (_) {
    if (mapState.active && !nativeFullscreenActive()) restoreDedicatedMap({ focus });
    else if (mapState.active) syncMapFullscreenStatus("전체화면을 종료하지 못했습니다. 지도 보기 나가기나 Esc를 다시 사용해 주세요.");
  } finally {
    mapState.nativeExitPending = false;
    state.view.fullscreenPending = false;
    updateReviewViewControls();
    updateMapFullscreenControls();
  }
  return !mapState.active;
}

function abandonDedicatedMapForContextChange() {
  const mapState = state.mapFullscreen;
  if (!mapState.active) return;
  const cancelPendingEntry = mapState.nativeRequested && !nativeFullscreenActive();
  const exitAcquiredNative = mapState.acquiredNative && nativeFullscreenActive();
  if (cancelPendingEntry) mapState.cancelledNativeEntry = true;
  restoreDedicatedMap({ focus: false, preserveCancelledEntry: cancelPendingEntry });
  if (exitAcquiredNative) {
    state.view.fullscreenPending = true;
    updateReviewViewControls();
    document.exitFullscreen().catch(() => {
      if (nativeFullscreenActive()) $("review-view-status").textContent = "전체화면을 종료하지 못했습니다. 전체화면 나가기나 Esc를 다시 사용해 주세요.";
    }).finally(() => {
      state.view.fullscreenPending = false;
      updateReviewViewControls();
    });
  }
}

async function focusReviewTarget(target, { openDetails = false } = {}) {
  if (state.mapFullscreen.active && !await leaveDedicatedMap({ focus: false })) return false;
  if (!target?.isConnected || target.hidden) return false;
  if (openDetails && target instanceof HTMLDetailsElement) target.open = true;
  await new Promise((resolve) => requestAnimationFrame(resolve));
  target.tabIndex = -1;
  target.focus({ preventScroll: true });
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  return true;
}

async function returnToReviewFromMap() {
  if (state.mapFullscreen.active && !await leaveDedicatedMap({ focus: false })) return;
  const target = queryMatchesDraft() && !$("query-results").hidden ? $("query-results") : $("query-form");
  await focusReviewTarget(target);
}

function updateReviewViewControls() {
  const fullscreen = nativeFullscreenActive();
  const available = reviewViewAvailable();
  document.body.classList.toggle("review-wide", state.view.wide);
  $("review-view-bar").hidden = !currentDataset() && !state.view.wide && !fullscreen;
  $("review-wide-toggle").textContent = state.view.wide ? "기본 화면으로" : "넓게 보기";
  $("review-wide-toggle").setAttribute("aria-pressed", String(state.view.wide));
  $("review-wide-toggle").disabled = state.view.fullscreenPending || (!state.view.wide && !available);
  $("review-fullscreen-toggle").textContent = fullscreen ? "전체화면 나가기" : "전체화면";
  $("review-fullscreen-toggle").setAttribute("aria-pressed", String(fullscreen));
  $("review-fullscreen-toggle").disabled = state.view.fullscreenPending || (!fullscreen && !available);
  updateMapFullscreenControls();
}

function syncReviewViewStatus() {
  updateReviewViewControls();
  if (nativeFullscreenActive()) {
    $("review-view-status").textContent = reviewViewAvailable()
      ? "전체화면에서 검토 중입니다. Esc 또는 나가기 버튼으로 종료할 수 있습니다."
      : "전체화면에 현재 분석할 결과가 없습니다. Esc 또는 나가기 버튼으로 종료할 수 있습니다.";
  } else if (state.view.wide) {
    $("review-view-status").textContent = reviewViewAvailable()
      ? "넓게 보는 중입니다. 선택과 조회 결과는 그대로 유지됩니다."
      : "넓게 보는 중이며 현재 분석할 결과가 없습니다. 기본 화면으로 돌아갈 수 있습니다.";
  } else if (reviewViewAvailable()) {
    $("review-view-status").textContent = "지도와 분석을 더 넓게 볼 수 있습니다.";
  } else {
    $("review-view-status").textContent = "분석할 수 있는 결과가 있어야 넓게 볼 수 있습니다.";
  }
}

function enterWideView() {
  if (state.view.wide) return true;
  if (!reviewViewAvailable()) {
    syncReviewViewStatus();
    return false;
  }
  state.view.baseScrollX = window.scrollX;
  state.view.baseScrollY = window.scrollY;
  state.view.wide = true;
  syncReviewViewStatus();
  redrawReviewChart();
  return true;
}

function finishBaseView() {
  const x = state.view.baseScrollX;
  const y = state.view.baseScrollY;
  state.view.wide = false;
  state.view.returningToBase = false;
  syncReviewViewStatus();
  requestAnimationFrame(() => {
    window.scrollTo(x, y);
    redrawReviewChart();
    if (modalOwnsFocus()) return;
    const wideToggle = $("review-wide-toggle");
    const target = $("review-view-bar").hidden || wideToggle.disabled ? $("main") : wideToggle;
    target.focus({ preventScroll: true });
  });
}

async function leaveWideView() {
  if (state.mapFullscreen.active) {
    await leaveDedicatedMap();
    return;
  }
  if (state.view.fullscreenPending) return;
  if (!nativeFullscreenActive()) {
    finishBaseView();
    return;
  }
  state.view.returningToBase = true;
  state.view.fullscreenPending = true;
  updateReviewViewControls();
  $("review-view-status").textContent = "전체화면을 종료한 뒤 기본 화면으로 돌아가는 중입니다.";
  try {
    await document.exitFullscreen();
    if (!nativeFullscreenActive() && state.view.returningToBase) finishBaseView();
    else if (nativeFullscreenActive()) $("review-view-status").textContent = "전체화면 종료 상태를 확인하지 못했습니다. 나가기 버튼이나 Esc를 다시 사용해 주세요.";
  } catch (_) {
    if (!nativeFullscreenActive() && state.view.returningToBase) finishBaseView();
    else {
      state.view.returningToBase = false;
      $("review-view-status").textContent = "전체화면을 종료하지 못했습니다. 나가기 버튼이나 Esc를 다시 사용해 주세요.";
    }
  } finally {
    state.view.fullscreenPending = false;
    updateReviewViewControls();
  }
}

async function toggleNativeFullscreen() {
  if (state.view.fullscreenPending || state.mapFullscreen.active) return;
  if (nativeFullscreenActive()) {
    state.view.fullscreenPending = true;
    updateReviewViewControls();
    $("review-view-status").textContent = "전체화면을 종료하는 중입니다.";
    try {
      await document.exitFullscreen();
      if (!nativeFullscreenActive()) {
        updateReviewViewControls();
        $("review-view-status").textContent = "전체화면을 종료했습니다. 넓게 보기는 유지됩니다.";
      }
    } catch (_) {
      $("review-view-status").textContent = nativeFullscreenActive()
        ? "전체화면을 종료하지 못했습니다. 나가기 버튼이나 Esc를 다시 사용해 주세요."
        : "전체화면을 종료했습니다. 넓게 보기는 유지됩니다.";
    } finally {
      state.view.fullscreenPending = false;
      updateReviewViewControls();
    }
    return;
  }
  if (!enterWideView()) return;
  if (typeof document.documentElement.requestFullscreen !== "function") {
    $("review-view-status").textContent = "이 브라우저는 전체화면을 지원하지 않습니다. 넓게 보기는 계속 사용할 수 있습니다.";
    return;
  }
  state.view.fullscreenPending = true;
  updateReviewViewControls();
  $("review-view-status").textContent = "전체화면으로 전환하는 중입니다.";
  try {
    await document.documentElement.requestFullscreen();
    if (nativeFullscreenActive()) syncReviewViewStatus();
    else $("review-view-status").textContent = "전체화면 상태를 확인할 수 없습니다. 넓게 보기는 계속 사용할 수 있습니다.";
  } catch (_) {
    if (nativeFullscreenActive()) syncReviewViewStatus();
    else $("review-view-status").textContent = "전체화면을 시작하지 못했습니다. 넓게 보기는 계속 사용할 수 있습니다.";
  } finally {
    state.view.fullscreenPending = false;
    updateReviewViewControls();
  }
}

function handleFullscreenChange() {
  const mapState = state.mapFullscreen;
  if (mapState.cancelledNativeEntry) {
    if (nativeFullscreenActive()) exitLateMapNativeEntry();
    else {
      mapState.cancelledNativeEntry = false;
      state.view.fullscreenPending = false;
      syncReviewViewStatus();
      syncMapFullscreenStatus();
    }
    redrawReviewChart();
    return;
  }
  if (mapState.active) {
    if (nativeFullscreenActive()) {
      if (mapState.nativeRequested) mapState.acquiredNative = true;
      syncMapFullscreenStatus();
    } else {
      restoreDedicatedMap({ focus: mapState.focusAfterExit });
    }
    redrawReviewChart();
    return;
  }
  if (nativeFullscreenActive()) {
    state.view.wide = true;
    syncReviewViewStatus();
  } else if (state.view.returningToBase) {
    finishBaseView();
    return;
  } else if (state.view.wide) {
    updateReviewViewControls();
    $("review-view-status").textContent = "전체화면을 종료했습니다. 넓게 보기는 유지됩니다.";
    const suppressFocus = Date.now() < state.view.suppressFullscreenFocusUntil;
    if (!suppressFocus && !modalOwnsFocus()) {
      const fullscreenToggle = $("review-fullscreen-toggle");
      const target = fullscreenToggle.disabled ? $("review-wide-toggle") : fullscreenToggle;
      target.focus({ preventScroll: true });
    }
  } else {
    syncReviewViewStatus();
  }
  redrawReviewChart();
}

function handleFullscreenError() {
  const mapState = state.mapFullscreen;
  if (mapState.cancelledNativeEntry) {
    $("review-view-status").textContent = mapState.lateExitPending
      ? "지도 전환 뒤 시작된 전체화면을 종료하지 못했습니다. 전체화면 나가기나 Esc를 다시 사용해 주세요."
      : "지도 전환 중 전체화면 오류가 발생했습니다. 현재 화면 상태를 확인하는 중입니다.";
    return;
  }
  if (mapState.active) {
    syncMapFullscreenStatus(mapState.nativeExitPending
      ? "전체화면을 종료하지 못했습니다. 지도 보기 나가기나 Esc를 다시 사용해 주세요."
      : nativeFullscreenActive() ? undefined : "브라우저 전체화면을 시작하지 못해 화면 안에서 지도를 크게 표시합니다.");
    return;
  }
  if (nativeFullscreenActive()) syncReviewViewStatus();
  else {
    updateReviewViewControls();
    $("review-view-status").textContent = "전체화면 전환을 완료하지 못했습니다. 넓게 보기는 계속 사용할 수 있습니다.";
  }
}

function selectedEquipmentSeries() {
  const dataset = currentDataset();
  const equipment = $("equipment-filter").value;
  return dataset?.current?.series.filter((item) => item.equipment === equipment) || [];
}

function renderTagSearch(unavailableMessage) {
  const input = $("tag-search");
  const results = $("tag-search-results");
  const clear = $("tag-search-clear");
  const previous = $("tag-search-prev");
  const next = $("tag-search-next");
  const pagination = previous.parentElement;
  const available = reviewViewAvailable();
  input.disabled = !available;
  clear.disabled = !available || input.value.length === 0;
  results.replaceChildren();
  previous.disabled = true;
  next.disabled = true;
  pagination.hidden = true;
  if (!available) {
    $("tag-search-status").textContent = unavailableMessage || "파일 상태를 확인하면 항목 이름을 찾을 수 있습니다.";
    return;
  }
  const series = selectedEquipmentSeries();
  const term = input.value.trim();
  if (!term) {
    state.search.page = 0;
    $("tag-search-status").textContent = `현재 설비의 항목 ${number(series.length)}개 · 이름을 입력하거나 위 전체 목록을 사용하세요.`;
    return;
  }
  const folded = term.toLowerCase();
  const matches = series.filter((item) => String(item.tag).toLowerCase().includes(folded));
  const pageCount = Math.max(1, Math.ceil(matches.length / TAG_SEARCH_PAGE_SIZE));
  state.search.page = Math.min(state.search.page, pageCount - 1);
  const start = state.search.page * TAG_SEARCH_PAGE_SIZE;
  const selectedTag = $("tag-filter").value;
  for (const item of matches.slice(start, start + TAG_SEARCH_PAGE_SIZE)) {
    const button = node("button", undefined, "tag-search-result");
    button.type = "button";
    button.dataset.searchTag = item.tag;
    button.disabled = state.busy;
    button.setAttribute("aria-pressed", String(item.tag === selectedTag));
    const detail = `${item.unit || "단위 없음"}${item.tag === selectedTag ? " · 현재 선택" : ""}`;
    button.append(node("strong", item.tag), node("span", detail));
    button.addEventListener("click", () => selectMapTag(item.tag));
    results.append(button);
  }
  const selectionOutside = selectedTag && !matches.some((item) => item.tag === selectedTag);
  $("tag-search-status").textContent = matches.length
    ? `검색 ${number(matches.length)}개 / 전체 ${number(series.length)}개 · ${number(state.search.page + 1)} / ${number(pageCount)}쪽${selectionOutside ? " · 현재 선택 항목은 그대로 유지됩니다." : ""}`
    : `검색 0개 / 전체 ${number(series.length)}개 · 결과 없음${selectionOutside ? " · 현재 선택 항목은 그대로 유지됩니다." : ""}`;
  pagination.hidden = matches.length <= TAG_SEARCH_PAGE_SIZE;
  previous.disabled = state.search.page === 0;
  next.disabled = state.search.page >= pageCount - 1;
}

function resetTagSearch(message) {
  $("tag-search").value = "";
  state.search.page = 0;
  renderTagSearch(message);
}

function updateQueryControls() {
  $("export-button").disabled = state.busy || !state.query;
}

function setQueryPlaceholder(message, hidden = false) {
  $("query-placeholder").textContent = message;
  $("query-placeholder").hidden = hidden;
}

function queryMatchesDraft() {
  const selected = state.query;
  const dataset = currentDataset();
  return !!selected && !!dataset?.current && selected.datasetId === dataset.id &&
    selected.result.version === dataset.current.version && selected.result.latest_attempt_id === dataset.latest?.id &&
    selected.result.equipment === $("equipment-filter").value && selected.result.tag === $("tag-filter").value;
}

function updateMapSelectionStatus(message) {
  const dataset = currentDataset();
  const item = dataset?.current?.series.find((series) => series.equipment === $("equipment-filter").value && series.tag === $("tag-filter").value);
  if (!item) {
    $("map-selection-status").textContent = message || "선택할 수 있는 측정 항목이 없습니다.";
    return;
  }
  if (message) {
    $("map-selection-status").textContent = message;
  } else if (queryMatchesDraft()) {
    $("map-selection-status").textContent = `조회 완료 · 선택 구간 ${number(state.query.result.summary.count)}개 · 파일 전체 ${number(item.count)}개`;
  } else {
    $("map-selection-status").textContent = `선택한 항목을 조회해 주세요 · 파일 전체 ${number(item.count)}개`;
  }
}

function applyMapVisibility() {
  const narrow = explanationNarrow.matches;
  const toggle = $("map-view-toggle");
  const dedicated = state.mapFullscreen.active;
  toggle.hidden = !narrow || dedicated;
  $("equipment-map-body").hidden = !dedicated && narrow && !state.map.expanded;
  toggle.setAttribute("aria-expanded", String(dedicated || !narrow || state.map.expanded));
  toggle.textContent = state.map.expanded ? "지도 접기" : "지도 펼치기";
  requestAnimationFrame(() => mapCanvas?.resize());
}

function renderMapUnavailable(message) {
  abandonDedicatedMapForContextChange();
  mapCanvas?.clear(message);
  $("map-overflow").textContent = "오래된 항목 관계나 통계를 표시하지 않습니다.";
  $("map-selected-item").textContent = "—";
  $("map-selection-status").textContent = "파일 상태를 새로고침해 주세요.";
  $("map-context").replaceChildren();
  $("map-source-link").disabled = true;
  resetTagSearch("파일 상태를 새로고침하면 항목 이름을 다시 찾을 수 있습니다.");
  syncReviewViewStatus();
  syncMapFullscreenStatus();
  applyMapVisibility();
}

function mapContextKey(dataset) {
  return JSON.stringify([dataset.id, dataset.current?.version, dataset.latest?.id]);
}

function mapGroups(current) {
  const groups = new Map();
  for (const item of current.series || []) {
    if (!groups.has(item.equipment)) groups.set(item.equipment, []);
    groups.get(item.equipment).push(item);
  }
  return [...groups].map(([equipment, items]) => ({ equipment, items }));
}

function renderEquipmentMap({ resetContext = false, revealSelection = false, focusSelection = false } = {}) {
  const dataset = currentDataset();
  const current = dataset?.current;
  if (!dataset || !current) return;
  $("equipment-map-section").hidden = false;
  if (state.map.unavailable) {
    renderMapUnavailable(state.map.unavailable);
    return;
  }
  const equipment = $("equipment-filter").value;
  let tag = $("tag-filter").value;
  const series = (current.series || []).filter((item) => item.equipment === equipment);
  const selected = series.find((item) => item.tag === tag) || series[0];
  if (selected && selected.tag !== tag) {
    tag = selected.tag;
    $("tag-filter").value = tag;
  }
  mapCanvas?.setContext({
    key: mapContextKey(dataset),
    groups: mapGroups(current),
    selected: selected ? { equipment, tag: selected.tag } : null,
    busy: state.busy
  }, { forceReset: resetContext, revealSelection, focusSelection });
  $("map-selected-item").textContent = selected ? `${selected.tag} · ${selected.unit || "단위 없음"}` : "—";
  updateMapSelectionStatus();
  const context = $("map-context");
  context.replaceChildren();
  const retained = dataset.latest?.status !== "ready";
  const resultState = node("article");
  resultState.append(node("strong", "현재 보관 결과"), node("p", retained ? "이전 정상 결과 유지" : "분석 가능"));
  const attemptState = node("article");
  attemptState.append(node("strong", "최신 시도 · 서버 시각"), node("p", `${statusNames[dataset.latest?.status] || dataset.latest?.status || "확인 불가"} · ${attemptDate(dataset.latest?.at) || "—"}`));
  const physicalState = node("article");
  physicalState.append(node("strong", "설비 상태"), node("p", "판단 근거 없음"));
  const sourceTime = node("article");
  sourceTime.append(node("strong", "원본 관측 범위"), node("p", `${dateLabel(current.range?.start)} – ${dateLabel(current.range?.end)} · ${current.time_basis === "unspecified" ? "시간대 미제공" : "UTC"}`));
  context.append(resultState, attemptState, physicalState, sourceTime);
  if (dataset.source_kind === "sample") context.append(node("p", "공개 샘플 · 과거 열차 공기압축기 기록 · 설비명은 검증된 자산 ID나 실시간 상태가 아닙니다.", "map-sample-note"));
  $("map-source-link").disabled = state.busy;
  syncMapFullscreenStatus();
  applyMapVisibility();
}

function clearQueryForDraft(message = "선택한 항목을 조회해 주세요.", { closeExplanationPanel = true } = {}) {
  state.queryGeneration += 1;
  state.query = null;
  if (closeExplanationPanel) resetExplanation();
  $("query-results").hidden = true;
  showError("", "query-error");
  setQueryPlaceholder(message);
  updateQueryControls();
  updateMapSelectionStatus(message);
}

function invalidateMapAndQuery(message, { preserveExplanationPanel = false } = {}) {
  state.map.unavailable = message || "파일 상태가 바뀌었습니다.";
  clearQueryForDraft("파일 상태를 새로고침한 뒤 다시 조회해 주세요.", { closeExplanationPanel: !preserveExplanationPanel });
  renderEquipmentMap();
  showError(state.map.unavailable, "query-error");
}

function suspendMapAndQuery(message) {
  abandonDedicatedMapForContextChange();
  clearQueryForDraft(message);
  if (currentDataset()?.current) {
    state.map.unavailable = message;
    renderEquipmentMap();
  }
}

function focusSelectedTag(equipment, tag) {
  const mapButton = [...document.querySelectorAll("[data-map-tag]")].find((button) => button.dataset.mapEquipment === equipment && button.dataset.mapTag === tag);
  const mapVisible = mapButton && !$("equipment-map-body").hidden && mapButton.offsetParent !== null;
  const target = mapVisible ? mapButton : $("tag-filter");
  target.focus({ preventScroll: true });
  target.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function selectMapItem(equipment, tag) {
  const dataset = currentDataset();
  const item = dataset?.current?.series.find((series) => series.equipment === equipment && series.tag === tag);
  if (!item) return;
  const same = $("equipment-filter").value === equipment && $("tag-filter").value === tag;
  if (same) {
    renderEquipmentMap({ revealSelection: true });
    renderTagSearch();
    focusSelectedTag(equipment, tag);
    return;
  }
  const equipmentChanged = $("equipment-filter").value !== equipment;
  if (equipmentChanged) {
    $("equipment-filter").value = equipment;
    populateTags(dataset, tag);
  } else {
    $("tag-filter").value = tag;
  }
  clearQueryForDraft();
  if (equipmentChanged) resetTagSearch();
  renderEquipmentMap({ revealSelection: true });
  renderTagSearch();
  focusSelectedTag(equipment, tag);
}

function selectMapTag(tag) {
  selectMapItem($("equipment-filter").value, tag);
}

function explanationKey(selected = state.query) {
  if (!selected) return null;
  const params = new URLSearchParams(selected.params);
  params.sort();
  return JSON.stringify([selected.datasetId, selected.result.version, selected.result.latest_attempt_id, params.toString()]);
}

function stopExplanationRequest(invalidate = true) {
  const current = state.explanation;
  if (invalidate) current.generation += 1;
  if (current.timeout !== null) clearTimeout(current.timeout);
  current.timeout = null;
  if (current.controller) current.controller.abort();
  current.controller = null;
  current.loading = false;
}

function clearExplanationContent() {
  state.explanation.question = null;
  state.explanation.requestKey = null;
  state.explanation.answerKey = null;
  state.explanation.retryVisible = false;
  $("explanation-answer").replaceChildren();
  $("explanation-context").replaceChildren();
  $("explanation-status").textContent = "";
  $("explanation-panel").querySelector(".explanation-evidence").hidden = true;
  for (const button of document.querySelectorAll("[data-explanation-evidence]")) button.hidden = false;
  for (const button of document.querySelectorAll("[data-explanation-question]")) {
    button.classList.remove("selected");
    button.removeAttribute("aria-pressed");
  }
}

function updateExplanationControls() {
  const focused = document.activeElement;
  const available = !!state.query && !state.busy && !state.explanation.loading;
  for (const button of document.querySelectorAll("[data-explanation-question]")) button.disabled = !available;
  $("explanation-cancel").hidden = !state.explanation.loading;
  $("explanation-retry").hidden = state.explanation.loading || !state.explanation.retryVisible;
  const panel = $("explanation-panel");
  if (!panel.hidden && ((focused?.matches?.("[data-explanation-question]") && focused.disabled) ||
      (explanationNarrow.matches && !panel.contains(document.activeElement)))) {
    $("explanation-title").focus({ preventScroll: true });
  }
}

function contextLine(list, label, value, mono = false) {
  list.append(node("dt", label), node("dd", value ?? "—", mono ? "mono" : undefined));
}

function renderExplanationContext(context, summary) {
  const root = $("explanation-context");
  root.replaceChildren();
  if (!context) return;
  const current = currentDataset()?.current;
  root.append(node("strong", "마지막 조회 결과 기준"));
  const list = node("dl");
  contextLine(list, "출처", context.source_name || current?.source_name || "현재 검증 파일");
  contextLine(list, "결과 버전", context.version, true);
  const sourceHash = context.source_sha256 || (context.version === current?.version ? current.source_sha256 : null);
  if (sourceHash) contextLine(list, "원본 SHA", sourceHash, true);
  contextLine(list, "설비 · 항목", `${context.equipment} · ${context.tag}`);
  const start = context.filter?.start ? `${dateLabel(context.filter.start)}부터` : "첫 관측부터";
  const end = context.filter?.end ? `${dateLabel(context.filter.end)} 전까지` : "마지막 관측까지";
  contextLine(list, "조회 범위", `${start} ${end}`);
  contextLine(list, "시각 기준", context.time_basis === "unspecified" ? "시간대 미제공" : "UTC");
  if (context.latest_attempt_id) contextLine(list, "최근 검사", `#${context.latest_attempt_id} · ${statusNames[context.latest_status] || context.latest_status}`);
  if (summary) contextLine(list, "선택 결과", `${number(summary.count)}개 · 평균 ${number(summary.mean)} ${context.unit || ""}`.trim());
  root.append(list);
}

function applyExplanationMode() {
  const panel = $("explanation-panel");
  // A native confirmation owns focus even if a resize makes the explanation narrow.
  const modal = !panel.hidden && explanationNarrow.matches && !document.querySelector("dialog:modal");
  panel.setAttribute("role", modal ? "dialog" : "complementary");
  if (modal) panel.setAttribute("aria-modal", "true"); else panel.removeAttribute("aria-modal");
  $("application-shell").inert = modal;
  for (const element of document.querySelectorAll(".skip-link,#toast,#delete-dialog")) element.inert = modal;
  document.body.classList.toggle("explanation-modal-open", modal);
  $("explanation-backdrop").hidden = !modal;
  if (modal && !panel.contains(document.activeElement)) $("explanation-title").focus();
}

function openExplanation() {
  const panel = $("explanation-panel");
  state.explanation.returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : $("explanation-launcher");
  panel.hidden = false;
  $("explanation-launcher").setAttribute("aria-expanded", "true");
  applyExplanationMode();
  if (state.query) {
    renderExplanationContext(state.query.result, state.query.result.summary);
    $("explanation-status").textContent = "마지막으로 성공한 조회 결과에서 설명할 질문을 선택하세요.";
  } else {
    $("explanation-status").textContent = "먼저 파일의 분석 가능한 결과를 조회해 주세요. 조회에 성공하면 이곳에서 설명을 요청할 수 있습니다.";
  }
  updateExplanationControls();
  $("explanation-title").focus();
}

function closeExplanation({ returnFocus = true, discard = true } = {}) {
  const target = state.explanation.returnFocus;
  stopExplanationRequest(true);
  if (discard) clearExplanationContent();
  $("explanation-panel").hidden = true;
  $("explanation-backdrop").hidden = true;
  $("application-shell").inert = false;
  for (const element of document.querySelectorAll(".skip-link,#toast,#delete-dialog")) element.inert = false;
  document.body.classList.remove("explanation-modal-open");
  $("explanation-launcher").setAttribute("aria-expanded", "false");
  if (returnFocus) (target?.isConnected ? target : $("explanation-launcher")).focus();
  state.explanation.returnFocus = null;
}

function resetExplanation() {
  closeExplanation({ returnFocus: false, discard: true });
}

function renderExplanationAnswer(payload, key) {
  const root = $("explanation-answer");
  root.replaceChildren(node("h3", payload.title));
  for (const paragraph of payload.paragraphs) root.append(node("p", paragraph));
  renderExplanationContext(payload.context, payload.summary);
  const evidence = $("explanation-panel").querySelector(".explanation-evidence");
  const allowed = new Set(payload.evidence.filter((kind) => ["query", "source", "history"].includes(kind)));
  for (const button of document.querySelectorAll("[data-explanation-evidence]")) button.hidden = !allowed.has(button.dataset.explanationEvidence);
  evidence.hidden = allowed.size === 0;
  state.explanation.answerKey = key;
  state.explanation.retryVisible = false;
  $("explanation-status").textContent = "고정한 조회 결과에서 규칙 기반 설명을 만들었습니다.";
}

function invalidateQueryForExplanation(message) {
  invalidateMapAndQuery(message, { preserveExplanationPanel: true });
  $("explanation-answer").replaceChildren();
  $("explanation-context").replaceChildren();
  $("explanation-panel").querySelector(".explanation-evidence").hidden = true;
  state.explanation.question = null;
  state.explanation.requestKey = null;
  state.explanation.answerKey = null;
  state.explanation.retryVisible = false;
  $("explanation-status").textContent = "파일 상태가 바뀌었거나 이 결과를 더 이상 확인할 수 없습니다. 파일 상태를 새로고침해 주세요.";
}

async function requestExplanation(question) {
  if (state.busy || state.explanation.loading) return;
  const selected = state.query;
  const key = explanationKey(selected);
  if (!selected || !key) {
    $("explanation-status").textContent = "먼저 파일의 분석 가능한 결과를 조회해 주세요.";
    updateExplanationControls();
    return;
  }
  stopExplanationRequest(true);
  const generation = state.explanation.generation;
  const controller = new AbortController();
  state.explanation.controller = controller;
  state.explanation.loading = true;
  state.explanation.question = question;
  state.explanation.requestKey = key;
  state.explanation.answerKey = null;
  state.explanation.retryVisible = false;
  $("explanation-answer").replaceChildren();
  $("explanation-panel").querySelector(".explanation-evidence").hidden = true;
  for (const button of document.querySelectorAll("[data-explanation-question]")) {
    const selectedQuestion = button.dataset.explanationQuestion === question;
    button.classList.toggle("selected", selectedQuestion);
    button.setAttribute("aria-pressed", String(selectedQuestion));
  }
  renderExplanationContext(selected.result, selected.result.summary);
  $("explanation-status").textContent = "마지막 조회 결과의 근거를 확인하는 중…";
  updateExplanationControls();

  const params = new URLSearchParams(selected.params);
  params.set("question", question);
  params.set("latest_attempt_id", String(selected.result.latest_attempt_id));
  state.explanation.timeout = setTimeout(() => {
    if (generation !== state.explanation.generation || explanationKey() !== key) return;
    // A timeout must terminate UI eligibility even when transport abort is ineffective.
    stopExplanationRequest(true);
    state.explanation.retryVisible = true;
    $("explanation-status").textContent = "10초 동안 응답을 받지 못해 요청을 중단했습니다. 다시 시도할 수 있습니다.";
    updateExplanationControls();
  }, EXPLANATION_TIMEOUT_MS);
  try {
    const payload = await request(`/api/datasets/${encodeURIComponent(selected.datasetId)}/explanation?${params}`, { signal: controller.signal });
    if (generation !== state.explanation.generation || explanationKey() !== key) return;
    if (payload.mode !== "guided" || payload.question !== question || payload.context?.dataset_id !== selected.datasetId ||
        payload.context?.version !== selected.result.version || payload.context?.latest_attempt_id !== selected.result.latest_attempt_id ||
        payload.context?.equipment !== selected.result.equipment || payload.context?.tag !== selected.result.tag ||
        JSON.stringify(payload.context?.filter) !== JSON.stringify(selected.result.filter) ||
        typeof payload.title !== "string" || !Array.isArray(payload.paragraphs) ||
        !payload.paragraphs.every((paragraph) => typeof paragraph === "string") || !Array.isArray(payload.evidence) ||
        !payload.evidence.every((kind) => ["query", "source", "history"].includes(kind))) {
      const mismatch = new Error("설명 응답이 마지막 조회 결과와 일치하지 않습니다. 결과를 다시 조회해 주세요.");
      mismatch.code = "CONTEXT_CHANGED";
      throw mismatch;
    }
    renderExplanationAnswer(payload, key);
  } catch (error) {
    if (generation !== state.explanation.generation || explanationKey() !== key) return;
    if ([401, 403, 404].includes(error.status) || ["INTEGRITY", "CONTEXT_CHANGED"].includes(error.code)) {
      invalidateQueryForExplanation(error.message);
    } else if (error.name !== "AbortError") {
      state.explanation.retryVisible = true;
      $("explanation-status").textContent = `${error.message || "설명을 만들지 못했습니다."} 자동으로 다시 요청하지 않았습니다.`;
    }
  } finally {
    if (generation === state.explanation.generation) {
      if (state.explanation.timeout !== null) clearTimeout(state.explanation.timeout);
      state.explanation.timeout = null;
      state.explanation.controller = null;
      state.explanation.loading = false;
      updateExplanationControls();
    }
  }
}

function cancelExplanation() {
  if (!state.explanation.loading) return;
  stopExplanationRequest(true);
  state.explanation.retryVisible = !!state.explanation.question && state.explanation.requestKey === explanationKey();
  $("explanation-status").textContent = "설명 요청을 취소했습니다. 필요하면 같은 조회 결과로 다시 시도하세요.";
  updateExplanationControls();
}

function retryExplanation() {
  if (!state.explanation.question || state.explanation.requestKey !== explanationKey()) {
    clearExplanationContent();
    $("explanation-status").textContent = "조회 결과가 바뀌었습니다. 현재 결과에서 질문을 다시 선택해 주세요.";
    updateExplanationControls();
    return;
  }
  requestExplanation(state.explanation.question);
}

async function focusExplanationEvidence(kind) {
  if (state.explanation.answerKey !== explanationKey()) return;
  const target = { query: $("query-results"), source: $("source-details"), history: $("history-details") }[kind];
  if (!target) return;
  closeExplanation({ returnFocus: false, discard: true });
  await focusReviewTarget(target, { openDetails: target instanceof HTMLDetailsElement });
}

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
      resetExplanation();
      try {
        const payload = await request(`/api/datasets/${encodeURIComponent(dataset.id)}`);
        upsert(payload.dataset);
        await selectDataset(payload.dataset.id, true);
      } catch (error) {
        if (dataset.id === state.active && isReviewContextError(error)) invalidateMapAndQuery(error.message);
        throw error;
      }
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
  state.map.unavailable = null;
  if (resetFilters) state.map.expanded = false;
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
  setQueryPlaceholder("선택한 항목을 조회해 주세요.");
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
    resetTagSearch();
    renderEquipmentMap({ resetContext: true });
  } else {
    abandonDedicatedMapForContextChange();
    $("equipment-map-section").hidden = true;
    mapCanvas?.clear();
    $("map-overflow").textContent = "";
    $("map-selected-item").textContent = "";
    $("map-selection-status").textContent = "";
    $("map-context").replaceChildren();
    $("map-source-link").disabled = true;
    resetTagSearch("분석할 수 있는 결과가 있어야 항목 이름을 찾을 수 있습니다.");
  }
  $("sample-attribution").hidden = dataset.source_kind !== "sample";
  $("sample-exercise").hidden = dataset.source_kind !== "sample";
  renderHistory(dataset);
  updateQueryControls();
  syncReviewViewStatus();
  syncMapFullscreenStatus();
}

async function selectDataset(id, resetFilters = false, loadResult = true) {
  if (state.mapFullscreen.active && state.active !== id) abandonDedicatedMapForContextChange();
  resetExplanation();
  const changed = state.active !== id;
  state.active = id;
  const dataset = currentDataset();
  state.queryGeneration += 1;
  renderList();
  if (!dataset) {
    state.query = null;
    state.map.unavailable = null;
    $("equipment-map-section").hidden = true;
    mapCanvas?.clear();
    $("workspace").hidden = true;
    $("welcome").hidden = false;
    document.title = "Telemetry Review · 설비 데이터 검토";
    resetTagSearch("분석할 수 있는 결과가 있어야 항목 이름을 찾을 수 있습니다.");
    syncReviewViewStatus();
    syncMapFullscreenStatus();
    return;
  }
  renderDataset(dataset, resetFilters || changed);
  if (dataset.current && loadResult) await loadQuery();
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
  resetExplanation();
  const dataset = currentDataset();
  if (!dataset?.current) return;
  if (state.map.unavailable) {
    showError("파일 상태를 새로고침한 뒤 조회해 주세요.", "query-error");
    return;
  }
  const generation = ++state.queryGeneration;
  const params = selectedParameters(dataset);
  const captured = {
    datasetId: dataset.id,
    version: dataset.current.version,
    latestAttemptId: dataset.latest?.id,
    equipment: params.get("equipment"),
    tag: params.get("tag")
  };
  state.query = null;
  $("query-results").hidden = true;
  setQueryPlaceholder("선택한 항목을 조회하는 중…");
  updateMapSelectionStatus("선택한 항목을 조회하는 중…");
  updateQueryControls();
  showError("", "query-error");
  try {
    const result = await request(`/api/datasets/${encodeURIComponent(dataset.id)}/query?${params}`);
    if (generation !== state.queryGeneration || captured.datasetId !== state.active) return;
    const described = currentDataset();
    if (!described?.current || described.current.version !== captured.version || described.latest?.id !== captured.latestAttemptId ||
        result.version !== captured.version || result.latest_attempt_id !== captured.latestAttemptId ||
        result.equipment !== captured.equipment || result.tag !== captured.tag) {
      invalidateMapAndQuery("파일 버전 또는 최근 검사 상태가 바뀌었습니다. 파일 상태를 명시적으로 새로고침해 주세요.");
      return;
    }
    state.query = { result, datasetId: dataset.id, params: new URLSearchParams(params) };
    state.query.params.set("version", result.version);
    renderQuery(result);
  } catch (error) {
    if (generation !== state.queryGeneration) return;
    if (isReviewContextError(error)) invalidateMapAndQuery(error.message);
    else {
      showError(error.message, "query-error");
      setQueryPlaceholder("조회를 완료하지 못했습니다. 조건을 확인하고 다시 조회해 주세요.");
      updateMapSelectionStatus("조회하지 못했습니다. 선택한 항목을 다시 조회해 주세요.");
      updateQueryControls();
    }
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
  setQueryPlaceholder("", true);
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
  updateMapSelectionStatus();
  updateQueryControls();
}

async function upload(file, replace) {
  if (!file || state.busy) return;
  if (file.size > state.limits.upload_bytes) { showError(`파일이 업로드 한도 ${number(state.limits.upload_bytes / 1024 / 1024)} MiB를 초과합니다. 필요한 구간만 나누어 업로드해 주세요.`); return; }
  if (!file.size) { showError("빈 파일입니다. CSV 내용이 있는 파일을 선택해 주세요."); return; }
  const dataset = currentDataset();
  if (replace && !dataset) return;
  suspendMapAndQuery(replace ? "수정 파일 검사가 끝나면 지도를 다시 표시합니다." : "새 파일 검사가 끝나면 지도를 다시 표시합니다.");
  await action(replace ? "수정 파일을 검사하는 중…" : "파일을 업로드하고 검사하는 중…", async () => {
    const path = replace ? `/api/datasets/${encodeURIComponent(dataset.id)}/replace` : "/api/datasets";
    const payload = await request(`${path}?${new URLSearchParams({ name: file.name })}`, { method: "POST", body: file, headers: { "Content-Type": "text/csv; charset=utf-8" } });
    upsert(payload.dataset);
    await selectDataset(payload.dataset.id, !replace || payload.dataset.latest?.status === "ready");
    showToast(payload.dataset.latest?.status === "ready" ? "파일 검증을 완료했습니다." : "검사 결과를 확인하고 파일을 수정해 주세요.");
  });
}

async function openSample() {
  suspendMapAndQuery("공개 샘플 검사가 끝나면 지도를 다시 표시합니다.");
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
  suspendMapAndQuery("검사가 끝나면 파일 버전과 지도를 다시 표시합니다.");
  await action(message, async () => {
    const payload = await request(`/api/datasets/${encodeURIComponent(dataset.id)}/${route}`, { method: "POST" });
    upsert(payload.dataset);
    await selectDataset(payload.dataset.id);
    showToast(resultMessage);
  });
}

async function refreshMapDataset() {
  const dataset = currentDataset();
  if (!dataset || state.busy) return;
  const datasetId = dataset.id;
  suspendMapAndQuery("파일 상태를 다시 확인하는 중입니다.");
  showError("", "query-error");
  await action("파일 상태를 새로고침하는 중…", async () => {
    try {
      const payload = await request(`/api/datasets/${encodeURIComponent(datasetId)}`);
      if (datasetId !== state.active) return;
      upsert(payload.dataset);
      state.map.unavailable = null;
      await selectDataset(datasetId, false, false);
      showToast("현재 파일 버전과 최근 검사 상태를 다시 확인했습니다. 선택한 항목을 조회해 주세요.");
    } catch (error) {
      if (datasetId === state.active) {
        state.map.unavailable = error.message || "파일 상태를 새로고침하지 못했습니다.";
        renderEquipmentMap();
        setQueryPlaceholder("파일 상태를 새로고침한 뒤 다시 조회해 주세요.");
        showError(state.map.unavailable, "query-error");
      }
      throw error;
    }
  });
}

async function downloadResult() {
  const selected = state.query;
  if (!selected) return;
  await action("선택한 버전의 결과를 준비하는 중…", async () => {
    let response;
    try {
      response = await request(`/api/datasets/${encodeURIComponent(selected.datasetId)}/export?${selected.params}`, { binary: true });
    } catch (error) {
      if (isReviewContextError(error)) invalidateMapAndQuery(error.message);
      throw error;
    }
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
  explanationNarrow.addEventListener("change", () => {
    if (!$("explanation-panel").hidden) {
      applyExplanationMode();
      updateExplanationControls();
    }
    applyMapVisibility();
  });
  $("review-wide-toggle").addEventListener("click", () => { if (state.view.wide) leaveWideView(); else enterWideView(); });
  $("review-fullscreen-toggle").addEventListener("click", toggleNativeFullscreen);
  document.addEventListener("fullscreenchange", handleFullscreenChange);
  document.addEventListener("fullscreenerror", handleFullscreenError);
  $("tag-search").addEventListener("input", () => { state.search.page = 0; renderTagSearch(); });
  $("tag-search-clear").addEventListener("click", () => { resetTagSearch(); $("tag-search").focus(); });
  $("tag-search-prev").addEventListener("click", () => {
    state.search.page = Math.max(0, state.search.page - 1);
    renderTagSearch();
    const target = $("tag-search-prev").disabled ? $("tag-search-next") : $("tag-search-prev");
    target.focus();
  });
  $("tag-search-next").addEventListener("click", () => {
    state.search.page += 1;
    renderTagSearch();
    const target = $("tag-search-next").disabled ? $("tag-search-prev") : $("tag-search-next");
    target.focus();
  });
  $("map-view-toggle").addEventListener("click", () => { state.map.expanded = !state.map.expanded; applyMapVisibility(); });
  $("map-refresh").addEventListener("click", refreshMapDataset);
  $("map-fullscreen-toggle").addEventListener("click", () => { if (state.mapFullscreen.active) leaveDedicatedMap(); else enterDedicatedMap(); });
  $("map-source-link").addEventListener("click", () => focusReviewTarget($("source-details"), { openDetails: true }));
  $("map-review-link").addEventListener("click", returnToReviewFromMap);
  $("explanation-launcher").addEventListener("click", openExplanation);
  $("explanation-close").addEventListener("click", () => closeExplanation());
  $("explanation-backdrop").addEventListener("click", () => closeExplanation());
  $("explanation-cancel").addEventListener("click", cancelExplanation);
  $("explanation-retry").addEventListener("click", retryExplanation);
  for (const button of document.querySelectorAll("[data-explanation-question]")) {
    button.addEventListener("click", () => requestExplanation(button.dataset.explanationQuestion));
  }
  for (const button of document.querySelectorAll("[data-explanation-evidence]")) {
    button.addEventListener("click", () => focusExplanationEvidence(button.dataset.explanationEvidence));
  }
  document.addEventListener("keydown", (event) => {
    const panel = $("explanation-panel");
    const openDialog = document.querySelector("dialog:modal");
    if (event.key === "Escape" && nativeFullscreenActive() && (openDialog || (!panel.hidden && explanationNarrow.matches))) {
      state.view.suppressFullscreenFocusUntil = Date.now() + 1000;
    }
    if (!panel.hidden) {
      if (openDialog) return;
      if (event.key === "Escape") {
        event.preventDefault();
        closeExplanation();
        return;
      }
      if (event.key !== "Tab" || !explanationNarrow.matches) return;
      const focusable = [...panel.querySelectorAll("button:not(:disabled)")].filter((item) => !item.hidden && item.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !focusable.includes(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !focusable.includes(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
      return;
    }
    if (event.key === "Escape" && state.mapFullscreen.active && !openDialog) {
      event.preventDefault();
      if (mapCanvas?.cancelMove()) return;
      leaveDedicatedMap();
    }
  });
  for (const id of ["upload-button", "welcome-upload"]) $(id).addEventListener("click", () => $("upload-input").click());
  $("replace-button").addEventListener("click", () => $("replace-input").click());
  for (const [id, replace] of [["upload-input", false], ["replace-input", true]]) $(id).addEventListener("change", (event) => { const file = event.target.files?.[0]; event.target.value = ""; upload(file, replace); });
  for (const id of ["sample-button", "welcome-sample"]) $(id).addEventListener("click", openSample);
  $("equipment-filter").addEventListener("change", () => {
    const dataset = currentDataset();
    if (!dataset) return;
    populateTags(dataset);
    clearQueryForDraft();
    resetTagSearch();
    renderEquipmentMap({ revealSelection: true });
  });
  $("tag-filter").addEventListener("change", () => {
    clearQueryForDraft();
    renderEquipmentMap({ revealSelection: true });
    renderTagSearch();
  });
  $("query-form").addEventListener("submit", (event) => { event.preventDefault(); action("선택 구간을 분석하는 중…", loadQuery); });
  $("reset-range").addEventListener("click", () => { $("start-filter").value = ""; $("end-filter").value = ""; action("전체 기간을 분석하는 중…", loadQuery); });
  $("export-button").addEventListener("click", downloadResult);
  $("retry-button").addEventListener("click", () => runAttempt("retry", "보관 원본을 다시 검사하는 중…", "보관 원본의 재검사를 마쳤습니다. 최근 검사 결과를 확인해 주세요."));
  $("delivery-button").addEventListener("click", () => runAttempt("delivery-check", "샘플의 일부 행을 제외하고 전달하는 중…", "전달 누락을 기록했습니다. 이전 검증 결과는 유지됩니다."));
  $("recover-button").addEventListener("click", () => runAttempt("retry", "보관된 전체 원본으로 복구하는 중…", "보관 원본을 다시 검사했습니다. 결과 버전과 최근 기록을 확인해 주세요."));
  $("delete-button").addEventListener("click", () => { $("delete-dialog").returnValue = "cancel"; $("delete-dialog").showModal(); });
  $("delete-dialog").addEventListener("close", () => {
    if ($("delete-dialog").returnValue !== "delete") {
      if (!$("explanation-panel").hidden) applyExplanationMode();
      return;
    }
    const dataset = currentDataset();
    if (!dataset) return;
    suspendMapAndQuery("파일을 삭제하는 중입니다.");
    action("파일과 검사 기록을 삭제하는 중…", async () => {
      try {
        await request(`/api/datasets/${encodeURIComponent(dataset.id)}`, { method: "DELETE" });
      } catch (error) {
        if (isReviewContextError(error)) invalidateMapAndQuery(error.message);
        throw error;
      }
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
  mapCanvas = window.createFileReviewMapCanvas({
    formatNumber: number,
    isInteractionBlocked: () => Boolean(document.querySelector("dialog:modal")) || $("application-shell").inert,
    onSelect: ({ key, equipment, tag }) => {
      const dataset = currentDataset();
      if (!dataset?.current || key !== mapContextKey(dataset)) return;
      selectMapItem(equipment, tag);
    }
  });
  installEvents();
  await action("작업 공간을 불러오는 중…", async () => {
    const session = await request("/api/session");
    state.csrf = session.csrf_token;
    state.capabilities = { ...state.capabilities, ...session.capabilities };
    state.limits = { ...state.limits, ...session.limits };
    if (!state.capabilities.uploads) {
      for (const id of ["upload-button", "welcome-upload", "replace-button", "dropzone", "input-guide"]) $(id).hidden = true;
      for (const link of document.querySelectorAll(".template-link")) link.hidden = true;
      $("welcome-description").textContent = "공개 설비 기록으로 데이터 검토와 복구 흐름을 체험하세요. 분석에 사용한 원본과 결과 버전을 함께 확인할 수 있습니다.";
    } else {
      $("format-hint").textContent = `UTF-8 · 최대 ${number(state.limits.upload_bytes / 1024 / 1024)} MiB · ${number(state.limits.rows)}행`;
    }
    const payload = await request("/api/datasets");
    state.datasets = payload.datasets;
    await selectDataset(state.datasets[0]?.id || null, true);
  });
}

initialize();
