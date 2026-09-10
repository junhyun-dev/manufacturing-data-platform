#!/usr/bin/env python3
"""Verify the dedicated map's screen area and unchanged review evidence locally."""
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from verify_review_navigation_browser import DesktopKeys, stress_csv

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/manufacturing_data_platform/file_review/static"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--native-desktop", action="store_true")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only an owned loopback preview or fixture server is allowed")
    base, out = args.url.rstrip("/"), Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    checks, requests, errors, external, created = [], [], [], [], []
    receipt = {"started_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
               "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "dirty": bool(subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT)),
               "geometry": [], "page_errors": errors, "external_requests": external}
    desktop = DesktopKeys() if args.native_desktop else None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.native_desktop)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR", reduced_motion="reduce")
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url) if "/api/" in r.url else None)
        page.on("request", lambda r: external.append(r.url) if urlparse(r.url).scheme in ("http", "https")
                and urlparse(r.url).netloc != urlparse(base).netloc else None)

        def idle():
            expect(page.locator("#loading")).to_be_hidden(timeout=30000)

        def settled():
            page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")

        def mutation(part, action):
            with page.expect_response(lambda r: part in r.url and r.request.method == "POST") as pending:
                action()
            assert pending.value.ok, pending.value.text()
            dataset = pending.value.json()["dataset"]
            if dataset["id"] not in created:
                created.append(dataset["id"])
            idle()
            return dataset

        def query():
            with page.expect_response(lambda r: "/query?" in r.url) as pending:
                page.locator("#query-button").click()
            assert pending.value.ok, pending.value.text()
            idle()
            return pending.value.json()

        def facts():
            return page.evaluate("""()=>({
              draft:['equipment-filter','tag-filter','start-filter','end-filter'].map(id=>document.getElementById(id).value),
              result:['query-selection','metric-count','metric-mean','metric-min','metric-max','result-version','map-selected-item'].map(id=>document.getElementById(id).textContent),
              source:document.getElementById('source-metadata').textContent,
              visible:!document.getElementById('query-results').hidden,
              exportDisabled:document.getElementById('export-button').disabled,
              answer:document.getElementById('explanation-answer').textContent
            })""")

        def unchanged(before, count):
            settled()
            assert facts() == before, "Presentation changed review facts"
            assert len(requests) == count, "Presentation sent a new API request"

        def focused(active=True):
            page.wait_for_function("""expected=>document.getElementById('map-fullscreen-layer')
                .contains(document.getElementById('equipment-map-section'))===expected""", arg=active)
            assert page.evaluate("document.getElementById('equipment-map-section')===window.testOriginalMap")
            assert page.evaluate("document.getElementById('main').inert") == active

        def enter():
            page.locator("#map-fullscreen-toggle").click()
            focused()
            expect(page.locator("#map-fullscreen-toggle")).to_be_enabled()

        def leave():
            page.locator("#map-fullscreen-toggle").click()
            focused(False)
            expect(page.locator("#map-fullscreen-toggle")).to_be_focused()

        def geometry(label, width_share, height_share):
            expression = """()=>{const r=document.getElementById('equipment-map').getBoundingClientRect();
                return {x:r.x,y:r.y,width:r.width,height:r.height,vw:innerWidth,vh:innerHeight,
                  widthShare:r.width/innerWidth,heightShare:r.height/innerHeight};}"""
            try:
                page.wait_for_function("""limits=>{const r=document.getElementById('equipment-map').getBoundingClientRect();
                  return r.width/innerWidth>=limits[0] && r.height/innerHeight>=limits[1]
                    && r.x>=-1 && r.y>=-1 && r.right<=innerWidth+1 && r.bottom<=innerHeight+1;}""",
                                       arg=[width_share, height_share], timeout=5000)
            finally:
                result = page.evaluate(expression)
                result["label"] = label
                receipt["geometry"].append(result)
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.screenshot(path=str(out / (label + ".png")))

        def zip_oracle(raw, result, name):
            rows = [r for r in csv.DictReader(io.StringIO(raw.decode()))
                    if r["equipment"] == result["equipment"] and r["tag"] == result["tag"]]
            values = [float(r["value"]) for r in rows]
            assert len(values) == result["summary"]["count"]
            assert math.isclose(statistics.fmean(values), result["summary"]["mean"], abs_tol=1e-10)
            with page.expect_download() as pending:
                page.locator("#export-button").click()
            pending.value.save_as(str(out / name))
            idle()
            with ZipFile(out / name) as z:
                manifest, data = json.loads(z.read("manifest.json")), z.read("observations.csv")
            for key in ("version", "equipment", "tag", "filter", "summary"):
                assert manifest[key] == result[key]
            assert manifest["source_sha256"] == hashlib.sha256(raw).hexdigest()
            assert manifest["observations_sha256"] == hashlib.sha256(data).hexdigest()
            return manifest

        try:
            receipt.update(browser=browser.version, health=context.request.get(base + "/healthz").json())
            receipt["assets_sha256"] = {}
            for name in ("index.html", "app.js", "styles.css", "map-canvas.js"):
                response = context.request.get(base + ("/" if name == "index.html" else "/" + name))
                assert response.body() == (STATIC / name).read_bytes(), name
                receipt["assets_sha256"][name] = hashlib.sha256(response.body()).hexdigest()
            page.goto(base)
            idle()
            mutation("/api/datasets/sample", lambda: page.locator("#welcome-sample").click())
            page.evaluate("window.testOriginalMap=document.getElementById('equipment-map-section')")
            page.locator("#tag-filter").select_option("Oil_temperature")
            result = query()
            sample_raw = (ROOT / "src/manufacturing_data_platform/file_review/sample/metropt3-day.csv").read_bytes()
            receipt["sample_zip"] = zip_oracle(sample_raw, result, "before.zip")
            # An unsubmitted date edit must stay distinct from the displayed result.
            page.locator("#start-filter").fill("2021-01-01T00:00")
            before, count = facts(), len(requests)
            page.evaluate("document.documentElement.requestFullscreen=undefined")
            page.evaluate("document.querySelector('.sidebar').inert=true")
            for width, height in ((1440, 900), (390, 844), (320, 844)):
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_function("document.getElementById('map-view-toggle').hidden===(innerWidth>850)")
                enter()
                assert not page.evaluate("Boolean(document.fullscreenElement)")
                geometry(f"fallback-{width}", .85 if width == 1440 else .9, .65 if width == 1440 else .5)
                page.locator("#map-fullscreen-layer").evaluate("el=>el.scrollTop=el.scrollHeight")
                settled()
                assert page.locator("#map-fullscreen-toggle").evaluate("el=>{const r=el.getBoundingClientRect();return r.y>=0&&r.bottom<=innerHeight}"), "Scrolling hid the map exit"
                page.locator("#map-fullscreen-layer").evaluate("el=>el.scrollTop=0")
                for control in ("map-zoom-in", "map-pan-right", "map-fit", "map-focus-selection"):
                    page.locator("#" + control).focus()
                    page.keyboard.press("Enter")
                unchanged(before, count)
                # Tab cannot enter the covered review background.
                for _ in range(8):
                    page.keyboard.press("Tab")
                    assert page.evaluate("document.activeElement===document.body || document.getElementById('map-fullscreen-layer').contains(document.activeElement) || document.activeElement.id==='explanation-launcher'")
                leave()
                unchanged(before, count)
                assert page.evaluate("document.querySelector('.sidebar').inert"), "Pre-existing inert value was lost"
            page.evaluate("document.querySelector('.sidebar').inert=false")
            checks.append("real 1440/390/320 map bounds, same DOM, camera/keyboard and unchanged query under labelled unsupported fallback")

            enter()
            page.locator("#map-pan-toggle").click()
            page.locator("#equipment-map").focus()
            page.keyboard.press("Escape")
            focused()
            expect(page.locator("#map-pan-toggle")).to_have_attribute("aria-pressed", "false")
            page.keyboard.press("Escape")
            focused(False)
            unchanged(before, count)
            enter()
            page.locator("#map-source-link").click()
            focused(False)
            expect(page.locator("#source-details")).to_have_attribute("open", "")
            assert page.evaluate("document.getElementById('source-details').contains(document.activeElement)")
            unchanged(before, count)
            enter()
            page.locator("#map-review-link").click()
            focused(False)
            assert page.evaluate("document.getElementById('query-results').contains(document.activeElement)")
            receipt["after_zip"] = zip_oracle(sample_raw, result, "after.zip")
            assert receipt["sample_zip"]["observations_sha256"] == receipt["after_zip"]["observations_sha256"]
            checks.append("move-mode Escape and map Escape act once; source/analysis focus and actual same-version ZIP preserved")

            page.set_viewport_size({"width": 1440, "height": 900})
            page.evaluate("""()=>{window.testEntryCalls=0;document.documentElement.requestFullscreen=()=>{
              window.testEntryCalls++;return new Promise(resolve=>{window.testResolveEntry=resolve})}}""")
            before, count = facts(), len(requests)
            page.locator("#map-fullscreen-toggle").click()
            focused()
            expect(page.locator("#map-fullscreen-toggle")).to_be_enabled()
            page.locator("#map-fullscreen-toggle").click()
            focused(False)
            expect(page.locator("#map-fullscreen-toggle")).to_be_disabled()
            page.locator("#map-fullscreen-toggle").evaluate("el=>el.click()")
            assert page.evaluate("window.testEntryCalls") == 1
            page.evaluate("window.testResolveEntry()")
            expect(page.locator("#map-fullscreen-toggle")).to_be_enabled()
            assert not page.evaluate("Boolean(document.fullscreenElement)")
            unchanged(before, count)
            page.evaluate("()=>{document.documentElement.requestFullscreen=()=>Promise.reject(new Error('Synthetic entry denial'))}")
            enter()
            assert not page.evaluate("Boolean(document.fullscreenElement)")
            geometry("denied-entry", .85, .65)
            before, count = facts(), len(requests)
            leave()
            unchanged(before, count)
            page.evaluate("delete document.documentElement.requestFullscreen")
            page.locator("#review-wide-toggle").click()
            assert page.evaluate("document.body.classList.contains('review-wide')")
            enter()
            page.wait_for_function("document.fullscreenElement===document.documentElement")
            before, count = facts(), len(requests)
            page.evaluate("()=>{document.exitFullscreen=()=>Promise.reject(new Error('Synthetic exit denial'))}")
            page.locator("#map-fullscreen-toggle").click()
            expect(page.locator("#map-fullscreen-toggle")).to_be_enabled()
            focused()
            assert page.evaluate("Boolean(document.fullscreenElement)")
            unchanged(before, count)
            page.evaluate("delete document.exitFullscreen")
            leave()
            assert page.evaluate("document.body.classList.contains('review-wide') && !document.fullscreenElement")
            unchanged(before, count)
            page.locator("#review-fullscreen-toggle").click()
            page.wait_for_function("!!document.fullscreenElement")
            enter()
            leave()
            assert page.evaluate("Boolean(document.fullscreenElement)"), "Map exit dropped a pre-existing review fullscreen"
            page.locator("#review-fullscreen-toggle").click()
            page.wait_for_function("!document.fullscreenElement")
            checks.append("real native entry/button exit; prior wide/native modes restored; labelled entry/exit failures retain visible exits")

            # Keep a real response pending while both presentation transitions run.
            page.locator("#start-filter").fill("")
            held = []
            page.route("**/query?*", lambda route: held.append(route))
            page.locator("#query-button").click()
            expect(page.locator("#loading")).to_be_visible()
            before, count = facts(), len(requests)
            page.evaluate("document.documentElement.requestFullscreen=undefined")
            enter()
            leave()
            unchanged(before, count)
            route = held.pop()
            route.fulfill(response=route.fetch())
            idle()
            expect(page.locator("#query-results")).to_be_visible()
            page.unroute("**/query?*")
            checks.append("a held genuine query survives entry/exit without another request")

            page.locator("#explanation-launcher").click()
            page.locator('[data-explanation-question="handoff_limits"]').click()
            expect(page.locator("#explanation-answer")).not_to_be_empty()
            answer = page.locator("#explanation-answer").text_content()
            before, count = facts(), len(requests)
            enter()
            unchanged(before, count)
            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.locator("#explanation-panel")).to_have_attribute("aria-modal", "true")
            assert page.evaluate("document.getElementById('application-shell').inert")
            expect(page.locator("#explanation-answer")).to_have_text(answer)
            page.keyboard.press("Escape")
            expect(page.locator("#explanation-panel")).to_be_hidden()
            focused()
            assert not page.evaluate("document.getElementById('application-shell').inert")
            # The existing confirmation is deliberately opened to exercise the
            # asynchronous/native top-layer boundary while background is inert.
            page.evaluate("document.getElementById('delete-dialog').showModal()")
            page.keyboard.press("Escape")
            expect(page.locator("#delete-dialog")).to_be_hidden()
            focused()
            leave()
            checks.append("open desktop answer survives map entry and narrow resize; explanation and injected existing delete dialog own their Escape")

            enter()
            page.locator("#explanation-launcher").click()
            page.locator('[data-explanation-question="handoff_limits"]').click()
            expect(page.locator("#explanation-answer")).not_to_be_empty()
            page.locator('[data-explanation-evidence="source"]').click()
            focused(False)
            expect(page.locator("#explanation-panel")).to_be_hidden()
            expect(page.locator("#source-details")).to_have_attribute("open", "")
            assert page.evaluate("document.getElementById('source-details').contains(document.activeElement)")
            assert not page.evaluate("document.getElementById('application-shell').inert")
            checks.append("guided source evidence returns from focused map to its existing detail and clears modal inert")

            if receipt["health"]["mode"] == "full":
                page.set_viewport_size({"width": 1440, "height": 900})
                raw, tags = stress_csv(200)
                mutation("/api/datasets?", lambda: page.locator("#upload-input").set_input_files(
                    {"name": "SYNTHETIC-map-fullscreen-200.csv", "mimeType": "text/csv", "buffer": raw}))
                page.locator("#equipment-filter").select_option("Fixture-Pump")
                page.locator("#tag-filter").select_option(tags[42])
                synthetic_result = query()
                before, count = facts(), len(requests)
                enter()
                page.locator("#map-fit").click()
                geometry("synthetic-200", .85, .65)
                page.locator("#map-zoom-in").click()
                page.locator("#map-pan-down").click()
                page.locator("#map-minimap").click()
                page.locator("#map-focus-selection").click()
                unchanged(before, count)
                leave()
                zip_oracle(raw, synthetic_result, "synthetic-200.zip")
                enter()
                count = len(requests)
                page.locator('[data-map-equipment="Fixture-Pump"][data-map-tag]').filter(has_text=tags[-1]).focus()
                page.keyboard.press("Enter")
                expect(page.locator("#tag-filter")).to_have_value(tags[-1])
                expect(page.locator("#query-results")).to_be_hidden()
                assert len(requests) == count, "Selecting another map item silently queried"
                page.set_viewport_size({"width": 390, "height": 844})
                geometry("synthetic-long-name-390", .9, .5)
                assert page.evaluate("!window.navInjected")
                page.locator("#map-review-link").click()
                focused(False)
                assert page.evaluate("document.getElementById('query-form').contains(document.activeElement)")
                expect(page.locator("#query-results")).to_be_hidden()
                checks.append("labelled synthetic 200-item map fills screen; camera/minimap and independent CSV/ZIP stay connected")

            # New dedicated-view lifecycle under real browser-level Escape.
            if desktop:
                from PIL import ImageGrab
                native = browser.new_context(no_viewport=True, locale="ko-KR", storage_state=context.storage_state())
                screen = native.new_page()
                screen.on("pageerror", lambda e: errors.append(str(e)))
                screen.on("request", lambda r: external.append(r.url) if urlparse(r.url).scheme in ("http", "https")
                          and urlparse(r.url).netloc != urlparse(base).netloc else None)
                cdp = native.new_cdp_session(screen)
                window = cdp.send("Browser.getWindowForTarget")["windowId"]
                try:
                    cdp.send("Browser.setWindowBounds", {"windowId": window, "bounds": {"width": 1440, "height": 1000}})
                    screen.goto(base)
                    expect(screen.locator("#loading")).to_be_hidden(timeout=30000)
                    screen.bring_to_front()
                    screen.locator("#map-fullscreen-toggle").click()
                    screen.wait_for_function("()=>document.fullscreenElement===document.documentElement")
                    screen.wait_for_function("""()=>{const r=document.getElementById('equipment-map').getBoundingClientRect();
                        return r.width/innerWidth>=.85 && r.height/innerHeight>=.65;}""")
                    receipt["geometry"].append(screen.evaluate("""()=>{const r=document.getElementById('equipment-map').getBoundingClientRect();
                        return {label:'native-desktop',width:r.width,height:r.height,vw:innerWidth,vh:innerHeight,
                            widthShare:r.width/innerWidth,heightShare:r.height/innerHeight};}"""))
                    screen.screenshot(path=str(out / "native-map.png"))
                    base_dpr = screen.evaluate("devicePixelRatio")
                    desktop.key("Control_L", True)
                    try:
                        for _ in range(5):
                            desktop.press("plus")
                            screen.wait_for_timeout(60)
                    finally:
                        desktop.key("Control_L", False)
                    screen.wait_for_function(f"()=>devicePixelRatio/{base_dpr}>=1.95")
                    assert round(100 * screen.evaluate("devicePixelRatio") / base_dpr) == 200
                    screen.locator("#map-fullscreen-layer").evaluate("el=>el.scrollTop=el.scrollHeight")
                    assert screen.locator("#map-fullscreen-toggle").evaluate("el=>{const r=el.getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth&&r.bottom<=innerHeight}")
                    # Surface capture at browser zoom can crop/repaint Chromium's
                    # surface. Capture the settled owned display before using it.
                    screen.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                    screen.wait_for_timeout(250)
                    ImageGrab.grab().save(out / "native-map-200-percent-display.png")
                    receipt["zoom_200"] = screen.evaluate("()=>({dpr:devicePixelRatio,inner:[innerWidth,innerHeight],visual:[visualViewport.width,visualViewport.height]})")
                    screen.locator("#map-fullscreen-toggle").click()
                    screen.wait_for_function("()=>!document.fullscreenElement && document.getElementById('map-fullscreen-layer').hidden")
                    desktop.key("Control_L", True)
                    desktop.press("0")
                    desktop.key("Control_L", False)
                    screen.wait_for_function(f"()=>Math.abs(devicePixelRatio-{base_dpr})<0.05")
                    screen.locator("#map-fullscreen-toggle").click()
                    screen.wait_for_function("()=>!!document.fullscreenElement")
                    desktop.press("Escape")
                    screen.wait_for_function("()=>!document.fullscreenElement && !document.getElementById('map-fullscreen-layer').contains(document.getElementById('equipment-map-section'))")
                    expect(screen.locator("#map-fullscreen-toggle")).to_be_focused()
                    screen.locator("#map-fullscreen-toggle").click()
                    screen.wait_for_function("()=>!!document.fullscreenElement")
                    screen.locator("#explanation-launcher").click()
                    screen.locator('[data-explanation-question="handoff_limits"]').click()
                    expect(screen.locator("#explanation-answer")).not_to_be_empty()
                    answer = screen.locator("#explanation-answer").text_content()
                    desktop.press("Escape")
                    screen.wait_for_function("()=>!document.fullscreenElement")
                    expect(screen.locator("#explanation-panel")).to_be_visible()
                    expect(screen.locator("#explanation-answer")).to_have_text(answer)
                    assert screen.evaluate("document.getElementById('explanation-panel').contains(document.activeElement)")
                    receipt["native_desktop"] = "PASS: XTest Escape in owned Xvfb; explicit native window bounds, not an automatic OS-sizing claim"
                    checks.append("native browser Escape exits the dedicated map; an open explanation retains answer and focus")
                finally:
                    native.close()
            else:
                receipt["native_desktop"] = "NOT RUN (use isolated Xvfb --native-desktop)"

            # The dialog opening is a labelled UI-layer injection; confirmation
            # uses the actual existing handler and deletes only this run's data.
            page.evaluate("()=>{document.documentElement.requestFullscreen=()=>new Promise(resolve=>{window.testDeletedEntryResolve=resolve})}")
            page.locator("#map-fullscreen-toggle").click()
            focused()
            expect(page.locator("#map-fullscreen-toggle")).to_be_enabled()
            page.evaluate("document.getElementById('delete-dialog').showModal()")
            with page.expect_response(lambda r: r.request.method == "DELETE" and "/api/datasets/" in r.url) as pending:
                page.locator("#confirm-delete").click()
            assert pending.value.ok, pending.value.text()
            idle()
            focused(False)
            page.evaluate("window.testDeletedEntryResolve()")
            if page.locator("#workspace").is_hidden():
                mutation("/api/datasets/sample", lambda: page.locator("#welcome-sample").click())
            expect(page.locator("#review-fullscreen-toggle")).to_be_enabled()
            assert not page.evaluate("document.getElementById('main').inert || document.getElementById('application-shell').inert")
            checks.append("actual owned-fixture deletion during an injected pending entry cannot strand the map or lock exit after late settlement")
            assert not errors, errors
            assert not external, external
            receipt["status"] = "PASS"
        except Exception as e:
            receipt.update(status="FAIL", failure=f"{type(e).__name__}: {e}")
            receipt["failure_layout"] = page.evaluate("""()=>({focus:document.activeElement.id,
                viewport:[innerWidth,innerHeight],elements:Object.fromEntries(
                ['map-fullscreen-layer','equipment-map-section','equipment-map','map-fullscreen-toggle',
                 'map-selected-item'].map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect();
                  return [id,{x:r.x,y:r.y,width:r.width,height:r.height,scrollTop:e.scrollTop,scrollHeight:e.scrollHeight}]}))})""")
            page.screenshot(path=str(out / "failure.png"), full_page=True)
            raise
        finally:
            failed_before_cleanup = receipt.get("status") == "FAIL"
            cleanup_error = None
            try:
                if created:
                    token = context.request.get(base + "/api/session").json()["csrf_token"]
                    for dataset_id in created:
                        assert context.request.delete(base + "/api/datasets/" + dataset_id,
                                                      headers={"X-Review-CSRF": token}).status in (200, 404)
                receipt["own_fixture_cleanup"] = "PASS" if created else "NO FIXTURES"
            except Exception as e:
                cleanup_error = e
                receipt["own_fixture_cleanup"] = f"FAIL: {e}"
                if not failed_before_cleanup:
                    receipt.update(status="FAIL", failure=f"Cleanup failed: {e}")
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            (out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            browser.close()
            if desktop:
                desktop.close()
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            if cleanup_error and not failed_before_cleanup:
                raise RuntimeError("Owned fixture cleanup failed") from cleanup_error


if __name__ == "__main__":
    main()
