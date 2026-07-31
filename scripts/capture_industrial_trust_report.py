#!/usr/bin/env python3
"""Capture the three Industrial Telemetry Trust Report screens from report.html."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = REPO_ROOT / "docs" / "portfolio" / "industrial-telemetry-trust"
SCREENS = [
    (
        "01-operator-decisions.png",
        "#screen-summary",
        "normal / quality / interrupted operator decisions",
    ),
    (
        "02-source-provenance.png",
        "#screen-source",
        "actual record / OPC UA replay / fault provenance",
    ),
    (
        "03-event-time-trust.png",
        "#screen-event-time",
        "event-time stress, trusted current and claim boundary",
    ),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--scale", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base = Path(args.dir)
    report = base / "report.html"
    if not report.exists():
        print(
            f"report not found: {report}; run build_industrial_trust_report.py first",
            file=sys.stderr,
        )
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright is not importable; browser capture is unavailable. "
            "Do not hand-draw a substitute image.",
            file=sys.stderr,
        )
        return 3

    assets = base / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(
            viewport={"width": args.width, "height": 1100},
            device_scale_factor=args.scale,
        )
        page.goto(report.resolve().as_uri())
        page.wait_for_selector("#root .scenario")

        for filename, selector, description in SCREENS:
            element = page.query_selector(selector)
            if element is None:
                print(f"selector not found: {selector}", file=sys.stderr)
                browser.close()
                return 4
            target = assets / filename
            element.screenshot(path=str(target))
            print(f"{filename}: {target.stat().st_size} bytes ({description})")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
