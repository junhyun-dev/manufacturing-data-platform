#!/usr/bin/env python3
"""Exercise presentation-only navigation against real local file-review HTTP.

Uses only fresh browser workspaces and deletes its own fixtures. Native fullscreen is
checked separately from labelled failure injections; stress inputs are synthetic.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/manufacturing_data_platform/file_review/static"
SAMPLE = ROOT / "src/manufacturing_data_platform/file_review/sample/metropt3-day.csv"


class DesktopKeys:
    """Send native browser accelerator keys only inside an explicitly owned Xvfb display."""
    def __init__(self):
        import ctypes
        import ctypes.util
        if os.environ.get("MFG_NAV_X11_TEST") != "1":
            raise RuntimeError("Use --native-desktop only through an isolated xvfb-run with MFG_NAV_X11_TEST=1")
        self.x = ctypes.CDLL(ctypes.util.find_library("X11"))
        self.xt = ctypes.CDLL(ctypes.util.find_library("Xtst"))
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.display = self.x.XOpenDisplay(None)
        assert self.display
        self.x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x.XStringToKeysym.restype = ctypes.c_ulong
        self.x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.XKeysymToKeycode.restype = ctypes.c_uint
        self.x.XFlush.argtypes = [ctypes.c_void_p]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

    def key(self, name, down):
        keycode = self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(name.encode()))
        assert keycode
        self.xt.XTestFakeKeyEvent(self.display, keycode, down, 0)
        self.x.XFlush(self.display)

    def press(self, name):
        self.key(name, True)
        self.key(name, False)

    def close(self):
        self.x.XCloseDisplay(self.display)


def stress_csv(count, offset=0):
    """Two observations per item; separate equipment repeats a name on purpose."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["timestamp", "equipment", "tag", "value", "unit"])
    prefix = '<img src=x onerror="window.navInjected=1">'
    hostile = prefix + "긴" * (128 - len(prefix))
    assert len(hostile) == 128
    tags = [f"temperature-{index:03}" for index in range(count - 1)] + [hostile]
    for index, tag in enumerate(tags):
        for second, value in [(0, 10 + index + offset), (20, 30 + index + offset)]:
            writer.writerow([f"2020-01-01T00:00:{second:02}", "Fixture-Pump", tag, value, "u"])
    for second, value in [(0, 1000), (20, 2000)]:
        writer.writerow([f"2020-01-01T00:00:{second:02}", "Fixture-Other", tags[0], value, "u"])
    return stream.getvalue().encode(), tags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("full", "sample"), default="full")
    parser.add_argument("--native-desktop", action="store_true", help="Isolated Xvfb: native Escape and 200%% browser zoom")
    parser.add_argument("--output", default=".cache/review-navigation-browser/" +
                        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only a loopback test server is supported.")
    base, output = args.url.rstrip("/"), Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    checks, errors, external, requests, created, measurements = [], [], [], [], [], []
    receipt = {"started_at": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
               "checks": checks, "page_errors": errors, "external_requests": external,
               "synthetic_search_observations": measurements,
               "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT))}
    desktop = DesktopKeys() if args.native_desktop else None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.native_desktop)
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="ko-KR")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(request.url) if "/api/" in request.url else None)
        page.on("request", lambda request: external.append(request.url) if urlparse(request.url).scheme in ("http", "https")
                and urlparse(request.url).netloc != urlparse(base).netloc else None)
        search = page.locator("#tag-search")
        found = page.locator("#tag-search-results [data-search-tag]")
        wide = page.locator("#review-wide-toggle")
        fullscreen = page.locator("#review-fullscreen-toggle")
        saved_cookies = None

        def idle():
            expect(page.locator("#loading")).to_be_hidden(timeout=30000)

        def frame():
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")

        def wait_browser(predicate, arg=None, timeout=10000):
            # CDP window/viewport changes can reset Playwright's utility world.
            # Poll direct browser evaluation without weakening the product CSP.
            deadline = time.monotonic() + timeout / 1000
            while not page.evaluate(predicate, arg):
                if time.monotonic() >= deadline:
                    raise AssertionError(f"Browser condition timed out: {predicate}")
                page.wait_for_timeout(50)

        def csrf():
            return context.request.get(base + "/api/session").json()["csrf_token"]

        def mutation(fragment, action):
            with page.expect_response(lambda r: fragment in r.url and r.request.method == "POST") as pending:
                action()
            response = pending.value
            assert response.ok, response.text()
            dataset = response.json()["dataset"]
            if dataset["id"] not in created:
                created.append(dataset["id"])
            idle()
            return dataset

        def sample():
            return mutation("/api/datasets/sample", lambda: page.locator("#welcome-sample" if page.locator("#welcome").is_visible() else "#sample-button").click())

        def upload(raw, name):
            return mutation("/api/datasets?", lambda: page.locator("#upload-input").set_input_files(
                {"name": name, "mimeType": "text/csv", "buffer": raw}))

        def query(status=200):
            with page.expect_response(lambda r: "/query?" in r.url) as pending:
                page.locator("#query-button").click()
            response = pending.value
            assert response.status == status, response.text()
            idle()
            return response.json()

        def state():
            # Read user-facing facts, not application globals or its context-key implementation.
            return page.evaluate("""() => ({
              draft: ['equipment-filter','tag-filter','start-filter','end-filter'].map(id=>document.getElementById(id).value),
              confirmed: ['query-selection','metric-count','metric-mean','metric-min','metric-max','result-version','map-selected-item'].map(id=>document.getElementById(id).textContent),
              resultVisible: !document.getElementById('query-results').hidden,
              exportDisabled: document.getElementById('export-button').disabled,
              source: document.getElementById('source-metadata').textContent,
              previous: !document.getElementById('previous-query').hidden,
              explanation: document.getElementById('explanation-answer').textContent
            })""")

        def unchanged(before, request_count):
            frame()
            assert state() == before, "Presentation/search changed selected or confirmed review facts"
            assert len(requests) == request_count, "Presentation/search caused an API request"

        def search_for(text, expected=None):
            search.fill(text)
            frame()
            expect(search).to_be_focused()
            if expected is not None:
                expect(found).to_have_count(expected)

        def result_tags():
            return found.evaluate_all("els=>els.map(el=>el.dataset.searchTag)")

        def choose(tag, keyboard=False):
            button = found.nth(result_tags().index(tag))
            button.focus()
            if keyboard:
                page.keyboard.press("Enter")
            else:
                button.click()
            expect(page.locator("#tag-filter")).to_have_value(tag)
            assert page.evaluate("document.activeElement===document.getElementById('tag-filter') || document.activeElement?.dataset.mapTag===document.getElementById('tag-filter').value")

        def zip_evidence(raw, result):
            values = [float(row["value"]) for row in csv.DictReader(io.StringIO(raw.decode()))
                      if row["equipment"] == result["equipment"] and row["tag"] == result["tag"]]
            assert result["summary"]["count"] == len(values)
            assert math.isclose(result["summary"]["mean"], statistics.fmean(values), abs_tol=1e-10)
            with page.expect_download() as pending:
                page.locator("#export-button").click()
            target = output / f"result-{len(list(output.glob('result-*.zip')))}.zip"
            pending.value.save_as(str(target))
            idle()
            with ZipFile(target) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                exported = archive.read("observations.csv")
            assert manifest["version"] == result["version"]
            assert manifest["equipment"] == result["equipment"] and manifest["tag"] == result["tag"]
            assert manifest["filter"] == result["filter"] and manifest["summary"] == result["summary"]
            assert manifest["source_sha256"] == hashlib.sha256(raw).hexdigest()
            assert manifest["observations_sha256"] == hashlib.sha256(exported).hexdigest()
            assert [float(r["value"]) for r in csv.DictReader(io.StringIO(exported.decode("utf-8-sig")))] == values
            return {key: manifest[key] for key in ("version", "source_sha256", "equipment", "tag", "filter", "summary", "observations_sha256")}

        def set_wide(enabled=True):
            active = "기본 화면" in wide.inner_text()
            if active != enabled:
                wide.click()
            expect(wide).to_contain_text("기본 화면" if enabled else "넓게 보기")

        def enter_fullscreen():
            fullscreen.click()
            wait_browser("document.fullscreenElement===document.documentElement")
            expect(fullscreen).to_contain_text("나가기")

        def exit_fullscreen():
            fullscreen.click()
            wait_browser("document.fullscreenElement===null")
            expect(fullscreen).not_to_contain_text("나가기")

        def screenshot(name):
            expect(page.locator("#toast")).to_be_hidden(timeout=10000)
            page.screenshot(path=str(output / name))

        def no_overflow():
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), "Page horizontally overflows"

        def cleared():
            expect(page.locator("#query-results")).to_be_hidden()
            assert found.count() == 0 or not found.first.is_visible()

        def native_checks():
            # A genuinely resizable browser window is separate from emulated phone
            # viewports. Reuse only this verifier's workspace cookie; no new fixtures.
            native = browser.new_context(no_viewport=True, locale="ko-KR",
                                         storage_state=context.storage_state())
            screen = native.new_page()
            screen.on("pageerror", lambda error: errors.append(str(error)))
            screen.on("request", lambda request: external.append(request.url) if urlparse(request.url).scheme in ("http", "https")
                      and urlparse(request.url).netloc != urlparse(base).netloc else None)
            api_calls = []
            screen.on("request", lambda request: api_calls.append(request.url) if "/api/" in request.url else None)
            cdp = native.new_cdp_session(screen)
            window = cdp.send("Browser.getWindowForTarget")

            def wait(predicate):
                deadline = time.monotonic() + 10
                while not screen.evaluate(predicate):
                    if time.monotonic() > deadline:
                        raise AssertionError("Native browser condition timed out: " + predicate)
                    screen.wait_for_timeout(50)

            def facts():
                return screen.evaluate("""() => ({
                  confirmed: ['query-selection','metric-count','metric-mean','metric-min','metric-max','result-version','map-selected-item'].map(id=>document.getElementById(id).textContent),
                  draft: ['equipment-filter','tag-filter','start-filter','end-filter'].map(id=>document.getElementById(id).value),
                  source: document.getElementById('source-metadata').textContent,
                  exportDisabled: document.getElementById('export-button').disabled
                })""")

            try:
                cdp.send("Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": {"width": 800, "height": 1050}})
                screen.goto(base)
                expect(screen.locator("#loading")).to_be_hidden(timeout=30000)
                expect(screen.locator("#query-results")).to_be_visible()
                wait("innerWidth<=850")
                screen.bring_to_front()
                screen.locator("#review-fullscreen-toggle").click()
                wait("document.fullscreenElement===document.documentElement")
                # Xvfb has no window manager to resize a fullscreen window. Drive
                # real window bounds explicitly; do not call this automatic OS sizing.
                cdp.send("Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": {"width": 1600, "height": 1200}})
                wait("innerWidth>850")
                screen.locator("#explanation-launcher").click()
                screen.locator('[data-explanation-question="handoff_limits"]').click()
                expect(screen.locator("#explanation-answer")).not_to_be_empty()
                answer = screen.locator("#explanation-answer").text_content()
                before, calls = facts(), len(api_calls)
                desktop.press("Escape")
                wait("document.fullscreenElement===null")
                cdp.send("Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": {"width": 800, "height": 1050}})
                wait("innerWidth<=850")
                expect(screen.locator("#explanation-panel")).to_be_visible()
                expect(screen.locator("#explanation-panel")).to_have_attribute("aria-modal", "true")
                expect(screen.locator("#explanation-answer")).to_have_text(answer)
                assert screen.evaluate("document.getElementById('explanation-panel').contains(document.activeElement)")
                assert facts() == before and len(api_calls) == calls
                screen.keyboard.press("Escape")
                expect(screen.locator("#explanation-panel")).to_be_hidden()
                assert not screen.evaluate("document.getElementById('application-shell').inert")
                screen.locator("#review-fullscreen-toggle").click()
                wait("document.fullscreenElement===document.documentElement")
                cdp.send("Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": {"width": 1440, "height": 1100}})
                wait("innerWidth>850")
                screen.locator("#explanation-launcher").click()
                screen.locator('[data-explanation-question="handoff_limits"]').click()
                expect(screen.locator("#explanation-answer")).not_to_be_empty()
                before, calls = facts(), len(api_calls)
                screen.locator("#delete-button").focus()
                screen.keyboard.press("Enter")
                expect(screen.locator("#delete-dialog")).to_be_visible()
                screen.evaluate("document.exitFullscreen()")
                cdp.send("Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": {"width": 800, "height": 1050}})
                wait("innerWidth<=850 && document.fullscreenElement===null")
                assert not screen.evaluate("document.getElementById('delete-dialog').inert"), "Resize made the active delete confirmation inert"
                assert screen.evaluate("document.getElementById('delete-dialog').contains(document.activeElement)")
                screen.keyboard.press("Escape")
                expect(screen.locator("#delete-dialog")).to_be_hidden()
                expect(screen.locator("#explanation-panel")).to_have_attribute("aria-modal", "true")
                assert screen.evaluate("document.getElementById('explanation-panel').contains(document.activeElement)")
                assert facts() == before and len(api_calls) == calls
                screen.keyboard.press("Escape")
                expect(screen.locator("#explanation-panel")).to_be_hidden()
                assert not screen.evaluate("document.getElementById('application-shell').inert")
                cdp.send("Browser.setWindowBounds", {"windowId": window["windowId"], "bounds": {"width": 1440, "height": 1100}})
                wait("innerWidth>850")
                before, calls = facts(), len(api_calls)
                base_dpr = screen.evaluate("devicePixelRatio")
                desktop.key("Control_L", True)
                try:
                    for _ in range(5):
                        desktop.press("plus")
                        screen.wait_for_timeout(60)
                finally:
                    desktop.key("Control_L", False)
                wait(f"devicePixelRatio/{base_dpr}>=1.95")
                zoom = round(100 * screen.evaluate("devicePixelRatio") / base_dpr)
                assert zoom == 200
                assert screen.evaluate("document.documentElement.scrollWidth<=innerWidth")
                screen.locator("#tag-search").fill("Oil")
                expect(screen.locator("#tag-search-results [data-search-tag]")).to_have_count(1)
                assert facts() == before and len(api_calls) == calls
                screen.locator("#tag-search").scroll_into_view_if_needed()
                screen.screenshot(path=str(output / "04-native-browser-200-percent.png"))
                desktop.key("Control_L", True)
                desktop.press("0")
                desktop.key("Control_L", False)
                wait(f"Math.abs(devicePixelRatio-{base_dpr})<0.05")
                return {"fullscreen_escape": "PASS", "breakpoint_answer_preservation": "PASS", "delete_dialog_resize": "PASS", "browser_zoom_percent": zoom,
                        "input": "XTest keys on isolated Xvfb, non-emulated native window",
                        "resize": "Explicit CDP native window bounds around fullscreen; automatic OS sizing not verified (no Xvfb window manager)"}
            except Exception:
                screen.screenshot(path=str(output / "failure-native-window.png"))
                raise
            finally:
                native.close()

        try:
            page.goto(base)
            idle()
            receipt["browser"] = browser.version
            receipt["health"] = context.request.get(base + "/healthz").json()
            assert receipt["health"]["mode"] == args.mode
            assets = {}
            for endpoint, name in [("/", "index.html"), ("/app.js", "app.js"), ("/styles.css", "styles.css"), ("/map-canvas.js", "map-canvas.js")]:
                served = context.request.get(base + endpoint).body()
                assert served == (STATIC / name).read_bytes()
                assets[name] = hashlib.sha256(served).hexdigest()
            receipt["served_assets_sha256"] = assets
            assert not wide.is_visible() or wide.is_disabled()
            first = sample()
            raw = SAMPLE.read_bytes()
            before, calls = state(), len(requests)
            search_for("  oil_TEMPERATURE  ", 1)
            unchanged(before, calls)
            choose("Oil_temperature", keyboard=True)
            selected = query()
            original_zip = zip_evidence(raw, selected)
            # Unsubmitted dates must stay drafts through navigation and a repeated ZIP export.
            page.locator("#start-filter").fill("2021-01-01T00:00")
            before, calls = state(), len(requests)
            search_for("no-such-item", 0)
            expect(page.locator("#tag-search-status")).not_to_be_empty()
            page.locator("#tag-search-clear").click()
            expect(search).to_have_value("")
            unchanged(before, calls)
            set_wide()
            unchanged(before, calls)
            enter_fullscreen()
            unchanged(before, calls)
            screenshot("01-native-fullscreen-sample.png")
            exit_fullscreen()
            unchanged(before, calls)
            expect(wide).to_contain_text("기본 화면")
            set_wide(False)
            unchanged(before, calls)
            expect(wide).to_be_focused()
            assert zip_evidence(raw, selected) == original_zip
            checks.append("real sample name search/keyboard selection, independent CSV/ZIP; drafts/results unchanged by search/clear/wide/native fullscreen")

            page.locator("#explanation-launcher").click()
            page.locator('[data-explanation-question="previous_result"]').click()
            expect(page.locator("#explanation-answer")).not_to_be_empty()
            before, calls = state(), len(requests)
            search_for("Motor", 1)
            set_wide()
            enter_fullscreen()
            exit_fullscreen()
            set_wide(False)
            unchanged(before, calls)
            page.locator("#explanation-close").click()
            checks.append("existing explanation answer survives metadata search and every presentation mode transition")

            # Actual browser fullscreen request, then external API exit drives the real change event.
            before, calls = state(), len(requests)
            enter_fullscreen()
            page.evaluate("document.exitFullscreen()")
            wait_browser("document.fullscreenElement===null")
            expect(fullscreen).not_to_contain_text("나가기")
            unchanged(before, calls)
            if desktop:
                enter_fullscreen()
                desktop.press("Escape")
                wait_browser("document.fullscreenElement===null", timeout=5000)
                unchanged(before, calls)
            enter_fullscreen()
            wide.click()
            wait_browser("document.fullscreenElement===null")
            expect(wide).to_contain_text("넓게 보기")
            unchanged(before, calls)
            checks.append("native fullscreen change/explicit exit/base return synchronize state without changing review facts; native Escape additionally checked in desktop mode")

            # Inject only the optional API boundary, never a successful native fullscreen result.
            page.evaluate("""() => {window.__nativeFullscreen=document.documentElement.requestFullscreen;
              document.documentElement.requestFullscreen=()=>Promise.reject(new DOMException('Fixture denied','NotAllowedError'));} """)
            before, calls = state(), len(requests)
            fullscreen.click()
            expect(page.locator("#review-view-status")).not_to_be_empty()
            expect(wide).to_contain_text("기본 화면")
            assert page.evaluate("document.fullscreenElement===null")
            unchanged(before, calls)
            page.evaluate("document.documentElement.requestFullscreen=undefined")
            # Support may be checked at load or action time; both preserve an ordinary accessible layout.
            if not fullscreen.is_disabled():
                fullscreen.click()
            unchanged(before, calls)
            page.evaluate("document.documentElement.requestFullscreen=window.__nativeFullscreen;delete window.__nativeFullscreen")
            checks.append("labelled denied/unsupported fullscreen API injections preserve wide view, selection and ZIP eligibility")
            set_wide(False)

            enter_fullscreen()
            page.evaluate("""() => {window.__nativeExit=document.exitFullscreen;
              document.exitFullscreen=()=>Promise.reject(new DOMException('Fixture exit denied','NotAllowedError'));} """)
            before, calls = state(), len(requests)
            wide.click()
            expect(wide).to_be_enabled()
            expect(wide).to_contain_text("기본 화면")
            assert page.evaluate("document.fullscreenElement===document.documentElement")
            fullscreen.click()
            expect(fullscreen).to_be_enabled()
            expect(fullscreen).to_contain_text("나가기")
            unchanged(before, calls)
            page.evaluate("document.exitFullscreen=window.__nativeExit;delete window.__nativeExit")
            exit_fullscreen()
            set_wide(False)
            checks.append("labelled native-exit rejection keeps actual fullscreen state and reachable retry/base controls")

            page.evaluate("""() => {window.__nativeFullscreen=document.documentElement.requestFullscreen;
              window.__fullscreenCalls=0;
              document.documentElement.requestFullscreen=function() {
                window.__fullscreenCalls++;
                return window.__nativeFullscreen.call(this).then(()=>new Promise(resolve=>{window.__releaseFullscreen=resolve}));
              };} """)
            before, calls = state(), len(requests)
            enter_fullscreen()
            page.locator("#review-fullscreen-toggle").evaluate("el=>{el.click();el.click()}")
            assert page.evaluate("window.__fullscreenCalls") == 1
            wait_browser("typeof window.__releaseFullscreen==='function'")
            page.evaluate("window.__releaseFullscreen()")
            expect(fullscreen).to_be_enabled()
            exit_fullscreen()
            unchanged(before, calls)
            page.evaluate("document.documentElement.requestFullscreen=window.__nativeFullscreen;delete window.__nativeFullscreen;delete window.__releaseFullscreen")
            checks.append("labelled delayed promise around real native fullscreen prevents duplicate transitions and preserves confirmed result")

            # Clear the unsubmitted dates, then confirm a fresh result for modal coexistence.
            page.locator("#start-filter").fill("")
            selected = query()
            enter_fullscreen()
            page.locator("#explanation-launcher").click()
            page.locator('[data-explanation-question="handoff_limits"]').click()
            expect(page.locator("#explanation-answer")).not_to_be_empty()
            before = state()
            # The existing non-modal explanation can cover the pointer target;
            # use the real keyboard path to exercise both layers together.
            page.locator("#delete-button").focus()
            page.keyboard.press("Enter")
            expect(page.locator("#delete-dialog")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#delete-dialog")).to_be_hidden()
            expect(page.locator("#explanation-panel")).to_be_visible()
            assert state() == before
            assert context.request.get(base + "/api/datasets/" + first["id"]).ok
            page.keyboard.press("Escape")
            expect(page.locator("#explanation-panel")).to_be_hidden()
            expect(page.locator("#explanation-launcher")).to_be_focused()
            if page.evaluate("document.fullscreenElement!==null"):
                exit_fullscreen()
            checks.append("actual fullscreen explanation and native delete-dialog Escape own one layer; no deletion or stranded focus")

            for width, height in [(390, 844), (320, 844), (844, 390)]:
                page.set_viewport_size({"width": width, "height": height})
                set_wide()
                search_for("TP2", 1)
                choose("TP2", keyboard=True)
                selected = query()
                no_overflow()
                page.locator("#tag-search").scroll_into_view_if_needed()
                screenshot(f"02-wide-{width}x{height}.png")
                enter_fullscreen()
                page.locator("#explanation-launcher").click()
                expect(page.locator("#explanation-panel")).to_have_attribute("aria-modal", "true")
                page.keyboard.press("Tab")
                assert page.evaluate("document.getElementById('explanation-panel').contains(document.activeElement)")
                # A real external fullscreen change while modal is open must not steal focus.
                page.evaluate("document.exitFullscreen()")
                frame()
                assert page.evaluate("document.getElementById('explanation-panel').contains(document.activeElement)")
                page.keyboard.press("Escape")
                expect(page.locator("#explanation-panel")).to_be_hidden()
                expect(page.locator("#explanation-launcher")).to_be_focused()
                assert not page.evaluate("document.getElementById('application-shell').inert")
                set_wide(False)
                expect(wide).to_be_focused()
            checks.append("390/320px and landscape keyboard/list/normal scroll; fullscreen exit during narrow explanation keeps modal focus then restores launcher")
            page.set_viewport_size({"width": 1440, "height": 1100})

            # A genuine held response survives view/search only, but not actual selection changes.
            held = []
            page.route("**/query?*", lambda route: held.append(route))
            page.locator("#query-button").click()
            expect(page.locator("#loading")).to_be_visible()
            assert len(held) == 1
            calls = len(requests)
            set_wide()
            search_for("Oil", 1)
            assert len(requests) == calls
            route = held.pop()
            response = route.fetch()
            route.fulfill(response=response)
            idle()
            expect(page.locator("#query-results")).to_be_visible()
            expect(page.locator("#query-selection")).to_contain_text("TP2")
            page.unroute("**/query?*")
            checks.append("genuine delayed query finishes across presentation/search changes without new request or selection drift")

            if args.mode == "full":
                for count in (8, 11, 50, 200):
                    raw_stress, tags = stress_csv(count)
                    fixture = upload(raw_stress, f"synthetic-{count}-items.csv")
                    page.locator("#equipment-filter").select_option("Fixture-Pump")
                    expect(search).to_have_value("")
                    assert page.locator("#tag-filter option").count() == count
                    before, calls = state(), len(requests)
                    start = time.perf_counter()
                    search_for("temperature", min(20, count - 1))
                    all_found = result_tags()
                    while page.locator("#tag-search-next").is_visible() and page.locator("#tag-search-next").is_enabled():
                        page.locator("#tag-search-next").click()
                        frame()
                        assert found.count() <= 20
                        all_found.extend(result_tags())
                    assert all_found == sorted(tags[:-1])
                    if count > 21:
                        page.locator("#tag-search-prev").click()
                        frame()
                        assert found.count() == 20
                    unchanged(before, calls)
                    measurements.append({"items": count, "matching_items": count - 1,
                                         "all_pages_elapsed_seconds": round(time.perf_counter() - start, 3),
                                         "kind": "synthetic browser exercise, not benchmark/SLA"})
                    target = tags[-2]
                    search_for(target, 1)
                    choose(target, keyboard=True)
                    expect(page.locator("#query-results")).to_be_hidden()
                    assert 1 <= page.locator("#equipment-map [data-map-tag]").count() <= 200
                    assert target in page.locator("#equipment-map [data-map-tag]").evaluate_all("els=>els.map(el=>el.dataset.mapTag)")
                    result = query()
                    zip_evidence(raw_stress, result)
                    before, calls = state(), len(requests)
                    search_for(target, 1)
                    choose(target)
                    unchanged(before, calls)
                    search_for("onerror", 1)
                    expect(found.first).to_contain_text(tags[-1])
                    assert page.locator("#tag-search-results img").count() == 0
                    assert page.evaluate("window.navInjected || 0") == 0
                    choose(tags[-1], keyboard=True)
                    result = query()
                    page.set_viewport_size({"width": 320, "height": 844})
                    no_overflow()
                    screenshot(f"03-synthetic-{count}-long-name.png")
                    page.set_viewport_size({"width": 1440, "height": 1100})
                    page.locator("#equipment-filter").select_option("Fixture-Other")
                    expect(search).to_have_value("")
                    search_for(tags[0], 1)
                    choose(tags[0])
                    result = query()
                    assert result["summary"]["mean"] == 1500
                    # Release only this fixture to avoid consuming the user's dataset quota.
                    assert context.request.delete(base + "/api/datasets/" + fixture["id"], headers={"X-Review-CSRF": csrf()}).ok
                checks.append("synthetic 8/11/50/200-item full search pagination, 128-character hostile names, selected overflow node, same-name equipment isolation and independent ZIP")
                second_raw, tags = stress_csv(11, offset=100)
                second = upload(second_raw, "synthetic-same-label-other-file.csv")
                page.locator("#equipment-filter").select_option("Fixture-Pump")
                search_for(tags[0], 1)
                choose(tags[0])
                result = query()
                assert result["summary"]["mean"] == 120
                refused = mutation("/replace?", lambda: page.locator("#replace-input").set_input_files(
                    {"name": "invalid.csv", "mimeType": "text/csv", "buffer": b"invalid,data\n1,2\n"}))
                assert refused["current"]["version"] == second["current"]["version"]
                expect(search).to_have_value("")
                result = query()
                assert result["previous_result"]
                zip_evidence(second_raw, result)
                checks.append("different file does not inherit search/identity; refused replacement keeps previous result and same-file ZIP")

            # Refresh and terminal errors share existing authorization/current boundaries.
            set_wide(False)
            current = sample()
            set_wide()
            if desktop:
                receipt["native_desktop"] = native_checks()
                page.bring_to_front()
                checks.append("headed Chromium native browser Escape, fullscreen breakpoint answer preservation and actual 200% browser zoom")
            else:
                receipt["native_desktop"] = "NOT RUN; requires isolated Xvfb --native-desktop"
            search_for("Oil", 1)
            assert context.request.post(base + "/api/datasets/" + current["id"] + "/retry", headers={"X-Review-CSRF": csrf()}).ok
            query()
            cleared()
            page.locator("#map-refresh").click()
            idle()
            expect(search).to_have_value("")
            result = query()
            page.route("**/query?*", lambda route: route.fulfill(status=503, content_type="application/json",
                       body=json.dumps({"error": {"code": "UNAVAILABLE", "message": "Fixture transient query"}})))
            query(503)
            expect(page.locator("#query-results")).to_be_hidden()
            search_for("Oil", 1)
            page.unroute("**/query?*")
            query()
            page.route("**/query?*", lambda route: route.fulfill(status=409, content_type="application/json",
                       body=json.dumps({"error": {"code": "INTEGRITY", "message": "Fixture integrity refusal"}})))
            query(409)
            cleared()
            page.unroute("**/query?*")
            page.locator("#map-refresh").click()
            idle()
            result = query()
            assert context.request.delete(base + "/api/datasets/" + current["id"], headers={"X-Review-CSRF": csrf()}).ok
            query(404)
            cleared()
            set_wide(False)
            current = sample()
            set_wide()
            search_for("Oil", 1)
            saved_cookies = context.cookies()
            context.clear_cookies()
            query(401)
            cleared()
            set_wide(False)
            checks.append("real changed-latest/deleted/missing-cookie refusal and labelled 503/integrity injections clear stale results/search while exits remain reachable")
            assert errors == [] and external == [], (errors, external)
            receipt["status"] = "PASS"
        except Exception as error:
            receipt.update(status="FAIL", failure=f"{type(error).__name__}: {error}")
            page.screenshot(path=str(output / "failure.png"), full_page=True)
            raise
        finally:
            try:
                if saved_cookies is not None:
                    context.add_cookies(saved_cookies)
                token = csrf()
                for dataset_id in created:
                    response = context.request.delete(base + "/api/datasets/" + dataset_id, headers={"X-Review-CSRF": token})
                    assert response.status in (200, 404), response.text()
                receipt["fixture_cleanup"] = "PASS"
            except Exception as error:
                receipt["fixture_cleanup"] = f"FAIL: {error}"
                receipt["status"] = "FAIL"
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            browser.close()
            if desktop:
                desktop.close()
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt.get("status") != "PASS":
        raise RuntimeError(receipt.get("failure") or receipt.get("fixture_cleanup"))


if __name__ == "__main__":
    main()
