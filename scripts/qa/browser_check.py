#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Load WOFF2 faces in Chromium, Firefox and WebKit and screenshot a specimen.

    .venv/Scripts/python.exe scripts/qa/browser_check.py --web <dir with *.woff2> --family "Friday Sans" \
        --prefix FridaySans --out work/qa/browser --text <specimen>

For each browser and face: the face must load (document.fonts.load resolves with the face
loaded and status 'loaded'), the repaired kanji / U+2252 must be drawn from it (the rendered
pixels of the specimen differ from the fallback), and a PNG is written.  Needs
PLAYWRIGHT_BROWSERS_PATH (scripts/activate-font-tools.ps1 sets it).
"""
import argparse
import json
import os
import sys
from html import escape
from pathlib import Path

from playwright.sync_api import sync_playwright

WEIGHTS = {"Light": 300, "Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
STYLE_WEIGHTS = {**WEIGHTS, **{(s + "Italic" if s != "Regular" else "Italic"): w
                            for s, w in WEIGHTS.items()}}
DEFAULT_TEXT = "共題武昆廃慮唄圓驀 ≒ 氏祇隄詆壻 日本語の文字 Hamburgefonstiv 0123456789"


def page_html(web, family, prefix, styles, text, lite):
    faces = []
    for style, w in styles.items():
        sub = "lite/" if lite else ""
        faces.append('@font-face{font-family:"T-%s";src:url("%s%s%s-%s.woff2") format("woff2");font-weight:%d;font-style:%s;}'
                     % (family, Path(web).resolve().as_uri() + "/", sub, prefix, style, w,
                        "italic" if style.endswith("Italic") else "normal"))
    rows = "".join('<div class="r" data-style="%s" style="font-family:\'T-%s\',serif;font-weight:%d;font-style:%s"><small>%s %d</small>'
                   '<span class="s">%s</span></div>' % (style, family, w, "italic" if style.endswith("Italic") else "normal", style, w, escape(text))
                   for style, w in styles.items())
    return ("<!doctype html><meta charset=utf-8><style>%s body{margin:16px;background:#fff;color:#000}"
            ".r{margin:0 0 6px;font-size:34px;line-height:1.35}small{display:inline-block;width:150px;"
            "font:12px sans-serif;color:#666}</style>%s" % ("".join(faces), rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", required=True)
    ap.add_argument("--family", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--text", default=DEFAULT_TEXT)
    ap.add_argument("--lite", action="store_true")
    ap.add_argument("--styles", default=",".join(WEIGHTS))
    a = ap.parse_args()
    requested = a.styles.split(",")
    if not all(requested) or len(set(requested)) != len(requested):
        ap.error("--styles must contain unique, nonempty styles")
    try:
        styles = {s: STYLE_WEIGHTS[s] for s in requested}
    except KeyError:
        ap.error("unknown style")
    if not a.text.strip():
        ap.error("--text must contain visible characters")
    os.makedirs(a.out, exist_ok=True)
    html = Path(a.out) / ("specimen-%s%s.html" % (a.prefix, "-lite" if a.lite else ""))
    html.write_text(page_html(a.web, a.family, a.prefix, styles, a.text, a.lite), encoding="utf-8")
    report, bad = {}, 0
    with sync_playwright() as p:
        for name in ("chromium", "firefox", "webkit"):
            browser = getattr(p, name).launch()
            page = browser.new_page(viewport={"width": 1500, "height": 900})
            page.goto(html.resolve().as_uri())
            res = page.evaluate(r"""async (expected) => {
                const out = {};
                for (const row of document.querySelectorAll('.r')) {
                    const style = row.dataset.style, css = getComputedStyle(row);
                    const sample = row.querySelector('.s').textContent;
                    const font = `${css.fontStyle} ${css.fontWeight} 64px ${css.fontFamily}`;
                    let loaded = [], error = null;
                    try { loaded = await document.fonts.load(font, sample); }
                    catch (e) { error = String(e); }
                    const canvas = document.createElement('canvas');
                    canvas.width = 8192; canvas.height = 160;
                    const ctx = canvas.getContext('2d', {willReadFrequently:true});
                    function raster(family, value=sample) {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        ctx.font = `${css.fontStyle} ${css.fontWeight} 64px ${family}`;
                        ctx.fillText(value, 8, 100);
                        return ctx.getImageData(0, 0, canvas.width, canvas.height).data;
                    }
                    const actual = raster(css.fontFamily), fallback = raster('serif');
                    let changedPixels = 0, inkPixels = 0;
                    for (let i=3; i<actual.length; i+=4) {
                        if (actual[i]) inkPixels++;
                        if (actual[i] !== fallback[i]) changedPixels++;
                    }
                    const glyphDifferences = {};
                    for (const ch of new Set(sample)) {
                        if (/\s/u.test(ch)) continue;
                        const a = raster(css.fontFamily, ch), b = raster('serif', ch);
                        let count = 0;
                        for (let i=3; i<a.length; i+=4) if (a[i] !== b[i]) count++;
                        glyphDifferences['U+' + ch.codePointAt(0).toString(16).toUpperCase().padStart(4,'0')] = count;
                    }
                    out[style] = {weight:css.fontWeight, style:css.fontStyle,
                        loadedFaces:loaded.length, status:loaded.map(f => f.status),
                        changedPixels, inkPixels, glyphDifferences, error,
                        pass:loaded.length === 1 && loaded[0].status === 'loaded' && changedPixels > 0 && inkPixels > 0};
                }
                if (Object.keys(out).length !== expected) throw Error('Unexpected face count');
                return out;
            }""", len(styles))
            page.wait_for_timeout(500)
            shot = Path(a.out) / ("%s-%s%s.png" % (a.prefix, name, "-lite" if a.lite else ""))
            page.screenshot(path=str(shot), full_page=True)
            report[name] = res
            bad += sum(1 for v in res.values() if not v["pass"])
            print(name, {s: {k: v for k, v in r.items() if k != "glyphDifferences"} for s, r in res.items()})
            browser.close()
    (Path(a.out) / ("browser-%s%s.json" % (a.prefix, "-lite" if a.lite else ""))).write_text(
        json.dumps(report, indent=1), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
