"""Check tool installation only; no font files are opened or reviewed."""
import importlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in (
    "fontTools", "ufoLib2", "diffenator2", "fontmake", "uharfbuzz",
    "pathops", "playwright", "vttLib", "freetype", "ttfautohint",
    "brotli", "scipy", "skimage",
):
    importlib.import_module(name)
    print(f"OK: {name}")

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / "work/font-tools/browsers")
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    for name in ("chromium", "firefox", "webkit"):
        browser = getattr(playwright, name).launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content("<title>Tool check</title><p>Ready</p>")
            assert page.title() == "Tool check"
            print(f"OK: Playwright {name}")
        finally:
            browser.close()
