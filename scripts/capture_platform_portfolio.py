#!/usr/bin/env python3
"""Capture the platform-overview screens directly from the rendered `report.html`.

The report renders the committed `evidence/runtime-evidence.json` in the browser, so a screenshot
taken here shows the same values the JSON holds. No image is drawn by hand: if the browser is not
available this script exits non-zero and the screenshot item must be reported as blocked rather
than mocked.

```bash
python scripts/capture_platform_portfolio.py
```

Requires Playwright with a Chromium build already installed locally. Playwright is intentionally
NOT added to any requirements file: this is a one-off authoring tool, not a runtime or CI
dependency.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = REPO_ROOT / "docs" / "portfolio" / "platform-overview"

# Each screen is one card of the report, captured at a fixed viewport width so the three images
# form a consistent set. `selector` is the element the shot is clipped to.
SCREENS = [
    ("01-platform-overview.png", "#screen-1", "architecture, scope and current result"),
    ("02-failure-recovery.png", "#screen-2", "partial failure -> blocked -> complete recovery"),
    ("03-publish-retry-evidence.png", "#screen-3", "quality/publish -> retry with no new snapshot"),
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
        print(f"report not found: {report}; run build_platform_portfolio_evidence.py first",
              file=sys.stderr)
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright is not importable; browser capture is unavailable.\n"
            "Report the screenshot item as BLOCKED. Do not hand-draw a substitute image.",
            file=sys.stderr,
        )
        return 3

    assets = base / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(
            viewport={"width": args.width, "height": 900},
            device_scale_factor=args.scale,
        )
        page.goto(report.resolve().as_uri())
        page.wait_for_selector("#root .card")

        for filename, selector, description in SCREENS:
            element = page.query_selector(selector)
            if element is None:
                print(f"selector not found for {filename}: {selector}", file=sys.stderr)
                browser.close()
                return 4
            target = assets / filename
            element.screenshot(path=str(target))
            print(f"{filename}: {target.stat().st_size} bytes  ({description})")

        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
