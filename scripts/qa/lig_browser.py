#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check that Friday Mono's ss02 ligatures show up in Chromium, Firefox and WebKit.

    .venv/Scripts/python.exe scripts/qa/lig_browser.py --web <dir with FridayMono-*.woff2> --out <dir>

For each browser and style the same specimen is drawn twice, with font-feature-settings "ss02" off
and on, from the WOFF2 file.  The two screenshots must differ (the ligatures were applied) and the
"on" one is written as a PNG.  The specimen also contains strings that must stay plain; they are
drawn in a separate line whose pixels must be identical on and off.  Needs PLAYWRIGHT_BROWSERS_PATH
(scripts/activate-font-tools.ps1 sets it).
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

STYLES = {"Light": 300, "Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
LIGATING = "== === != !== => -> <- <-> <=> >= <= >> << >>= =>> |> <| <|> a/=b p=/=q"
PLAIN = "==== ---- ->> <<< >>> a = b + c; (x, y) {}"


def page(web, styles, feature):
    faces, rows = [], []
    for style, weight in styles.items():
        for italic in (False, True):
            name = style + ("Italic" if italic else "") if not (style == "Regular" and italic) else "Italic"
            if style == "Regular" and not italic:
                name = "Regular"
            fam = "F-%s" % name
            faces.append('@font-face{font-family:"%s";src:url("%s/FridayMono-%s.woff2") format("woff2");'
                         'font-weight:%d;font-style:%s}' % (fam, Path(web).resolve().as_uri(), name, weight,
                                                            "italic" if italic else "normal"))
            rows.append('<div class="r" data-style="%s"><div class="l">%s</div><div class="p">%s</div></div>'
                        % (name, LIGATING, PLAIN))
            faces.append('.r[data-style="%s"]{font-family:"%s";font-weight:%d;font-style:%s}'
                         % (name, fam, weight, "italic" if italic else "normal"))
    css = ("body{margin:12px;background:#fff;color:#000;font-size:30px;font-feature-settings:%s}"
           ".r{margin:0 0 4px}.l,.p{white-space:pre;line-height:1.3}" % feature)
    return "<!doctype html><meta charset=utf-8><style>%s%s</style>%s" % ("".join(faces), css, "".join(rows))


def shot(browser, html_path, png=None):
    pg = browser.new_page(viewport={"width": 1500, "height": 900})
    pg.goto(html_path.resolve().as_uri())
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(500)
    status = pg.evaluate("[...document.fonts].map(f => f.family + ':' + f.status)")
    lines = {}
    for part in ("l", "p"):
        els = pg.query_selector_all("." + part)
        lines[part] = [hashlib.sha256(e.screenshot()).hexdigest() for e in els]
    if png:
        pg.screenshot(path=str(png), full_page=True)
    pg.close()
    return status, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "off.html").write_text(page(a.web, STYLES, '"ss02" 0'), encoding="utf-8")
    (out / "on.html").write_text(page(a.web, STYLES, '"ss02" 1'), encoding="utf-8")
    failures, report = 0, {}
    with sync_playwright() as p:
        for name in ("chromium", "firefox", "webkit"):
            browser = getattr(p, name).launch()
            s_off, off = shot(browser, out / "off.html")
            s_on, on = shot(browser, out / "on.html", out / ("FridayMono-ss02-%s.png" % name))
            browser.close()
            loaded = all(x.endswith(":loaded") for x in s_on)
            changed = [i for i, (x, y) in enumerate(zip(off["l"], on["l"])) if x != y]
            plain_same = off["p"] == on["p"]
            ok = loaded and len(changed) == len(off["l"]) and plain_same
            failures += 0 if ok else 1
            report[name] = {"faces_loaded": loaded, "ligating_rows_changed": "%d/%d" % (len(changed), len(off["l"])),
                            "plain_rows_identical": plain_same, "ok": ok}
            print("%-9s faces loaded %s, ligating rows changed %d/%d, plain rows identical %s -> %s"
                  % (name, loaded, len(changed), len(off["l"]), plain_same, "OK" if ok else "FAIL"))
    (out / "lig-browser.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
