#!/usr/bin/env python3
"""Loopback review handoff checks; actual downloads against independent CSV values."""
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright


RAW = ("timestamp,equipment,tag,value,unit\n"
       "2020-02-01T00:00:00,Pump,pressure,10,bar\n"
       "2020-02-01T00:00:10,Pump,pressure,20,bar\n"
       "2020-02-01T00:00:20,Pump,pressure,30,bar\n").encode()


def read_export(path):
    with ZipFile(path) as archive:
        assert set(archive.namelist()) == {"observations.csv", "manifest.json", "review.txt"}
        data = archive.read("observations.csv")
        manifest = json.loads(archive.read("manifest.json"))
        review = archive.read("review.txt").decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    assert hashlib.sha256(data).hexdigest() == manifest["observations_sha256"]
    assert len(rows) == manifest["summary"]["count"]
    for key in ("version", "source_sha256", "observations_sha256", "source_name", "equipment", "tag", "unit"):
        assert str(manifest[key]) in review, key
    values = [float(row["value"]) for row in rows]
    lines = review.splitlines()
    def reported(label):
        matches = [line.removeprefix(label + ": ") for line in lines if line.startswith(label + ": ")]
        assert len(matches) == 1, label
        return matches[0]
    assert int(reported("관측값 수")) == len(values)
    if values:
        assert math.isclose(manifest["summary"]["mean"], statistics.fmean(values), rel_tol=1e-12)
        assert manifest["summary"]["min"] == min(values)
        assert manifest["summary"]["max"] == max(values)
        assert math.isclose(float(reported("표본 평균")), statistics.fmean(values), rel_tol=1e-12)
        assert float(reported("최솟값")) == min(values)
        assert float(reported("최댓값")) == max(values)
    else:
        assert all(manifest["summary"][key] is None for key in ("mean", "min", "max"))
        assert all(reported(label) == "없음" for label in ("표본 평균", "최솟값", "최댓값"))
    for key in ("observations.csv", "manifest.json", "시간", "품질", "보간"):
        assert key in review, key
    return manifest, rows, review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("full", "sample"), default="full")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only loopback test servers are supported")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    checks, errors, downloads, queries = [], [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ko-KR")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("download", lambda download: downloads.append(download.suggested_filename))
        page.on("request", lambda request: queries.append(request.url) if "/query?" in request.url else None)

        def idle():
            expect(page.locator("#loading")).to_be_hidden(timeout=30000)

        def mutate(part, action):
            with page.expect_response(lambda r: part in r.url and r.request.method == "POST") as pending:
                action()
            response = pending.value
            assert response.ok, response.text()
            idle()
            return response.json()["dataset"]

        def query():
            with page.expect_response(lambda r: "/query?" in r.url) as pending:
                page.locator("#query-button").click()
            response = pending.value
            assert response.ok, response.text()
            idle()
            return response.json()

        def download(name, keyboard=False):
            with page.expect_download() as pending:
                if keyboard:
                    page.locator("#export-button").focus()
                    expect(page.locator("#export-button")).to_be_focused()
                    page.keyboard.press("Enter")
                else:
                    page.locator("#export-button").click()
            pending.value.save_as(str(out / name))
            idle()
            return read_export(out / name)

        try:
            page.goto(args.url)
            idle()
            health = context.request.get(args.url + "/healthz").json()
            sample = mutate("/api/datasets/sample", lambda: page.locator("#sample-button").click())
            page.locator("#tag-filter").select_option("Oil_temperature")
            result = query()
            expect(page.locator("#handoff-card")).to_be_visible()
            assert page.locator("#export-button").count() == 1
            assert page.locator("#handoff-card #export-button").count() == 1
            m, rows, review = download("sample.zip")
            # Independently read the bundled input, not the exported values alone.
            source = Path(__file__).resolve().parents[1] / "src/manufacturing_data_platform/file_review/sample/metropt3-day.csv"
            selected = [r for r in csv.DictReader(io.StringIO(source.read_text())) if r["tag"] == "Oil_temperature"]
            expected_values = [float(r["value"]) for r in selected]
            assert len(rows) == len(selected) == 7144
            assert [float(r["value"]) for r in rows] == expected_values
            assert math.isclose(m["summary"]["mean"], statistics.fmean(expected_values), rel_tol=1e-12)
            assert m["version"] == sample["current"]["version"] == result["version"]
            assert m["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
            assert m["summary"]["quality_counts"]["unspecified"] == 7144
            assert "시간대 미제공" in review
            (out / "sample-review.txt").write_text(review)
            checks.append("actual sample CSV, SQL summary and three-file ZIP agree")

            before = page.locator("#handoff-context").inner_text()
            query_count = len(queries)
            page.locator("#start-filter").fill("2040-01-01T00:00")
            page.locator("#end-filter").fill("2040-01-02T00:00")
            page.locator("#review-wide-toggle").click()
            assert page.locator("#handoff-context").inner_text() == before
            assert len(queries) == query_count
            draft, _, _ = download("date-draft.zip")
            assert draft["filter"] == m["filter"] == {"start": None, "end": None}
            assert draft["version"] == m["version"] and draft["observations_sha256"] == m["observations_sha256"]
            page.locator("#start-filter").fill("")
            page.locator("#end-filter").fill("")
            checks.append("date drafts and wide view preserve submitted scope and ZIP identity")

            # Same real content, readable card and keyboard activation at three widths.
            for width in (1440, 390, 320):
                page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                page.locator("#handoff-card").scroll_into_view_if_needed()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                box = page.locator("#handoff-card").bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1
                page.screenshot(path=str(out / f"handoff-{width}.png"))
            keyboard, _, _ = download("keyboard.zip", keyboard=True)
            assert keyboard["observations_sha256"] == m["observations_sha256"]
            checks.append("1440/390/320 card layout and keyboard download")

            page.set_viewport_size({"width": 1440, "height": 1000})
            page.locator("#explanation-launcher").click()
            with page.expect_response(lambda r: "/explanation?" in r.url) as pending:
                page.locator('[data-explanation-question="handoff_limits"]').click()
            explanation = pending.value.json()
            assert explanation["summary"]["count"] == 7144 and explanation["context"]["version"] == m["version"]
            page.locator("#explanation-close").click()
            checks.append("existing guided handoff explanation agrees with exported selection")

            # Sample failure is the existing incomplete-delivery exercise, not a real plant event.
            page.locator("#sample-exercise summary").click()
            failed = mutate("/delivery-check", lambda: page.locator("#delivery-button").click())
            retained, _, retained_text = download("retained-sample.zip")
            assert failed["latest"]["status"] == retained["latest_status"] == "incomplete"
            assert retained["previous_result"] is True and retained["version"] == m["version"]
            assert retained["observations_sha256"] == m["observations_sha256"]
            assert "이전" in retained_text and "미완료" in retained_text
            page.locator("#handoff-card").scroll_into_view_if_needed()
            page.screenshot(path=str(out / "retained-handoff.png"))
            checks.append("incomplete latest attempt preserves old observations with honest summary")

            if args.mode == "full":
                dataset = mutate("/api/datasets?", lambda: page.locator("#upload-input").set_input_files({"name": "pressure.csv", "mimeType": "text/csv", "buffer": RAW}))
                page.locator("#end-filter").fill("2020-02-01T00:00:20")
                query()
                half, exported, text = download("half-open.zip")
                assert [float(r["value"]) for r in exported] == [10, 20]
                assert half["summary"]["mean"] == 15 and half["summary"]["count"] == 2
                assert datetime.fromisoformat(half["filter"]["end"]) == datetime(2020, 2, 1, 0, 0, 20)
                assert half["source_sha256"] == hashlib.sha256(RAW).hexdigest()
                assert "2020-02-01T00:00:20" in text and ("미포함" in text or "전까지" in text or "제외" in text)
                page.locator("#start-filter").fill("2040-01-01T00:00")
                page.locator("#end-filter").fill("2040-01-02T00:00")
                query()
                empty, _, text = download("empty.zip")
                assert empty["summary"]["count"] == 0 and empty["summary"]["mean"] is None
                assert "없" in text
                page.locator("#handoff-card").scroll_into_view_if_needed()
                page.screenshot(path=str(out / "empty-handoff.png"))
                checks.append("synthetic half-open boundary and empty result are independent of previous numbers")

                long_tag = "<img src=x>" + "long-name-" * 12
                # 128 is the current accepted tag length; this is a synthetic label stress case.
                long_tag = long_tag[:128]
                hostile = ("timestamp,equipment,tag,value,unit\n"
                           f"2020-02-01T00:00:00,Pump <b>west</b>,{long_tag},10,bar\n").encode()
                dataset = mutate("/api/datasets?", lambda: page.locator("#upload-input").set_input_files({"name": "labels.csv", "mimeType": "text/csv", "buffer": hostile}))
                expect(page.locator("#handoff-context")).to_contain_text(long_tag)
                assert page.locator("#handoff-context img, #handoff-context b").count() == 0
                page.set_viewport_size({"width": 320, "height": 844})
                page.locator("#handoff-card").scroll_into_view_if_needed()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                page.screenshot(path=str(out / "long-label-320.png"))
                checks.append("synthetic long markup label remains inert and wraps at 320px")

                # Real owner-checked deletion from a second tab/API context invalidates download.
                session = context.request.get(args.url + "/api/session").json()
                deleted = context.request.delete(args.url + "/api/datasets/" + dataset["id"], headers={"X-Review-CSRF": session["csrf_token"]})
                assert deleted.ok
                count = len(downloads)
                page.locator("#export-button").click()
                idle()
                expect(page.locator("#handoff-card")).to_be_hidden()
                assert len(downloads) == count
                checks.append("real deleted dataset refuses export and hides the incompatible handoff")

            assert not errors, errors
            receipt = {"status": "PASS", "mode": args.mode, "health": health, "checks": checks,
                       "errors": errors, "sample_version": m["version"], "sample_csv_sha256": m["observations_sha256"],
                       "limit": "Local browser/CSV evidence, not human task success, deployment or clock repair."}
            (out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps(receipt, ensure_ascii=False))
        except Exception:
            page.screenshot(path=str(out / "failure.png"))
            (out / "failure.json").write_text(json.dumps({"completed": checks, "errors": errors}, ensure_ascii=False, indent=2))
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
