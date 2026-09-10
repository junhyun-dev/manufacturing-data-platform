#!/usr/bin/env python3
"""Check file-local graph exploration using real local HTTP and browser evidence.

All uploads are labelled synthetic fixtures in fresh browser workspaces. Camera
checks observe DOM and requests, never the controller's internal model. Server
failure injections are reported separately from real HTTP outcomes.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from verify_review_navigation_browser import stress_csv

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/manufacturing_data_platform/file_review/static"
SAMPLE = ROOT / "src/manufacturing_data_platform/file_review/sample/metropt3-day.csv"


def many_groups(count=25):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["timestamp", "equipment", "tag", "value", "unit"])
    for group in range(count):
        for second, value in [(0, group), (20, group + 10)]:
            writer.writerow([f"2020-01-01T00:00:{second:02}", f"Group-{group:02}", "same-tag", value, "u"])
    return stream.getvalue().encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("full", "sample"), default="full")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only an explicitly owned loopback fixture server is supported")
    base, output = args.url.rstrip("/"), Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    checks, errors, requests, external, created, measurements = [], [], [], [], [], []
    receipt = {"started_at": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
               "checks": checks, "page_errors": errors, "external_requests": external,
               "synthetic_measurements": measurements,
               "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT))}
    saved_cookies = None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="ko-KR", reduced_motion="reduce")
        page = context.new_page()
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("request", lambda req: requests.append(req.url) if "/api/" in req.url else None)
        page.on("request", lambda req: external.append(req.url) if urlparse(req.url).scheme in ("http", "https")
                and urlparse(req.url).netloc != urlparse(base).netloc else None)
        nodes = page.locator("#map-world [data-map-tag]")
        groups = page.locator("#map-world [data-map-toggle]")

        def idle():
            expect(page.locator("#loading")).to_be_hidden(timeout=30000)

        def frame():
            page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

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
            button = "#welcome-sample" if page.locator("#welcome").is_visible() else "#sample-button"
            return mutation("/api/datasets/sample", lambda: page.locator(button).click())

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

        def facts():
            return page.evaluate("""() => ({
              draft: ['equipment-filter','tag-filter','start-filter','end-filter'].map(id=>document.getElementById(id).value),
              result: ['query-selection','metric-count','metric-mean','metric-min','metric-max','result-version','map-selected-item'].map(id=>document.getElementById(id).textContent),
              shown: !document.getElementById('query-results').hidden,
              exportDisabled: document.getElementById('export-button').disabled,
              source: document.getElementById('source-metadata').textContent,
              explanation: document.getElementById('explanation-answer').textContent
            })""")

        def unchanged(before, calls):
            frame()
            assert facts() == before, "Camera/grouping changed selected or submitted review facts"
            assert len(requests) == calls, "Camera/grouping made an API request"

        def by_attr(locator, name, value):
            values = locator.evaluate_all("(els,name)=>els.map(el=>el.getAttribute(name))", name)
            assert value in values, (name, value, values)
            return locator.nth(values.index(value))

        def activate(locator):
            locator.focus()
            page.keyboard.press("Enter")
            frame()

        def toggle(equipment, expanded):
            button = by_attr(groups, "data-map-toggle", equipment)
            if button.get_attribute("aria-expanded") != str(expanded).lower():
                activate(button)
            expect(by_attr(groups, "data-map-toggle", equipment)).to_have_attribute("aria-expanded", str(expanded).lower())

        def single_group(equipment):
            names = groups.evaluate_all("els=>els.map(el=>el.dataset.mapToggle)")
            for name in names:
                if name != equipment:
                    toggle(name, False)
            toggle(equipment, True)

        def choose(equipment, tag):
            pairs = nodes.evaluate_all("els=>els.map(el=>[el.dataset.mapEquipment,el.dataset.mapTag])")
            target = nodes.nth(pairs.index([equipment, tag]))
            activate(target)
            expect(page.locator("#equipment-filter")).to_have_value(equipment)
            expect(page.locator("#tag-filter")).to_have_value(tag)

        def camera():
            return page.locator("#map-world").evaluate("el=>getComputedStyle(el).transform")

        def visible_selection():
            selected = page.locator('#map-world [data-map-tag][aria-pressed="true"]')
            expect(selected).to_have_count(1)
            # The controller schedules a camera update and ResizeObserver can run
            # after a viewport change. Read both boxes in one browser frame, and
            # wait for the actual promised geometry rather than mixed old/new boxes.
            page.wait_for_function("""() => {
              const node = document.querySelector('#map-world [data-map-tag][aria-pressed="true"]');
              if (!node) return false;
              const box = node.getBoundingClientRect();
              const root = document.getElementById('equipment-map').getBoundingClientRect();
              return box.width >= 24 && box.height >= 24 && box.x >= root.x - 2 && box.y >= root.y - 2
                && box.right <= root.right + 2 && box.bottom <= root.bottom + 2;
            }""", timeout=2000)

        def boxes():
            # Overlap is independent of camera scale/translation. Exclude controls
            # that intentionally sit inside a group container.
            result = nodes.evaluate_all("els=>els.map(el=>{const r=el.getBoundingClientRect();return [r.x,r.y,r.right,r.bottom]})")
            for i, a in enumerate(result):
                for b in result[i + 1:]:
                    assert not (a[0] < b[2] - .5 and b[0] < a[2] - .5 and a[1] < b[3] - .5 and b[1] < a[3] - .5), "Measurement boxes overlap"
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "World overflows the document"

        def zip_oracle(raw, result):
            rows = [row for row in csv.DictReader(io.StringIO(raw.decode()))
                    if row["equipment"] == result["equipment"] and row["tag"] == result["tag"]]
            values = [float(row["value"]) for row in rows]
            assert result["summary"]["count"] == len(values)
            assert math.isclose(result["summary"]["mean"], statistics.fmean(values), abs_tol=1e-10)
            assert result["summary"]["min"] == min(values) and result["summary"]["max"] == max(values)
            with page.expect_download() as download:
                page.locator("#export-button").click()
            path = output / f"evidence-{len(list(output.glob('evidence-*.zip')))}.zip"
            download.value.save_as(str(path))
            idle()
            with ZipFile(path) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                exported = archive.read("observations.csv")
            for key in ("version", "equipment", "tag", "filter", "summary"):
                assert manifest[key] == result[key]
            assert manifest["source_sha256"] == hashlib.sha256(raw).hexdigest()
            assert manifest["observations_sha256"] == hashlib.sha256(exported).hexdigest()
            assert [float(row["value"]) for row in csv.DictReader(io.StringIO(exported.decode("utf-8-sig")))] == values
            return manifest

        def screenshot(name):
            page.locator(".review-layout").evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
            page.screenshot(path=str(output / name))

        try:
            page.goto(base)
            idle()
            receipt["browser"] = browser.version
            receipt["health"] = context.request.get(base + "/healthz").json()
            assert receipt["health"]["mode"] == args.mode
            assets = {}
            for filename in ("index.html", "app.js", "map-canvas.js", "styles.css"):
                response = context.request.get(base + ("/" if filename == "index.html" else "/" + filename))
                assert response.ok and response.body() == (STATIC / filename).read_bytes(), filename
                assets[filename] = hashlib.sha256(response.body()).hexdigest()
            receipt["served_assets_sha256"] = assets
            first = sample()
            expect(nodes).to_have_count(3)
            expect(groups).to_have_count(1)
            choose("MetroPT-3 APU", "Oil_temperature")
            result = query()
            receipt["sample_zip"] = zip_oracle(SAMPLE.read_bytes(), result)
            before, calls = facts(), len(requests)
            for control in ("map-zoom-out", "map-zoom-in", "map-pan-right", "map-pan-down", "map-fit", "map-focus-selection"):
                page.locator("#" + control).click()
                unchanged(before, calls)
            visible_selection()
            toggle("MetroPT-3 APU", False)
            expect(nodes).to_have_count(0)
            unchanged(before, calls)
            page.locator("#map-focus-selection").click()
            expect(nodes).to_have_count(3)
            visible_selection()
            unchanged(before, calls)
            checks.append("real sample: grouping/camera preserve query; hidden selection revealed; independent source/count/aggregates/ZIP")
            screenshot("01-canvas-sample-desktop.png")

            # Pan starts on background in explicit mode, then cancel must end it.
            page.locator("#map-pan-toggle").click()
            root = page.locator("#equipment-map").bounding_box()
            origin = camera()
            x, y = root["x"] + 12, root["y"] + 12
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 65, y + 45, steps=5)
            page.mouse.up()
            frame()
            assert camera() != origin, "Background drag did not move camera"
            unchanged(before, calls)
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 30, y + 20, steps=3)
            page.locator("#equipment-map").focus()
            page.keyboard.press("Escape")
            expect(page.locator("#equipment-map")).not_to_have_class(re.compile(r".*map-panning.*"))
            frame()
            stopped = camera()
            page.mouse.move(x + 100, y + 90)
            frame()
            assert camera() == stopped, "Esc left an active drag moving the camera"
            page.mouse.up()
            expect(page.locator("#map-pan-toggle")).to_have_attribute("aria-pressed", "false")
            page.locator("#map-pan-toggle").click()
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 20, y + 20, steps=2)
            page.locator("#equipment-map").dispatch_event("pointercancel", {"pointerId": 1})
            expect(page.locator("#equipment-map")).not_to_have_class(re.compile(r".*map-panning.*"))
            frame()
            stopped = camera()
            page.mouse.move(x + 80, y + 80)
            frame()
            assert camera() == stopped, "pointercancel left an active drag"
            page.mouse.up()
            page.locator("#map-pan-toggle").click()
            mini = page.locator("#map-minimap")
            bounds = mini.bounding_box()
            assert bounds and bounds["width"] > 0
            origin = camera()
            mini.click(position={"x": bounds["width"] * .15, "y": bounds["height"] * .2})
            frame()
            assert camera() != origin, "Minimap click did not move camera"
            # Click the minimap at a node's actual DOM position. Its corresponding
            # full-size point must move to the viewport center, including SVG padding.
            target = nodes.first
            point = target.evaluate("el=>({x:el.offsetLeft+el.offsetWidth/2,y:el.offsetTop+el.offsetHeight/2})")
            mini_svg = page.locator("#map-minimap svg")
            svg_box = mini_svg.bounding_box()
            view_box = mini_svg.evaluate("el=>({w:el.viewBox.baseVal.width,h:el.viewBox.baseVal.height})")
            mini.evaluate("el=>el.addEventListener('click',e=>{window.canvasTestClick={x:e.clientX,y:e.clientY}}, {once:true,capture:true})")
            page.mouse.click(svg_box["x"] + point["x"] / view_box["w"] * svg_box["width"],
                             svg_box["y"] + point["y"] / view_box["h"] * svg_box["height"])
            frame()
            delta = target.evaluate("""el=>{
              const a=el.getBoundingClientRect(),v=document.getElementById('equipment-map').getBoundingClientRect();
              return {x:a.x+a.width/2-v.x-v.width/2,y:a.y+a.height/2-v.y-v.height/2,
                camera:getComputedStyle(document.getElementById('map-world')).transform,
                scroll:[document.getElementById('equipment-map').scrollLeft,document.getElementById('equipment-map').scrollTop]};
            }""")
            # MouseEvent client coordinates can be rounded to whole CSS pixels.
            # Compare against the actually delivered click, not a fractional
            # ideal position that the browser never sent to the product.
            click = page.evaluate("window.canvasTestClick")
            scale = mini_svg.evaluate("()=>new DOMMatrixReadOnly(getComputedStyle(document.getElementById('map-world')).transform).a")
            expected_x = (point["x"] - (click["x"] - svg_box["x"]) / svg_box["width"] * view_box["w"]) * scale
            expected_y = (point["y"] - (click["y"] - svg_box["y"]) / svg_box["height"] * view_box["h"]) * scale
            assert abs(delta["x"] - expected_x) < 1 and abs(delta["y"] - expected_y) < 1, (delta, click, expected_x, expected_y)
            page.locator("#map-focus-selection").click()
            visible_selection()
            unchanged(before, calls)
            checks.append("real pointer drag/cancel, Escape move-mode exit, minimap click and click-only camera controls")

            held = []
            page.route("**/query?*", lambda route: held.append(route))
            page.locator("#query-button").click()
            expect(page.locator("#loading")).to_be_visible()
            assert len(held) == 1
            loading_facts, calls = facts(), len(requests)
            toggle("MetroPT-3 APU", False)
            page.locator("#map-zoom-out").click()
            page.locator("#map-focus-selection").click()
            page.locator("#tag-search").fill("Oil")
            unchanged(loading_facts, calls)
            route = held.pop()
            response = route.fetch()
            route.fulfill(response=response)
            idle()
            expect(page.locator("#query-results")).to_be_visible()
            page.unroute("**/query?*")
            checks.append("real held query survives group/camera/search operations without another query")

            for width, height in ((390, 844), (320, 844), (844, 390), (1440, 1100)):
                page.set_viewport_size({"width": width, "height": height})
                if page.locator("#equipment-map-body").is_hidden():
                    page.locator("#map-view-toggle").click()
                before, calls = facts(), len(requests)
                activate(page.locator("#map-focus-selection"))
                visible_selection()
                if width == 320:
                    for _ in range(8):
                        activate(page.locator("#map-zoom-in"))
                    activate(page.locator("#map-focus-selection"))
                    visible_selection()
                boxes()
                for control in ("map-zoom-in", "map-pan-left", "map-fit"):
                    activate(page.locator("#" + control))
                unchanged(before, calls)
                screenshot(f"02-canvas-{width}x{height}.png")
                page.locator("#map-source-link").click()
                expect(page.locator("#source-details")).to_have_attribute("open", "")
                assert page.evaluate("document.getElementById('source-details').contains(document.activeElement)")
            checks.append("1440/390/320 and landscape: keyboard/click controls, selected focus, source focus and no document overflow")

            if args.mode == "full":
                for count in (8, 11, 50, 200, 205):
                    raw, tags = stress_csv(count)
                    started = time.perf_counter()
                    fixture = upload(raw, f"synthetic-canvas-{count}.csv")
                    page.locator("#equipment-filter").select_option("Fixture-Pump")
                    single_group("Fixture-Pump")
                    expect(nodes).to_have_count(min(200, count))
                    boxes()
                    layout_seconds = time.perf_counter() - started
                    before, calls = facts(), len(requests)
                    page.locator("#map-fit").click()
                    for _ in range(3):
                        page.locator("#map-zoom-in").click()
                    page.locator("#map-pan-right").click()
                    unchanged(before, calls)
                    if count > 200:
                        all_seen = set(nodes.evaluate_all("els=>els.map(el=>el.dataset.mapTag)"))
                        next_button = by_attr(page.locator("[data-map-items-next]"), "data-map-items-next", "Fixture-Pump")
                        activate(next_button)
                        all_seen.update(nodes.evaluate_all("els=>els.map(el=>el.dataset.mapTag)"))
                        assert all_seen == set(tags), "Item pages lost or duplicated semantic items"
                        unchanged(before, calls)
                    # Search outside rendered page/position reveals the exact item.
                    page.locator("#tag-search").fill(tags[-1])
                    found = page.locator("#tag-search-results [data-search-tag]")
                    expect(found).to_have_count(1)
                    activate(found)
                    expect(page.locator("#tag-filter")).to_have_value(tags[-1])
                    expect(page.locator("#tag-search")).to_have_value(tags[-1])
                    page.locator("#map-focus-selection").click()
                    visible_selection()
                    assert not page.evaluate("Boolean(window.navInjected)")
                    result = query()
                    zip_oracle(raw, result)
                    before, calls = facts(), len(requests)
                    toggle("Fixture-Other", True)
                    assert nodes.count() <= 200
                    unchanged(before, calls)
                    boxes()
                    # Same string belongs to a different equipment; selection must change both pins.
                    choose("Fixture-Other", tags[0])
                    expect(page.locator("#query-results")).to_be_hidden()
                    other = query()
                    assert other["summary"]["mean"] == 1500
                    zip_oracle(raw, other)
                    page.locator("#equipment-filter").select_option("Fixture-Pump")
                    single_group("Fixture-Pump")
                    page.locator("#map-fit").click()
                    screenshot(f"03-synthetic-{count}-overview.png")
                    measurements.append({"items": count, "upload_to_layout_seconds": round(layout_seconds, 3),
                                         "rendered_measurements": nodes.count(), "kind": "synthetic local browser timing; not SLA"})
                    token = context.request.get(base + "/api/session").json()["csrf_token"]
                    assert context.request.delete(base + "/api/datasets/" + fixture["id"], headers={"X-Review-CSRF": token}).ok
                    created.remove(fixture["id"])
                checks.append("8/11/50/200/205 real synthetic uploads: geometry/budget, full item reachability, inert 128-char labels, cross-group selection and ZIP")

                raw = many_groups()
                fixture = upload(raw, "synthetic-25-equipment-groups.csv")
                expect(groups).to_have_count(20)
                seen = set(groups.evaluate_all("els=>els.map(el=>el.dataset.mapToggle)"))
                before, calls = facts(), len(requests)
                page.locator("#map-groups-next").click()
                seen.update(groups.evaluate_all("els=>els.map(el=>el.dataset.mapToggle)"))
                assert seen == {f"Group-{i:02}" for i in range(25)}
                unchanged(before, calls)
                toggle("Group-24", True)
                choose("Group-24", "same-tag")
                result = query()
                assert math.isclose(result["summary"]["mean"], 29, abs_tol=1e-10), result
                zip_oracle(raw, result)
                before, calls = facts(), len(requests)
                page.locator("#map-groups-prev").click()
                unchanged(before, calls)
                page.locator("#map-focus-selection").click()
                visible_selection()
                unchanged(before, calls)
                checks.append("25-group paging is view-only; identical item names stay group-scoped; selected-position reveals another page")

                raw = (b"timestamp,equipment,tag,value,unit\n"
                       b"2020-01-01T00:00:00,group,z,4,u\n"
                       b"2020-01-01T00:00:00,z,probe,90,u\n")
                upload(raw, "synthetic-group-key-collision.csv")
                choose("group", "z")
                page.locator("#map-focus-selection").click()
                frame()
                selected = page.locator('#map-world [data-map-tag][aria-pressed="true"]')
                actual, viewport = selected.bounding_box(), page.locator("#equipment-map").bounding_box()
                assert abs(actual["x"] + actual["width"] / 2 - viewport["x"] - viewport["width"] / 2) < 3
                assert abs(actual["y"] + actual["height"] / 2 - viewport["y"] - viewport["height"] / 2) < 3
                result = query()
                assert result["summary"]["mean"] == 4
                zip_oracle(raw, result)
                checks.append("adversarial equipment/tag strings cannot collide with internal group location keys")

            # Use a fresh sample after synthetic stress to check reset/last-good semantics.
            latest_sample = sample()
            choose("MetroPT-3 APU", "Oil_temperature")
            result = query()
            page.locator("#sample-exercise summary").click()
            refused = mutation("/delivery-check", lambda: page.locator("#delivery-button").click())
            assert refused["current"]["version"] == latest_sample["current"]["version"]
            expect(nodes).to_have_count(3)
            result = query()
            assert result["previous_result"]
            zip_oracle(SAMPLE.read_bytes(), result)
            recovered = mutation("/retry", lambda: page.locator("#recover-button").click())
            assert recovered["current"]["version"] == refused["current"]["version"]
            checks.append("real sample delivery refusal/recovery resets graph context and preserves last-good version/ZIP")

            for status, code in ((503, "UNAVAILABLE"), (409, "INTEGRITY")):
                page.route("**/query?*", lambda route: route.fulfill(
                    status=status, content_type="application/json", body=json.dumps({"error": {"code": code, "message": "Synthetic refusal"}})))
                query(status)
                expect(page.locator("#query-results")).to_be_hidden()
                if status == 503:
                    expect(nodes).to_have_count(3)
                else:
                    expect(nodes).to_have_count(0)
                page.unroute("**/query?*")
            page.locator("#map-refresh").click()
            idle()
            expect(nodes).to_have_count(3)
            saved_cookies = context.cookies()
            context.clear_cookies()
            query(401)
            expect(nodes).to_have_count(0)
            context.add_cookies(saved_cookies)
            saved_cookies = None
            checks.append("labelled transient/integrity response injections and real missing-workspace HTTP refusal cannot revive stale graph/results")
            assert not errors, errors
            assert not external, external
            receipt["status"] = "PASS"
        except Exception as error:
            receipt.update(status="FAIL", failure=f"{type(error).__name__}: {error}")
            try:
                page.screenshot(path=str(output / "failure.png"), full_page=True)
            except Exception:
                pass
            raise
        finally:
            try:
                if saved_cookies:
                    context.add_cookies(saved_cookies)
                token = context.request.get(base + "/api/session").json()["csrf_token"]
                for dataset_id in created:
                    response = context.request.delete(base + "/api/datasets/" + dataset_id, headers={"X-Review-CSRF": token})
                    assert response.status in (200, 404), response.text()
                receipt["fixture_cleanup"] = "PASS"
            except Exception as error:
                receipt.update(status="FAIL", fixture_cleanup=f"FAIL: {error}")
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            browser.close()
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt.get("status") != "PASS":
        raise RuntimeError(receipt.get("failure") or receipt.get("fixture_cleanup"))


if __name__ == "__main__":
    main()
