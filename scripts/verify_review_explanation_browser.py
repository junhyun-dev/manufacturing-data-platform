#!/usr/bin/env python3
"""Exercise guided explanations in Chromium against a loopback server.

Uses a fresh browser workspace and removes only its own datasets. Install browser
extras separately; the service runtime does not depend on Playwright.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
RAW = ("timestamp,equipment,tag,value,unit\n"
       "2020-01-01T00:00:00,Pump,pressure,10,bar\n"
       "2020-01-01T00:02:00,Pump,pressure,20,bar\n").encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("full", "sample"), default="full")
    parser.add_argument("--output", default=".cache/review-explanation-browser/" +
                        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only a loopback test server is supported.")
    base = args.url.rstrip("/")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    checks, errors, external, created, answers = [], [], [], [], []
    receipt = {"mode": args.mode, "started_at": datetime.now(timezone.utc).isoformat(),
               "checks": checks, "page_errors": errors, "external_requests": external}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="ko-KR")
        # Fault injection: transport abort is deliberately ineffective for explanations.
        # The application's request/context generation must still reject late results.
        context.add_init_script("""(() => {
          const original = window.fetch.bind(window);
          window.fetch = (input, options = {}) => {
            if (window.__ignoreExplanationAbort && String(input).includes('/explanation?')) {
              const copied = {...options}; delete copied.signal; return original(input, copied);
            }
            return original(input, options);
          };
        })();""")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda req: external.append(req.url)
                if urlparse(req.url).scheme in ("http", "https") and
                urlparse(req.url).netloc != urlparse(base).netloc else None)
        panel = page.locator("#explanation-panel")
        answer = page.locator("#explanation-answer")
        launcher = page.locator("#explanation-launcher")
        held = []

        def idle():
            expect(page.locator("#loading")).to_be_hidden(timeout=30000)

        def close():
            if panel.is_visible():
                page.locator("#explanation-close").click()
                expect(panel).to_be_hidden()

        def open_panel():
            if not panel.is_visible():
                launcher.click()
                expect(panel).to_be_visible()

        def ask(question="previous_result", status=200):
            open_panel()
            with page.expect_response(lambda response: "/explanation?" in response.url) as pending:
                page.locator(f'[data-explanation-question="{question}"]').click()
            response = pending.value
            assert response.status == status, response.text()
            body = response.json()
            if status == 200:
                expect(answer).to_be_visible()
                expect(answer).to_contain_text(body["title"])
                assert body["mode"] == "guided" and body["question"] == question
                assert "rows" not in body and "points" not in body
                answers.append(body)
            return body

        def mutation(fragment, action):
            with page.expect_response(lambda response: fragment in response.url and
                                      response.request.method == "POST") as pending:
                action()
            response = pending.value
            assert response.ok, response.text()
            dataset = response.json()["dataset"]
            if dataset["id"] not in created:
                created.append(dataset["id"])
            idle()
            return dataset

        def export_result(expected):
            close()
            with page.expect_download() as pending:
                page.locator("#export-button").click()
            archive_path = output / ("result-" + str(len(checks)) + ".zip")
            pending.value.save_as(str(archive_path))
            idle()
            with ZipFile(archive_path) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                assert manifest["version"] == expected["context"]["version"]
                assert manifest["source_sha256"] == expected["context"]["source_sha256"]
                assert manifest["filter"] == expected["context"]["filter"]
                assert manifest["summary"] == expected["summary"]
                assert manifest["observations_sha256"] == hashlib.sha256(archive.read("observations.csv")).hexdigest()

        def delay():
            open_panel()
            page.evaluate("window.__ignoreExplanationAbort = true")
            page.route("**/explanation?*", lambda route: held.append(route))
            page.locator('[data-explanation-question="previous_result"]').click()
            expect(page.locator("#explanation-cancel")).to_be_visible()
            assert len(held) == 1

        def finish_late(body):
            stale = dict(body, title="LATE_RESPONSE_MUST_NOT_RENDER",
                         paragraphs=["This response belongs to an invalidated request."])
            held.pop().fulfill(status=200, content_type="application/json", body=json.dumps(stale))
            page.unroute("**/explanation?*")
            page.wait_for_timeout(100)
            assert "LATE_RESPONSE_MUST_NOT_RENDER" not in answer.text_content()
            page.evaluate("window.__ignoreExplanationAbort = false")

        try:
            page.goto(base)
            idle()
            health = context.request.get(base + "/healthz").json()
            assert health["mode"] == args.mode
            receipt.update(browser=browser.version, health=health)
            open_panel()
            for question in ("previous_result", "handoff_limits", "gap_limits"):
                expect(page.locator(f'[data-explanation-question="{question}"]')).to_be_disabled()
            checks.append("no result: instructions instead of fabricated explanation")
            close()

            if args.mode == "full":
                first = mutation("/api/datasets?", lambda: page.locator("#upload-input").set_input_files(
                    {"name": "pressure.csv", "mimeType": "text/csv", "buffer": RAW}))
                expect(page.locator("#metric-mean")).to_have_text("15")
                mutation("/replace?", lambda: page.locator("#replace-input").set_input_files(
                    {"name": "broken.csv", "mimeType": "text/csv", "buffer": RAW.replace(b",20,", b",NaN,")}))
                body = ask()
                assert body["previous_result"] and body["latest"]["status"] == "blocked"
                assert body["context"]["version"] == first["current"]["version"]
                assert body["context"]["source_name"] == "pressure.csv"
                assert body["latest"]["source_name"] == "broken.csv"
                assert body["summary"]["count"] == 2 and body["summary"]["mean"] == 15
                page.screenshot(path=str(output / "01-previous-result-desktop.png"), full_page=True)
                checks.append("failed replacement: actual retained source/version and independent mean 15")
                body = ask("handoff_limits")
                assert body["summary"]["quality_counts"]["unspecified"] == 2
                assert "미제공" in answer.inner_text()
                gaps = ask("gap_limits")
                assert gaps["summary"]["gap_count"] == 1 and gaps["summary"]["max_gap_seconds"] == 120
                checks.append("unspecified quality and 120-second descriptive gap")

                page.locator("#start-filter").fill("2021-01-01T00:00")
                draft = ask("handoff_limits")
                assert draft["summary"]["mean"] == 15 and draft["context"]["filter"]["start"] is None
                expect(page.locator("#explanation-context")).to_contain_text("마지막 조회")
                page.locator('[data-explanation-evidence="query"]').click()
                expect(panel).to_be_hidden()
                assert page.evaluate("document.activeElement.closest('#query-results, #analysis-area') !== null")
                checks.append("draft filter ignored; evidence returns to the same confirmed result")
                page.locator("#query-button").click()
                idle()
                empty = ask("handoff_limits")
                assert empty["summary"]["count"] == 0 and empty["summary"]["mean"] is None
                checks.append("empty selection clears the former mean")
                close()
                page.locator("#reset-range").click()
                idle()
                export_result(ask("handoff_limits"))
                checks.append("explanation context/summary matches actual exported manifest and CSV digest")

                evil = "<img src=x onerror=window.injected=1>"
                mutation("/api/datasets?", lambda: page.locator("#upload-input").set_input_files(
                    {"name": "labels.csv", "mimeType": "text/csv", "buffer": RAW.replace(b"Pump", evil.encode())}))
                safe = ask()
                assert safe["context"]["equipment"] == evil
                assert panel.locator("img").count() == 0 and page.evaluate("window.injected || 0") == 0
                checks.append("CSV instruction/markup labels remain inert text")
                close()

            sample = mutation("/api/datasets/sample", lambda: page.locator("#sample-button").click())
            page.locator("#tag-filter").select_option("Oil_temperature")
            page.locator("#query-button").click()
            idle()
            body = ask("handoff_limits")
            with (ROOT / "src/manufacturing_data_platform/file_review/sample/metropt3-day.csv").open() as source:
                values = [float(row["value"]) for row in csv.DictReader(source) if row["tag"] == "Oil_temperature"]
            assert body["summary"]["count"] == len(values) == 7144
            assert math.isclose(body["summary"]["mean"], statistics.fmean(values), abs_tol=1e-10)
            close()
            page.locator("#sample-exercise summary").click()
            mutation("/delivery-check", lambda: page.locator("#delivery-button").click())
            body = ask()
            assert body["latest"]["status"] == "incomplete" and body["previous_result"]
            assert body["context"]["version"] == sample["current"]["version"]
            page.screenshot(path=str(output / "02-sample-explanation-desktop.png"), full_page=True)
            checks.append("real sample statistics and delivery failure retain original version")

            # Desktop must permit using the result; narrow presentation must actually be modal.
            page.keyboard.press("Escape")
            expect(panel).to_be_hidden()
            expect(launcher).to_be_focused()
            for width in (390, 320):
                page.set_viewport_size({"width": width, "height": 844})
                ask("handoff_limits")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert panel.evaluate("el => el.matches(':modal') || el.getAttribute('aria-modal') === 'true'")
                page.locator("#query-button").evaluate("el => el.focus()")
                assert page.evaluate("document.activeElement.closest('#explanation-panel') !== null"), "Modal background accepted focus"
                # Cycle through enough stops to cross the end of this small dialog twice.
                for _ in range(24):
                    page.keyboard.press("Tab")
                    assert page.evaluate("document.activeElement.closest('#explanation-panel') !== null")
                page.screenshot(path=str(output / f"03-explanation-mobile-{width}.png"), full_page=True)
                page.keyboard.press("Escape")
                expect(panel).to_be_hidden()
                expect(launcher).to_be_focused()
            checks.append("1440/390/320px, modal focus containment, Escape and return")
            page.set_viewport_size({"width": 1440, "height": 1100})
            body = ask()

            # Test UI safety even when aborting the fetch cannot prevent delivery.
            delay()
            page.locator("#explanation-cancel").click()
            finish_late(body)
            checks.append("cancel invalidates a late response even with ineffective transport abort")
            ask()
            delay()
            page.locator("#reset-range").click()
            idle()
            finish_late(body)
            checks.append("new query invalidates a late explanation")
            body = ask()
            delay()
            close()
            mutation("/api/datasets/sample", lambda: page.locator("#sample-button").click())
            finish_late(body)
            checks.append("dataset switch discards a delayed old answer")

            # Timeout is a client wait limit, not proof that a server operation was cancelled.
            body = ask()
            delay()
            expect(page.locator("#explanation-retry")).to_be_visible(timeout=15000)
            finish_late(body)
            with page.expect_response(lambda response: "/explanation?" in response.url) as pending:
                page.locator("#explanation-retry").click()
            assert pending.value.ok
            expect(answer).to_be_visible()
            checks.append("10-second timeout rejects late answer; explicit retry succeeds")

            # Another tab changes latest after this tab's successful query.
            current = ask()
            route = base + "/api/datasets/" + current["context"]["dataset_id"]
            csrf = context.request.get(base + "/api/session").json()["csrf_token"]
            assert context.request.post(route + "/retry", headers={"X-Review-CSRF": csrf}).ok
            changed = ask(status=409)
            assert changed["error"]["code"] == "CONTEXT_CHANGED"
            assert not answer.text_content().strip(), "Stale answer content survived context change"
            checks.append("other-tab latest change returns CONTEXT_CHANGED and clears stale content")
            page.reload()
            idle()
            open_panel()
            assert not answer.text_content().strip(), "Answer history survived reload"
            checks.append("reload does not restore conversation history")

            current = ask()
            params = dict(current["context"]["filter"], question="previous_result",
                          equipment=current["context"]["equipment"], tag=current["context"]["tag"],
                          version=current["context"]["version"], latest_attempt_id=current["context"]["latest_attempt_id"])
            params = {key: value for key, value in params.items() if value is not None}
            endpoint = base + "/api/datasets/" + current["context"]["dataset_id"] + "/explanation?" + urlencode(params)
            stranger = browser.new_context()
            stranger.request.get(base + "/api/session")
            assert stranger.request.get(endpoint).status == 404
            stranger.close()
            checks.append("real HTTP explanation denies another browser workspace")

            delay()
            # Deletion in another tab must be observed as refusal on the next request.
            dataset_id = current["context"]["dataset_id"]
            assert context.request.delete(base + "/api/datasets/" + dataset_id,
                                          headers={"X-Review-CSRF": csrf}).ok
            page.locator("#explanation-cancel").click()
            finish_late(current)
            deleted = ask(status=404)
            assert deleted["error"]["code"] == "NOT_FOUND" and not answer.text_content().strip()
            checks.append("deleted dataset refuses explanation without remembered-content fallback")
            assert errors == [] and external == [], (errors, external)
            receipt["status"] = "PASS"
        except Exception as error:
            receipt.update(status="FAIL", failure=f"{type(error).__name__}: {error}")
            page.screenshot(path=str(output / "failure.png"), full_page=True)
            raise
        finally:
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            (output / "responses.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2) + "\n")
            try:
                csrf = context.request.get(base + "/api/session").json()["csrf_token"]
                for dataset_id in created:
                    response = context.request.delete(base + "/api/datasets/" + dataset_id,
                                                      headers={"X-Review-CSRF": csrf})
                    assert response.status in (200, 404), response.text()
            finally:
                browser.close()
            print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
