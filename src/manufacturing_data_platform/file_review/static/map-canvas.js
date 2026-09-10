(function () {
  "use strict";

  const GROUP_PAGE_SIZE = 20;
  const ITEM_BUDGET = 200;
  const MIN_SCALE = 0.01;
  const MAX_SCALE = 2;
  const READABLE_SCALE = 1;
  const MAP_PADDING = 32;
  const ITEM_WIDTH = 132;
  const ITEM_HEIGHT = 64;
  const ITEM_GAP_X = 16;
  const ITEM_GAP_Y = 16;
  const GROUP_WIDTH = 190;
  const GROUP_LEFT = 24;
  const ITEMS_LEFT = 270;

  function element(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }

  function svgElement(tag, attributes = {}) {
    const item = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [name, value] of Object.entries(attributes)) item.setAttribute(name, value);
    return item;
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function groupIdentity(equipment) {
    return JSON.stringify(["group", equipment]);
  }

  function itemIdentity(equipment, tag) {
    return JSON.stringify(["item", equipment, tag]);
  }

  function fairAllocations(groups) {
    const allocations = new Map();
    let remaining = ITEM_BUDGET;
    let active = groups.map((group) => ({ equipment: group.equipment, need: group.items.length }));
    while (active.length) {
      const share = Math.floor(remaining / active.length);
      const fulfilled = active.filter((item) => item.need <= share);
      if (!fulfilled.length) {
        active.forEach((item, index) => allocations.set(item.equipment, share + (index < remaining % active.length ? 1 : 0)));
        break;
      }
      for (const item of fulfilled) {
        allocations.set(item.equipment, item.need);
        remaining -= item.need;
      }
      const fulfilledNames = new Set(fulfilled.map((item) => item.equipment));
      active = active.filter((item) => !fulfilledNames.has(item.equipment));
    }
    return allocations;
  }

  function createMapCanvas(options) {
    const root = document.getElementById("equipment-map");
    const world = document.getElementById("map-world");
    const minimap = document.getElementById("map-minimap");
    const overflow = document.getElementById("map-overflow");
    const groupStatus = document.getElementById("map-groups-status");
    const groupPrevious = document.getElementById("map-groups-prev");
    const groupNext = document.getElementById("map-groups-next");
    const zoomIn = document.getElementById("map-zoom-in");
    const zoomOut = document.getElementById("map-zoom-out");
    const zoomLevel = document.getElementById("map-zoom-level");
    const fitButton = document.getElementById("map-fit");
    const focusButton = document.getElementById("map-focus-selection");
    const moveToggle = document.getElementById("map-pan-toggle");
    const cameraStatus = document.getElementById("map-camera-status");
    const panButtons = {
      "map-pan-left": [-1, 0], "map-pan-right": [1, 0],
      "map-pan-up": [0, -1], "map-pan-down": [0, 1]
    };
    const formatNumber = options.formatNumber || String;
    const state = {
      key: null, groups: [], selected: null, groupPage: 0, open: new Set(), offsets: new Map(),
      scale: 1, x: 0, y: 0, layout: null, cameraInitialized: false, moveMode: false,
      pointer: null, generation: 0, renderFrame: null, viewWidth: 0, viewHeight: 0, busy: false
    };

    function blocked() {
      return Boolean(options.isInteractionBlocked?.());
    }

    function announce(message) {
      cameraStatus.textContent = message;
    }

    function visibleGroups() {
      const start = state.groupPage * GROUP_PAGE_SIZE;
      return state.groups.slice(start, start + GROUP_PAGE_SIZE);
    }

    function updateGroupControls() {
      const total = state.groups.length;
      const pages = Math.max(1, Math.ceil(total / GROUP_PAGE_SIZE));
      state.groupPage = clamp(state.groupPage, 0, pages - 1);
      const start = total ? state.groupPage * GROUP_PAGE_SIZE + 1 : 0;
      const end = Math.min(total, start + GROUP_PAGE_SIZE - 1);
      groupStatus.textContent = total ? `설비 ${formatNumber(start)}–${formatNumber(end)} / ${formatNumber(total)} · ${formatNumber(state.groupPage + 1)} / ${formatNumber(pages)}쪽` : "표시할 설비가 없습니다.";
      groupPrevious.disabled = state.groupPage === 0;
      groupNext.disabled = !total || state.groupPage >= pages - 1;
    }

    function allocationsForVisibleGroups(groups) {
      return fairAllocations(groups.filter((group) => state.open.has(group.equipment)));
    }

    function normalizeOffset(group, capacity) {
      const requested = state.offsets.get(group.equipment) || 0;
      const last = group.items.length ? Math.floor((group.items.length - 1) / capacity) * capacity : 0;
      const offset = clamp(Math.floor(requested / capacity) * capacity, 0, last);
      state.offsets.set(group.equipment, offset);
      return offset;
    }

    function buildLayout(groups, allocations) {
      const entries = [];
      let y = 24;
      let worldWidth = 560;
      for (const group of groups) {
        const expanded = state.open.has(group.equipment);
        const capacity = expanded ? Math.max(1, allocations.get(group.equipment) || 1) : 0;
        const offset = expanded ? normalizeOffset(group, capacity) : 0;
        const items = expanded ? group.items.slice(offset, offset + capacity) : [];
        const columns = items.length ? (items.length <= 3 ? 1 : Math.min(8, Math.ceil(Math.sqrt(items.length * 1.7)))) : 0;
        const rows = columns ? Math.ceil(items.length / columns) : 0;
        const itemWidth = columns ? columns * ITEM_WIDTH + (columns - 1) * ITEM_GAP_X : 0;
        const height = expanded ? Math.max(218, 48 + rows * ITEM_HEIGHT + Math.max(0, rows - 1) * ITEM_GAP_Y) : 136;
        worldWidth = Math.max(worldWidth, ITEMS_LEFT + itemWidth + 36);
        entries.push({ group, expanded, capacity, offset, items, columns, y, height });
        y += height + 20;
      }
      const width = worldWidth;
      const height = Math.max(260, y + 4);
      const boxes = new Map();
      for (const entry of entries) {
        entry.frame = { x: GROUP_LEFT, y: entry.y, width: width - GROUP_LEFT * 2, height: entry.height };
        entry.groupBox = { x: GROUP_LEFT + 22, y: entry.y + 28, width: GROUP_WIDTH, height: 80 };
        entry.itemBoxes = entry.items.map((item, index) => ({
          item,
          x: ITEMS_LEFT + (index % entry.columns) * (ITEM_WIDTH + ITEM_GAP_X),
          y: entry.y + 28 + Math.floor(index / entry.columns) * (ITEM_HEIGHT + ITEM_GAP_Y),
          width: ITEM_WIDTH,
          height: ITEM_HEIGHT
        }));
        boxes.set(groupIdentity(entry.group.equipment), entry.groupBox);
        for (const box of entry.itemBoxes) boxes.set(itemIdentity(entry.group.equipment, box.item.tag), box);
      }
      return { width, height, entries, boxes };
    }

    function createGroup(entry, generation) {
      const frame = element("section", undefined, `map-group-frame${entry.expanded ? " expanded" : ""}`);
      frame.style.left = `${entry.frame.x}px`;
      frame.style.top = `${entry.frame.y}px`;
      frame.style.width = `${entry.frame.width}px`;
      frame.style.height = `${entry.frame.height}px`;
      const toggle = element("button", undefined, "map-group-toggle");
      toggle.type = "button";
      toggle.dataset.mapEquipment = entry.group.equipment;
      toggle.dataset.mapToggle = entry.group.equipment;
      toggle.setAttribute("aria-expanded", String(entry.expanded));
      toggle.setAttribute("aria-label", `${entry.group.equipment}, 측정 항목 ${formatNumber(entry.group.items.length)}개, ${entry.expanded ? "접기" : "펼치기"}`);
      toggle.style.left = "22px";
      toggle.style.top = "28px";
      toggle.append(element("span", entry.expanded ? "설비 묶음 · 펼침" : "설비 묶음 · 접힘"), element("strong", entry.group.equipment), element("small", `측정 항목 ${formatNumber(entry.group.items.length)}개`));
      toggle.addEventListener("click", () => {
        if (generation !== state.generation || blocked()) return;
        if (state.open.has(entry.group.equipment)) state.open.delete(entry.group.equipment);
        else state.open.add(entry.group.equipment);
        render({ focusTarget: { type: "group", equipment: entry.group.equipment } });
        announce(`${entry.group.equipment} 묶음을 ${state.open.has(entry.group.equipment) ? "펼쳤습니다." : "접었습니다."}`);
      });
      toggle.addEventListener("focus", () => keepReadable(entry.groupBox));
      frame.append(toggle);
      if (!entry.expanded) {
        const collapsed = element("p", "측정 항목을 보려면 설비 묶음을 펼치세요.", "map-group-collapsed");
        frame.append(collapsed);
        return frame;
      }

      const page = element("div", undefined, "map-item-pagination");
      const start = entry.items.length ? entry.offset + 1 : 0;
      const end = entry.offset + entry.items.length;
      const pages = Math.max(1, Math.ceil(entry.group.items.length / entry.capacity));
      const pageNumber = entry.group.items.length ? Math.floor(entry.offset / entry.capacity) + 1 : 1;
      const status = element("span", `항목 ${formatNumber(start)}–${formatNumber(end)} / ${formatNumber(entry.group.items.length)} · ${formatNumber(pageNumber)} / ${formatNumber(pages)}쪽`);
      status.dataset.mapItemsStatus = entry.group.equipment;
      const previous = element("button", "이전", "map-page-button");
      previous.type = "button";
      previous.dataset.mapEquipment = entry.group.equipment;
      previous.dataset.mapPage = "previous";
      previous.dataset.mapItemsPrev = entry.group.equipment;
      previous.setAttribute("aria-label", `${entry.group.equipment} 이전 측정 항목`);
      previous.disabled = entry.offset === 0;
      const next = element("button", "다음", "map-page-button");
      next.type = "button";
      next.dataset.mapEquipment = entry.group.equipment;
      next.dataset.mapPage = "next";
      next.dataset.mapItemsNext = entry.group.equipment;
      next.setAttribute("aria-label", `${entry.group.equipment} 다음 측정 항목`);
      next.disabled = end >= entry.group.items.length;
      previous.addEventListener("click", () => changeItemPage(entry, -1, generation));
      next.addEventListener("click", () => changeItemPage(entry, 1, generation));
      const pageBox = { x: entry.groupBox.x, y: entry.y + 116, width: GROUP_WIDTH, height: 64 };
      previous.addEventListener("focus", () => keepReadable(pageBox));
      next.addEventListener("focus", () => keepReadable(pageBox));
      page.append(previous, status, next);
      frame.append(page);
      return frame;
    }

    function changeItemPage(entry, direction, generation) {
      if (generation !== state.generation || blocked()) return;
      const nextOffset = clamp(entry.offset + direction * entry.capacity, 0, Math.max(0, entry.group.items.length - 1));
      state.offsets.set(entry.group.equipment, nextOffset);
      render({ focusTarget: { type: "page", equipment: entry.group.equipment, direction: direction < 0 ? "previous" : "next" } });
      announce(`${entry.group.equipment} 항목 ${direction < 0 ? "이전" : "다음"} 쪽을 표시합니다.`);
    }

    function createItemButton(entry, box, generation) {
      const item = box.item;
      const selected = state.selected?.equipment === entry.group.equipment && state.selected?.tag === item.tag;
      const button = element("button", undefined, "map-node");
      button.type = "button";
      button.dataset.mapEquipment = entry.group.equipment;
      button.dataset.mapTag = item.tag;
      button.style.left = `${box.x}px`;
      button.style.top = `${box.y}px`;
      button.setAttribute("aria-pressed", String(selected));
      button.setAttribute("aria-label", `${entry.group.equipment}, ${item.tag}, ${item.unit || "단위 없음"}, 파일 전체 ${formatNumber(item.count)}개 관측${selected ? ", 현재 선택" : ""}`);
      button.title = `${entry.group.equipment} · ${item.tag}`;
      button.disabled = state.busy;
      button.append(element("span", item.tag, "map-node-name"), element("small", `${item.unit || "단위 없음"} · 전체 ${formatNumber(item.count)}`));
      button.addEventListener("click", () => {
        if (generation !== state.generation || state.busy || blocked()) return;
        options.onSelect?.({ key: state.key, equipment: entry.group.equipment, tag: item.tag });
      });
      button.addEventListener("focus", () => keepReadable(box));
      return button;
    }

    function render({ focusTarget = null, initial = false } = {}) {
      const generation = state.generation;
      updateGroupControls();
      const groups = visibleGroups();
      const allocations = allocationsForVisibleGroups(groups);
      const layout = buildLayout(groups, allocations);
      state.layout = layout;
      world.replaceChildren();
      world.style.width = `${layout.width}px`;
      world.style.height = `${layout.height}px`;
      const lines = svgElement("svg", { class: "map-lines", viewBox: `0 0 ${layout.width} ${layout.height}`, width: layout.width, height: layout.height, "aria-hidden": "true", focusable: "false" });
      const layer = element("div", undefined, "map-node-layer");
      for (const entry of layout.entries) {
        layer.append(createGroup(entry, generation));
        for (const box of entry.itemBoxes) {
          lines.append(svgElement("line", {
            x1: entry.groupBox.x + entry.groupBox.width,
            y1: entry.groupBox.y + entry.groupBox.height / 2,
            x2: box.x,
            y2: box.y + box.height / 2
          }));
          layer.append(createItemButton(entry, box, generation));
        }
      }
      world.append(lines, layer);
      const displayedItems = layout.entries.reduce((sum, entry) => sum + entry.items.length, 0);
      const openCount = groups.filter((group) => state.open.has(group.equipment)).length;
      overflow.textContent = `현재 쪽 설비 ${formatNumber(groups.length)}개 중 ${formatNumber(openCount)}개 펼침 · 측정 항목 ${formatNumber(displayedItems)} / 최대 ${formatNumber(ITEM_BUDGET)}개 표시 · 각 묶음의 이전·다음으로 전체 항목에 접근할 수 있습니다.`;
      renderMinimap();
      if (initial || !state.cameraInitialized) scheduleCamera(() => fit(false));
      else applyCamera();
      if (focusTarget) scheduleCamera(() => focusRenderedTarget(focusTarget));
    }

    function scheduleCamera(work) {
      const generation = state.generation;
      cancelAnimationFrame(state.renderFrame);
      state.renderFrame = requestAnimationFrame(() => {
        state.renderFrame = null;
        if (generation === state.generation && state.key) work();
      });
    }

    function focusRenderedTarget(target) {
      let selector;
      if (target.type === "group") selector = "[data-map-toggle]";
      else if (target.type === "page") selector = `[data-map-page="${target.direction}"]`;
      else selector = "[data-map-tag]";
      let match = [...world.querySelectorAll(selector)].find((button) => {
        if (button.dataset.mapEquipment !== target.equipment) return false;
        return target.type !== "item" || button.dataset.mapTag === target.tag;
      });
      if (target.type === "page" && (!match || match.disabled)) {
        match = [...world.querySelectorAll("[data-map-page]")].find((button) => button.dataset.mapEquipment === target.equipment && !button.disabled)
          || [...world.querySelectorAll("[data-map-toggle]")].find((button) => button.dataset.mapEquipment === target.equipment);
      }
      if (match && !blocked()) match.focus({ preventScroll: true });
    }

    function prepareSelection() {
      if (!state.selected) return false;
      const groupIndex = state.groups.findIndex((group) => group.equipment === state.selected.equipment);
      if (groupIndex < 0) return false;
      state.groupPage = Math.floor(groupIndex / GROUP_PAGE_SIZE);
      state.open.add(state.selected.equipment);
      const groups = visibleGroups();
      const group = groups.find((item) => item.equipment === state.selected.equipment);
      const allocations = allocationsForVisibleGroups(groups);
      const capacity = Math.max(1, allocations.get(group.equipment) || 1);
      const itemIndex = group.items.findIndex((item) => item.tag === state.selected.tag);
      if (itemIndex < 0) return false;
      state.offsets.set(group.equipment, Math.floor(itemIndex / capacity) * capacity);
      return true;
    }

    function revealSelection({ focus = false, announceChange = false } = {}) {
      if (!prepareSelection()) {
        announce("현재 선택 항목의 지도 위치를 찾을 수 없습니다.");
        return;
      }
      render({ focusTarget: focus ? { type: "item", ...state.selected } : null });
      scheduleCamera(() => {
        const box = state.layout?.boxes.get(itemIdentity(state.selected.equipment, state.selected.tag));
        if (!box) return;
        centerBox(box, Math.max(state.scale, READABLE_SCALE));
        if (focus && !blocked()) focusRenderedTarget({ type: "item", ...state.selected });
        if (announceChange) announce(`${state.selected.equipment}의 ${state.selected.tag} 위치를 표시합니다.`);
      });
    }

    function viewportSize() {
      return { width: root.clientWidth, height: root.clientHeight };
    }

    function applyCamera() {
      if (!state.layout) return;
      world.style.transform = `translate(${state.x}px,${state.y}px) scale(${state.scale})`;
      zoomLevel.value = `${Math.round(state.scale * 100)}%`;
      zoomLevel.textContent = `${Math.round(state.scale * 100)}%`;
      renderMinimap();
    }

    function fit(announceChange = true) {
      if (!state.layout) return;
      const view = viewportSize();
      if (view.width <= 0 || view.height <= 0) return;
      state.scale = clamp(Math.min((view.width - MAP_PADDING * 2) / state.layout.width, (view.height - MAP_PADDING * 2) / state.layout.height), MIN_SCALE, MAX_SCALE);
      state.x = (view.width - state.layout.width * state.scale) / 2;
      state.y = (view.height - state.layout.height * state.scale) / 2;
      state.viewWidth = view.width;
      state.viewHeight = view.height;
      state.cameraInitialized = true;
      applyCamera();
      if (announceChange) announce(`표시된 지도 전체에 맞췄습니다. 배율 ${Math.round(state.scale * 100)}%.`);
    }

    function centerBox(box, scale = state.scale) {
      const view = viewportSize();
      if (view.width <= 0 || view.height <= 0) return;
      // Returning to a node must reveal the whole focus target even after a
      // desktop-sized zoom is carried into a narrow viewport.
      const fittingScale = Math.min((view.width - 44) / box.width, (view.height - 44) / box.height);
      state.scale = clamp(Math.min(scale, fittingScale), MIN_SCALE, MAX_SCALE);
      state.x = view.width / 2 - (box.x + box.width / 2) * state.scale;
      state.y = view.height / 2 - (box.y + box.height / 2) * state.scale;
      state.viewWidth = view.width;
      state.viewHeight = view.height;
      state.cameraInitialized = true;
      applyCamera();
    }

    function keepReadable(box) {
      if (!box || blocked()) return;
      const view = viewportSize();
      if (!view.width || !view.height) return;
      const wantedScale = Math.max(state.scale, READABLE_SCALE);
      const left = box.x * wantedScale + state.x;
      const top = box.y * wantedScale + state.y;
      const right = (box.x + box.width) * wantedScale + state.x;
      const bottom = (box.y + box.height) * wantedScale + state.y;
      const margin = 22;
      if (wantedScale !== state.scale || left < margin || top < margin || right > view.width - margin || bottom > view.height - margin) centerBox(box, wantedScale);
    }

    function zoomBy(factor) {
      if (!state.layout) return;
      const view = viewportSize();
      const oldScale = state.scale;
      const next = clamp(oldScale * factor, MIN_SCALE, MAX_SCALE);
      const worldX = (view.width / 2 - state.x) / oldScale;
      const worldY = (view.height / 2 - state.y) / oldScale;
      state.scale = next;
      state.x = view.width / 2 - worldX * next;
      state.y = view.height / 2 - worldY * next;
      state.cameraInitialized = true;
      applyCamera();
      announce(`지도 배율 ${Math.round(next * 100)}%.`);
    }

    function pan(dx, dy) {
      if (!state.layout) return;
      const amount = Math.max(56, Math.min(root.clientWidth, root.clientHeight) * 0.18);
      state.x -= dx * amount;
      state.y -= dy * amount;
      state.cameraInitialized = true;
      applyCamera();
      announce("방향 버튼으로 지도 위치를 옮겼습니다.");
    }

    function cancelPointer() {
      const pointer = state.pointer;
      state.pointer = null;
      root.classList.remove("map-panning");
      if (pointer && root.hasPointerCapture(pointer.id)) {
        try { root.releasePointerCapture(pointer.id); } catch (_) { /* Capture may already have ended. */ }
      }
      return pointer;
    }

    function setMoveMode(enabled, announceChange = true) {
      state.moveMode = Boolean(enabled && state.layout);
      if (!state.moveMode) cancelPointer();
      moveToggle.setAttribute("aria-pressed", String(state.moveMode));
      moveToggle.textContent = state.moveMode ? "지도 이동 켬" : "지도 이동 끔";
      root.classList.toggle("map-move-active", state.moveMode);
      if (announceChange) announce(state.moveMode ? "지도 이동을 켰습니다. 빈 배경을 끌어 옮기고 Esc로 끝낼 수 있습니다." : "지도 이동을 껐습니다. 방향 버튼으로도 위치를 옮길 수 있습니다.");
    }

    function cancelMove() {
      if (!state.moveMode) return false;
      setMoveMode(false);
      return true;
    }

    function renderMinimap() {
      minimap.replaceChildren();
      if (!state.layout) {
        minimap.disabled = true;
        return;
      }
      minimap.disabled = false;
      const svg = svgElement("svg", { viewBox: `0 0 ${state.layout.width} ${state.layout.height}`, preserveAspectRatio: "none", "aria-hidden": "true" });
      for (const entry of state.layout.entries) {
        svg.append(svgElement("rect", { x: entry.groupBox.x, y: entry.groupBox.y, width: entry.groupBox.width, height: entry.groupBox.height, class: "minimap-group" }));
        for (const box of entry.itemBoxes) {
          const selected = state.selected?.equipment === entry.group.equipment && state.selected?.tag === box.item.tag;
          svg.append(svgElement("rect", { x: box.x, y: box.y, width: box.width, height: box.height, class: selected ? "minimap-item selected" : "minimap-item" }));
        }
      }
      const view = viewportSize();
      const viewX = -state.x / state.scale;
      const viewY = -state.y / state.scale;
      svg.append(svgElement("rect", { x: viewX, y: viewY, width: view.width / state.scale, height: view.height / state.scale, class: "minimap-viewport" }));
      minimap.append(svg);
    }

    function clear(message = "") {
      state.generation += 1;
      state.key = null;
      state.groups = [];
      state.selected = null;
      state.layout = null;
      state.open.clear();
      state.offsets.clear();
      state.cameraInitialized = false;
      cancelAnimationFrame(state.renderFrame);
      state.renderFrame = null;
      setMoveMode(false, false);
      world.replaceChildren();
      world.style.width = "100%";
      world.style.height = "100%";
      world.style.transform = "none";
      if (message) {
        const unavailable = element("div", undefined, "map-unavailable");
        unavailable.append(element("strong", "지도 근거를 확인할 수 없습니다."), element("p", message));
        world.append(unavailable);
      }
      overflow.textContent = "";
      updateGroupControls();
      renderMinimap();
      updateControls();
    }

    function setContext(context, settings = {}) {
      const changed = settings.forceReset || context.key !== state.key;
      if (changed) {
        state.generation += 1;
        state.key = context.key;
        state.groups = context.groups;
        state.groupPage = 0;
        state.open = new Set();
        state.offsets = new Map();
        state.scale = 1;
        state.x = 0;
        state.y = 0;
        state.cameraInitialized = false;
        setMoveMode(false, false);
      } else {
        state.groups = context.groups;
      }
      state.selected = context.selected;
      state.busy = Boolean(context.busy);
      if (changed) prepareSelection();
      if (settings.revealSelection && !changed) {
        revealSelection({ focus: settings.focusSelection, announceChange: false });
      } else {
        render({ initial: changed, focusTarget: settings.focusSelection ? { type: "item", ...state.selected } : null });
      }
      updateControls();
    }

    function setBusy(busy) {
      state.busy = Boolean(busy);
      for (const button of world.querySelectorAll("[data-map-tag]")) button.disabled = state.busy;
    }

    function resize() {
      if (!state.layout) return;
      const view = viewportSize();
      if (!view.width || !view.height) return;
      if (!state.cameraInitialized) {
        fit(false);
        return;
      }
      const oldWidth = state.viewWidth || view.width;
      const oldHeight = state.viewHeight || view.height;
      const centerX = (oldWidth / 2 - state.x) / state.scale;
      const centerY = (oldHeight / 2 - state.y) / state.scale;
      state.x = view.width / 2 - centerX * state.scale;
      state.y = view.height / 2 - centerY * state.scale;
      state.viewWidth = view.width;
      state.viewHeight = view.height;
      applyCamera();
    }

    function updateControls() {
      const available = Boolean(state.layout);
      for (const button of [zoomIn, zoomOut, fitButton, focusButton, moveToggle, ...Object.keys(panButtons).map((id) => document.getElementById(id))]) button.disabled = !available;
      focusButton.disabled = !available || !state.selected;
      zoomLevel.value = `${Math.round(state.scale * 100)}%`;
      zoomLevel.textContent = `${Math.round(state.scale * 100)}%`;
    }

    zoomIn.addEventListener("click", () => { if (!blocked()) zoomBy(1.25); });
    zoomOut.addEventListener("click", () => { if (!blocked()) zoomBy(0.8); });
    fitButton.addEventListener("click", () => { if (!blocked()) fit(true); });
    focusButton.addEventListener("click", () => { if (!blocked()) revealSelection({ focus: true, announceChange: true }); });
    moveToggle.addEventListener("click", () => { if (!blocked()) setMoveMode(!state.moveMode); });
    for (const [id, direction] of Object.entries(panButtons)) document.getElementById(id).addEventListener("click", () => { if (!blocked()) pan(...direction); });
    groupPrevious.addEventListener("click", () => {
      if (blocked() || groupPrevious.disabled) return;
      state.groupPage -= 1;
      render();
      (!groupPrevious.disabled ? groupPrevious : !groupNext.disabled ? groupNext : groupStatus).focus();
      announce("이전 설비 묶음 쪽을 표시합니다.");
    });
    groupNext.addEventListener("click", () => {
      if (blocked() || groupNext.disabled) return;
      state.groupPage += 1;
      render();
      (!groupNext.disabled ? groupNext : !groupPrevious.disabled ? groupPrevious : groupStatus).focus();
      announce("다음 설비 묶음 쪽을 표시합니다.");
    });
    minimap.addEventListener("click", (event) => {
      if (!state.layout || blocked()) return;
      if (!event.detail) {
        fit(true);
        return;
      }
      // Use the drawable SVG, excluding the button's border, so a miniature
      // node and its world coordinate identify the same point at every zoom.
      const bounds = minimap.querySelector("svg").getBoundingClientRect();
      const worldX = (event.clientX - bounds.left) / bounds.width * state.layout.width;
      const worldY = (event.clientY - bounds.top) / bounds.height * state.layout.height;
      const view = viewportSize();
      state.x = view.width / 2 - worldX * state.scale;
      state.y = view.height / 2 - worldY * state.scale;
      state.cameraInitialized = true;
      applyCamera();
      announce("미니맵에서 고른 위치로 이동했습니다.");
    });
    root.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || !state.moveMode || blocked()) return;
      event.preventDefault();
      event.stopPropagation();
      setMoveMode(false);
    });
    root.addEventListener("pointerdown", (event) => {
      if (!state.moveMode || state.pointer || blocked() || event.button !== 0 || event.target.closest("button,a,input,select,textarea")) return;
      state.pointer = { id: event.pointerId, clientX: event.clientX, clientY: event.clientY, x: state.x, y: state.y, dragged: false };
      root.setPointerCapture(event.pointerId);
      root.classList.add("map-panning");
      event.preventDefault();
    });
    root.addEventListener("pointermove", (event) => {
      if (!state.pointer || state.pointer.id !== event.pointerId) return;
      if (!state.moveMode || blocked()) {
        cancelPointer();
        return;
      }
      const dx = event.clientX - state.pointer.clientX;
      const dy = event.clientY - state.pointer.clientY;
      if (Math.hypot(dx, dy) >= 4) state.pointer.dragged = true;
      state.x = state.pointer.x + dx;
      state.y = state.pointer.y + dy;
      state.cameraInitialized = true;
      applyCamera();
      event.preventDefault();
    });
    function finishPointer(event) {
      if (!state.pointer || state.pointer.id !== event.pointerId) return;
      const pointer = cancelPointer();
      if (pointer.dragged) announce("지도를 옮겼습니다.");
    }
    root.addEventListener("pointerup", finishPointer);
    root.addEventListener("pointercancel", finishPointer);
    root.addEventListener("lostpointercapture", finishPointer);
    const resizeObserver = new ResizeObserver(() => resize());
    resizeObserver.observe(root);
    updateGroupControls();
    updateControls();
    renderMinimap();

    return { clear, setContext, setBusy, resize, revealSelection, cancelMove };
  }

  window.createFileReviewMapCanvas = createMapCanvas;
}());
