#!/usr/bin/env python3
"""Verify the local equipment-map journey in a fresh Chromium workspace.

Real sample/fixture HTTP, independent CSV/ZIP oracles, and labelled transport fault injection.
No database access, plant data, external requests, or Docker. Removes only datasets it creates.
"""
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

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "src/manufacturing_data_platform/file_review/sample/metropt3-day.csv"


def synthetic_csv(offset=0):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["timestamp", "equipment", "tag", "value", "unit"])
    hostile = '<img src=x onerror="window.mapInjected=1">' + "긴이름" * 20
    for equipment, tags in [("Fixture-Pump", [f"series-{n:02}" for n in range(10)] + [hostile]),
                            ("Fixture-Motor", ["current"])]:
        for index, tag in enumerate(tags):
            for second, value in [(0, 10 + index + offset), (20, 30 + index + offset)]:
                writer.writerow([f"2020-01-01T00:00:{second:02}", equipment, tag, value, "u"])
    return output.getvalue().encode(), hostile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("full", "sample"), default="full")
    parser.add_argument("--output", default=".cache/equipment-map-browser/" +
                        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only a loopback test server is supported.")
    base = args.url.rstrip("/")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    checks, errors, external, created, responses, query_requests = [], [], [], [], [], []
    receipt = {"started_at": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
               "checks": checks, "page_errors": errors, "external_requests": external}
    receipt["source_revision"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    receipt["worktree_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="ko-KR")
        context.add_init_script("""(() => {
          const original = window.fetch.bind(window);
          window.fetch = (input, options = {}) => {
            if (window.__ignoreMapAbort && String(input).includes('/query?')) {
              const copied = {...options}; delete copied.signal; return original(input, copied);
            }
            return original(input, options);
          };
        })();""")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda req: query_requests.append(req.url) if "/query?" in req.url else None)
        page.on("request", lambda req: external.append(req.url) if urlparse(req.url).scheme in ("http", "https")
                and urlparse(req.url).netloc != urlparse(base).netloc else None)
        saved_cookies = None
        nodes = page.locator("#equipment-map [data-map-tag]")
        results = page.locator("#query-results")

        def idle():
            expect(page.locator("#loading")).to_be_hidden(timeout=30000)

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
            return mutation("/api/datasets/sample", lambda: page.locator("#sample-button").click())

        def upload(raw, name="synthetic-map.csv"):
            return mutation("/api/datasets?", lambda: page.locator("#upload-input").set_input_files(
                {"name": name, "mimeType": "text/csv", "buffer": raw}))

        def tags():
            return nodes.evaluate_all("els => els.map(el => el.dataset.mapTag)")

        def graph_visible():
            page.wait_for_function("document.getElementById('map-view-toggle').hidden === (innerWidth > 850)")
            if not page.locator("#equipment-map").is_visible():
                page.locator("#map-view-toggle").click()
            expect(page.locator("#equipment-map")).to_be_visible()

        def select_map(tag, keyboard=False):
            graph_visible()
            button = nodes.nth(tags().index(tag))
            before = len(query_requests)
            button.focus()
            if keyboard:
                page.keyboard.press(keyboard if isinstance(keyboard, str) else "Enter")
            else:
                button.click()
            expect(page.locator("#tag-filter")).to_have_value(tag)
            selected = nodes.nth(tags().index(tag))
            expect(selected).to_have_attribute("aria-pressed", "true")
            if keyboard:
                expect(selected).to_be_focused()
            assert len(query_requests) == before, "Selection eagerly queried instead of using explicit submit"

        def submit(status=200):
            with page.expect_response(lambda r: "/query?" in r.url) as pending:
                page.locator("#query-button").click()
            response = pending.value
            assert response.status == status, response.text()
            idle()
            body = response.json()
            responses.append(body)
            if status == 200:
                return body
            expect(results).to_be_hidden()

        def oracle(raw, result, equipment, tag):
            rows = list(csv.DictReader(io.StringIO(raw.decode())))
            values = [float(row["value"]) for row in rows if row["equipment"] == equipment and row["tag"] == tag]
            assert result["equipment"] == equipment and result["tag"] == tag
            assert result["summary"]["count"] == len(values)
            assert math.isclose(result["summary"]["mean"], statistics.fmean(values), abs_tol=1e-10)
            assert result["summary"]["min"] == min(values) and result["summary"]["max"] == max(values)
            expect(page.locator("#metric-count")).to_have_text(f"{len(values):,}")
            expect(page.locator("#query-selection")).to_contain_text(tag)
            with page.expect_download() as pending:
                page.locator("#export-button").click()
            path = output / f"result-{len(checks)}.zip"
            pending.value.save_as(str(path))
            idle()
            with ZipFile(path) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                exported = archive.read("observations.csv")
                assert manifest["version"] == result["version"]
                assert manifest["source_sha256"] == hashlib.sha256(raw).hexdigest()
                assert manifest["equipment"] == equipment and manifest["tag"] == tag
                assert manifest["filter"] == result["filter"] and manifest["summary"] == result["summary"]
                assert manifest["observations_sha256"] == hashlib.sha256(exported).hexdigest()
                export_rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))
                assert len(export_rows) == len(values)
                assert [float(row["value"]) for row in export_rows] == values
            page.locator("#map-source-link").click()
            expect(page.locator("#source-details")).to_have_attribute("open", "")
            expect(page.locator("#source-metadata")).to_contain_text(result["version"])
            expect(page.locator("#source-metadata")).to_contain_text(hashlib.sha256(raw).hexdigest())
            assert page.evaluate("document.activeElement.closest('#source-details') !== null")

        def cleared():
            expect(results).to_be_hidden()
            assert not nodes.count() or not nodes.first.is_visible(), "Obsolete membership remains usable"

        def refresh():
            page.locator("#map-refresh").click()
            idle()
            expect(nodes.first).to_be_visible()

        def capture(name):
            # Scroll the normal-flow parent, not its sticky child, so the chart stays beside the map.
            page.locator(".review-layout").evaluate("el => el.scrollIntoView({block:'start',behavior:'instant'})")
            expect(page.locator("#toast")).to_be_hidden(timeout=10000)
            page.screenshot(path=str(output / name))

        def usable_buttons():
            graph_visible()
            # Canvas clipping is intentional. The selected node must be readable
            # and in view; other displayed nodes remain reachable by camera/list.
            page.locator("#map-focus-selection").click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            selected = page.locator('#equipment-map [data-map-tag][aria-pressed="true"]')
            expect(selected).to_have_count(1)
            page.wait_for_function("""() => {
              const node = document.querySelector('#equipment-map [data-map-tag][aria-pressed="true"]');
              if (!node) return false;
              const box = node.getBoundingClientRect();
              const root = document.getElementById('equipment-map').getBoundingClientRect();
              return box.width >= 24 && box.height >= 24 && box.x >= root.x - 1 && box.y >= root.y - 1
                && box.right <= root.right + 1 && box.bottom <= root.bottom + 1;
            }""", timeout=2000)
            boxes = page.locator('#map-world [data-map-tag], #map-world [data-map-toggle]').evaluate_all(
                "els=>els.map(el=>{const r=el.getBoundingClientRect();return [r.x,r.y,r.right,r.bottom]})")
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    assert not (a[0]<b[2]-.5 and b[0]<a[2]-.5 and a[1]<b[3]-.5 and b[1]<a[3]-.5), "Overlapping graph nodes"

        try:
            page.goto(base)
            idle()
            health = context.request.get(base + "/healthz").json()
            assert health["mode"] == args.mode
            receipt.update(browser=browser.version, health=health)
            assets = {}
            for endpoint, filename in [("/", "index.html"), ("/app.js", "app.js"), ("/styles.css", "styles.css"), ("/map-canvas.js", "map-canvas.js")]:
                served = context.request.get(base + endpoint)
                assert served.ok
                content = (ROOT / "src/manufacturing_data_platform/file_review/static" / filename).read_bytes()
                assert served.body() == content, f"Served {filename} differs from the reviewed checkout"
                assets[filename] = hashlib.sha256(content).hexdigest()
            receipt["served_assets_sha256"] = assets
            assert not nodes.count() or not nodes.first.is_visible()
            first = sample()
            sample_bytes = SAMPLE.read_bytes()
            assert set(tags()) == {"Oil_temperature", "Motor_current", "TP2"}
            expect(page.locator("#workspace")).to_contain_text("판단 근거 없음")
            expect(page.locator("#equipment-map-section")).to_contain_text("2020-02-01")
            select_map("Oil_temperature", keyboard=True)
            result = submit()
            assert result["version"] == first["current"]["version"]
            oracle(sample_bytes, result, "MetroPT-3 APU", "Oil_temperature")
            checks.append("real sample membership; independent CSV count/mean/extrema/source hash; matching ZIP and source focus")
            capture("01-map-desktop.png")

            select_map("Motor_current", keyboard=True)
            expect(results).to_be_hidden()
            expect(page.locator("#map-selection-status")).to_contain_text("조회")
            result = submit()
            oracle(sample_bytes, result, "MetroPT-3 APU", "Motor_current")
            page.locator("#tag-filter").select_option("Oil_temperature")
            expect(results).to_be_hidden()
            expect(nodes.nth(tags().index("Oil_temperature"))).to_have_attribute("aria-pressed", "true")
            result = submit()
            checks.append("keyboard map/native list share selection; old detail/export cleared until explicit query")

            page.locator("#sample-exercise summary").click()
            failed = mutation("/delivery-check", lambda: page.locator("#delivery-button").click())
            assert failed["current"]["version"] == first["current"]["version"]
            expect(page.locator("#attempt-banner")).to_contain_text("전달")
            result = submit()
            assert result["previous_result"] and result["latest_status"] == "incomplete"
            oracle(sample_bytes, result, "MetroPT-3 APU", "Oil_temperature")
            capture("02-map-retained-result.png")
            recovered = mutation("/retry", lambda: page.locator("#recover-button").click())
            assert recovered["current"]["version"] == first["current"]["version"]
            checks.append("real delivery exercise/last-good membership and ZIP; recovery preserves immutable version")

            page.locator("#start-filter").fill("2021-01-01T00:00")
            empty = submit()
            assert empty["summary"]["count"] == 0 and empty["summary"]["mean"] is None
            expect(page.locator("#metric-mean")).to_have_text("—")
            page.locator("#reset-range").click()
            idle()
            checks.append("empty selected range leaves membership intact but does not recall old average")

            for width in (390, 320):
                page.set_viewport_size({"width": width, "height": 844})
                graph_visible()
                select_map("TP2", keyboard="Space" if width == 320 else True)
                submit()
                usable_buttons()
                capture(f"03-map-mobile-{width}.png")
                page.locator("#explanation-launcher").click()
                expect(page.locator("#explanation-panel")).to_have_attribute("aria-modal", "true")
                page.locator('[data-explanation-question="handoff_limits"]').click()
                expect(page.locator("#explanation-answer")).not_to_be_empty()
                page.keyboard.press("Escape")
                expect(page.locator("#explanation-launcher")).to_be_focused()
            checks.append("390/320px map/list, keyboard focus, non-overlapping buttons, no page overflow and explanation modal")
            page.set_viewport_size({"width": 1440, "height": 1100})
            graph_visible()

            page.route("**/query?*", lambda route: route.fulfill(status=503, content_type="application/json",
                       body=json.dumps({"error": {"code": "UNAVAILABLE", "message": "Fixture transient failure"}})))
            submit(503)
            expect(nodes.first).to_be_visible()
            page.unroute("**/query?*")
            submit()
            checks.append("injected HTTP 503 clears failed-query stats and permits explicit retry without invented data")

            # Server-side second-tab mutation: same immutable version but a new latest-attempt identity.
            route = base + "/api/datasets/" + first["id"]
            assert context.request.post(route + "/retry", headers={"X-Review-CSRF": csrf()}).ok
            submit()
            cleared()
            refresh()
            checks.append("real other-tab retry detected from query latest-attempt mismatch; explicit refresh recovers")

            # Delay a genuine response while an adversarial event changes the draft selection.
            old = submit()
            held = []
            page.evaluate("window.__ignoreMapAbort = true")
            page.route("**/query?*", lambda request: held.append(request))
            page.locator("#query-button").click()
            expect(page.locator("#loading")).to_be_visible()
            assert len(held) == 1
            next_tag = "Oil_temperature" if old["tag"] != "Oil_temperature" else "TP2"
            page.locator("#tag-filter").evaluate("(el, tag) => {el.value=tag; el.dispatchEvent(new Event('change',{bubbles:true}));}", next_tag)
            held.pop().fulfill(status=200, content_type="application/json", body=json.dumps(old))
            idle()
            expect(results).to_be_hidden()
            expect(page.locator("#tag-filter")).to_have_value(next_tag)
            page.unroute("**/query?*")
            page.evaluate("window.__ignoreMapAbort = false")
            submit()
            checks.append("injected late genuine query response rejected after dispatched selection change, even without transport abort")

            if args.mode == "full":
                raw, hostile = synthetic_csv()
                fixture = upload(raw)
                assert set(page.locator("#equipment-filter option").evaluate_all("els => els.map(el => el.value)")) == {"Fixture-Motor", "Fixture-Pump"}
                page.locator("#equipment-filter").select_option("Fixture-Pump")
                expect(results).to_be_hidden()
                assert nodes.evaluate_all("els=>els.filter(el=>el.dataset.mapEquipment==='Fixture-Pump').length") == 11
                assert page.locator("#tag-filter option").count() == 11
                expect(page.locator("#map-overflow")).to_be_visible()
                page.locator("#tag-filter").select_option("series-09")
                assert "series-09" in tags() and 11 <= nodes.count() <= 12
                result = submit()
                oracle(raw, result, "Fixture-Pump", "series-09")
                page.locator("#tag-filter").select_option(hostile)
                assert hostile in tags() and 11 <= nodes.count() <= 12
                submit()
                assert page.locator("#equipment-map img").count() == 0
                assert page.evaluate("window.mapInjected || 0") == 0
                for width in (1440, 1280, 1024, 601, 600, 390, 320):
                    page.set_viewport_size({"width": width, "height": 844})
                    graph_visible()
                    usable_buttons()
                capture("04-synthetic-long-labels-mobile.png")
                page.set_viewport_size({"width": 1440, "height": 1100})
                checks.append("synthetic two-equipment/11-item input: native full list and expanded 11-item group; selected-position camera and hostile long labels inert")

                other, _ = synthetic_csv(offset=100)
                second = upload(other, "same-name-different-file.csv")
                assert second["id"] != fixture["id"] and second["current"]["version"] != fixture["current"]["version"]
                page.locator("#equipment-filter").select_option("Fixture-Pump")
                page.locator("#tag-filter").select_option("series-09")
                result = submit()
                oracle(other, result, "Fixture-Pump", "series-09")
                refused = mutation("/replace?", lambda: page.locator("#replace-input").set_input_files(
                    {"name": "refused.csv", "mimeType": "text/csv", "buffer": b"not,a,valid,file\n1,2,3,4\n"}))
                assert refused["current"]["version"] == second["current"]["version"]
                result = submit()
                oracle(other, result, "Fixture-Pump", "series-09")
                checks.append("real same-name separate datasets never merge; refused replacement keeps selected file's original data and ZIP")
                bad = upload(b"not,a,valid,file\n1,2,3,4\n", "no-current.csv")
                assert bad["current"] is None
                cleared()
                expect(page.locator("#no-current")).to_be_visible()
                checks.append("real rejected first input has no fabricated equipment map")

            current = sample()
            graph_visible()
            # UI refusal boundary injection; backend tamper/expiry semantics have independent API tests.
            page.route("**/query?*", lambda request: request.fulfill(status=409, content_type="application/json",
                       body=json.dumps({"error": {"code": "INTEGRITY", "message": "Fixture integrity refusal"}})))
            submit(409)
            cleared()
            page.unroute("**/query?*")
            refresh()
            checks.append("injected integrity refusal clears map/statistics; no remembered-content fallback")
            result = submit()
            stranger = browser.new_context()
            stranger.request.get(base + "/api/session")
            assert stranger.request.get(base + "/api/datasets/" + current["id"] + "/query").status == 404
            stranger.close()
            assert context.request.delete(base + "/api/datasets/" + current["id"], headers={"X-Review-CSRF": csrf()}).ok
            with page.expect_response(lambda r: "/export?" in r.url) as pending:
                page.locator("#export-button").click()
            assert pending.value.status == 404
            idle()
            cleared()
            checks.append("real cross-workspace query denial and other-tab deletion observed on export clear obsolete map")
            sample()
            saved_cookies = context.cookies()
            context.clear_cookies()
            submit(401)
            cleared()
            checks.append("real missing workspace cookie refuses query and clears obsolete map/result")
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
                    response = context.request.delete(base + "/api/datasets/" + dataset_id,
                                                      headers={"X-Review-CSRF": token})
                    assert response.status in (200, 404), response.text()
                receipt["fixture_cleanup"] = "PASS"
            except Exception as error:
                receipt["fixture_cleanup"] = f"FAIL: {type(error).__name__}: {error}"
                receipt["status"] = "FAIL"
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            (output / "responses.json").write_text(json.dumps(responses, ensure_ascii=False, indent=2) + "\n")
            browser.close()
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if receipt.get("status") != "PASS":
        raise RuntimeError(receipt.get("failure") or receipt.get("fixture_cleanup"))


if __name__ == "__main__":
    main()
