#!/usr/bin/env python3
"""Optional actual-browser acceptance, run against a local `make serve` instance."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

RAW = b"timestamp,equipment,tag,value,unit\n2020-01-01T00:00:00,Pump,pressure,10,bar\n2020-01-01T00:00:10,Pump,pressure,20,bar\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default=".cache/file-review-browser")
    parser.add_argument("--mode", choices=("full", "sample"), default="full")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Browser verification only supports loopback servers.")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    errors, created_ids = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="ko-KR", timezone_id="Asia/Seoul")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def idle():
            expect(page.locator("#loading")).to_be_hidden(timeout=30000)

        def mutation(route, action):
            with page.expect_response(lambda response: route in response.url and response.request.method == "POST") as pending:
                action()
            response = pending.value
            assert response.ok, response.text()
            dataset = response.json()["dataset"]
            if dataset["id"] not in created_ids:
                created_ids.append(dataset["id"])
            idle()
            return dataset

        try:
            page.goto(args.url)
            idle()
            expect(page.locator("#welcome-title")).to_be_visible()
            page.screenshot(path=str(output / "01-welcome.png"), full_page=True)
            capabilities = page.evaluate("fetch('/api/session').then(response => response.json()).then(body => body.capabilities)")
            assert capabilities == {"uploads": args.mode == "full", "sample": True, "accounts": False}
            if args.mode == "sample":
                for selector in ("#upload-button", "#welcome-upload", "#replace-button", "#dropzone", "#input-guide"):
                    expect(page.locator(selector)).to_be_hidden()
                assert page.locator(".template-link").evaluate_all("elements => elements.every(element => element.hidden)")
                expect(page.locator("#welcome-description")).to_contain_text("공개 설비 기록")
            else:
                first = mutation("/api/datasets?", lambda: page.locator("#upload-input").set_input_files({"name": "pressure.csv", "mimeType": "text/csv", "buffer": RAW}))
                expect(page.locator("#metric-mean")).to_have_text("15")
                mutation("/replace", lambda: page.locator("#replace-input").set_input_files({"name": "broken.csv", "mimeType": "text/csv", "buffer": RAW.replace(b",20,", b",NaN,")}))
                expect(page.locator("#previous-query")).to_be_visible()
                expect(page.locator("#metric-mean")).to_have_text("15")
                page.screenshot(path=str(output / "02-previous-result.png"), full_page=True)
                with page.expect_download() as pending:
                    page.locator("#export-button").click()
                download = pending.value
                download.save_as(str(output / "previous-result.zip"))
                with ZipFile(output / "previous-result.zip") as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                    assert manifest["version"] == first["current"]["version"] and manifest["previous_result"] is True
                    assert manifest["observations_sha256"] == hashlib.sha256(archive.read("observations.csv")).hexdigest()
                idle()
                fixed = mutation("/replace", lambda: page.locator("#replace-input").set_input_files({"name": "corrected.csv", "mimeType": "text/csv", "buffer": RAW.replace(b",20,", b",30,")}))
                expect(page.locator("#metric-mean")).to_have_text("20")
                assert fixed["current"]["version"] != first["current"]["version"]
                # An empty valid interval must clear the preceding numbers, not retain the old chart.
                page.locator("#start-filter").fill("2021-01-01T00:00")
                page.locator("#end-filter").fill("2021-01-02T00:00")
                page.locator("#query-button").click()
                idle()
                expect(page.locator("#metric-count")).to_have_text("0")
                expect(page.locator("#metric-mean")).to_have_text("—")
            sample = mutation("/api/datasets/sample", lambda: page.locator("#sample-button").click())
            page.locator("#tag-filter").select_option("Oil_temperature")
            page.locator("#query-button").click()
            idle()
            expect(page.locator("#metric-count")).to_have_text("7,144")
            expect(page.locator("#metric-mean")).to_have_text("55.7481")
            # Allow transient status toast to dismiss before retaining the product screenshot.
            page.locator("#toast").evaluate("element => { element.hidden = true; }")
            page.screenshot(path=str(output / ("02-sample.png" if args.mode == "sample" else "03-sample.png")), full_page=True)
            page.locator("#sample-exercise summary").click()
            incomplete = mutation("/delivery-check", lambda: page.locator("#delivery-button").click())
            assert incomplete["current"]["version"] == sample["current"]["version"]
            expect(page.locator("#previous-query")).to_be_visible()
            recovered = mutation("/retry", lambda: page.locator("#recover-button").click())
            assert recovered["current"]["version"] == sample["current"]["version"]
            page.reload()
            idle()
            expect(page.locator("#dataset-count")).to_have_text("1 / 10" if args.mode == "sample" else "2 / 10")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / "04-mobile.png"), full_page=True)
            stranger = browser.new_context()
            stranger_page = stranger.new_page()
            stranger_page.goto(args.url)
            expect(stranger_page.locator("#loading")).to_be_hidden()
            expect(stranger_page.locator("#dataset-count")).to_have_text("0 / 10")
            stranger.close()
            assert errors == [], errors
            checks = (["sample-only controls"] if args.mode == "sample" else
                      ["upload", "blocked replacement", "previous result ZIP", "corrected upload", "empty range"])
            checks.extend(["sample query", "incomplete delivery", "recovery", "reload", "browser isolation", "mobile"])
            receipt = {"status": "PASS", "mode": args.mode, "browser": browser.version, "page_errors": errors,
                       "viewports": [1440, 390], "sample_version": sample["current"]["version"],
                       "checks": checks}
            (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps(receipt, indent=2))
        finally:
            # Only remove the datasets this verification created, using its isolated browser workspace.
            try:
                csrf = context.request.get(args.url + "/api/session").json()["csrf_token"]
                for dataset in created_ids:
                    context.request.delete(args.url + "/api/datasets/" + dataset, headers={"X-Review-CSRF": csrf})
            finally:
                browser.close()


if __name__ == "__main__":
    main()
