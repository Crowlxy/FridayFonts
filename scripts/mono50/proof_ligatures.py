"""Specimens of the ss02 ligatures: reports/proof-ligatures.png and proof-ligatures-styles.png.

    .venv/Scripts/python.exe scripts/mono50/proof_ligatures.py [--paper <Paper Mono ttf>]

Draws the built WOFF2 faces in Chromium (feature settings off / on).  proof-ligatures.png: every
sequence, Regular, plain next to ss02.  proof-ligatures-styles.png: all ten styles with ss02.
--paper adds a reference column (Paper Mono, its own ss01 "Coding ligatures") to
proof-ligatures-vs-paper.png in the output folder; Paper Mono is OFL-licensed and is used only to
look at, never copied into the fonts.
"""
import argparse
import os
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_mono_50 import OUT, STYLES  # noqa: E402
import ligatures  # noqa: E402

os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str((HERE.parents[1] / 'work/font-tools/browsers').resolve()))
from playwright.sync_api import sync_playwright  # noqa: E402

WEB = OUT / 'web'
REPORTS = OUT / 'reports'
SEQS = [s for s, _ in ligatures.SEQUENCES]


def face_css(prefix='F'):
    css = []
    for style, weight in STYLES:
        css.append('@font-face{font-family:"%s-%s";src:url("%s");font-weight:%d;font-style:%s}'
                   % (prefix, style, (WEB / ('FridayMono-%s.woff2' % style)).resolve().as_uri(), weight,
                      'italic' if 'Italic' in style else 'normal'))
    return ''.join(css)


def render(html, png, width, name):
    page_file = REPORTS / (name + '.html')
    page_file.write_text(html, encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={'width': width, 'height': 600})
        pg.goto(page_file.resolve().as_uri())
        pg.evaluate('document.fonts.ready')
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(png), full_page=True)
        browser.close()
    page_file.unlink()


def compare_page(paper=None):
    cols = ['Friday Mono Regular', 'Friday Mono Regular + ss02']
    cells = []
    for seq in SEQS:
        row = '<div class="s">%s</div>' % escape(seq)
        row += '<div class="g f off">a%sb</div><div class="g f on">a%sb</div>' % (escape(seq), escape(seq))
        if paper:
            row += '<div class="g p">a%sb</div>' % escape(seq)
        cells.append(row)
    head = ''.join('<div class="h">%s</div>' % c for c in ['sequence'] + cols + (['Paper Mono + ss01 (reference)'] if paper else []))
    extra = '@font-face{font-family:P;src:url("%s");font-weight:400}' % Path(paper).resolve().as_uri() if paper else ''
    ncol = 4 if paper else 3
    return ('<!doctype html><meta charset=utf-8><style>%s%s body{margin:16px;background:#fff;color:#000}'
            '.t{display:grid;grid-template-columns:90px repeat(%d,1fr);gap:4px 24px;align-items:center}'
            '.h{font:12px sans-serif;color:#666}.s{font:13px sans-serif;color:#444}.g{font-size:46px;white-space:pre;line-height:1.25}'
            '.f{font-family:"F-Regular"}.off{font-feature-settings:"ss02" 0}.on{font-feature-settings:"ss02" 1}'
            '.p{font-family:P;font-feature-settings:"ss01" 1}</style><div class="t">%s%s</div>'
            % (face_css(), extra, ncol - 1, head, ''.join(cells)))


def styles_page():
    rows = []
    for style, weight in STYLES:
        text = '  '.join(SEQS)
        rows.append('<div class="r" style="font-family:\'F-%s\';font-weight:%d;font-style:%s">'
                    '<small>%s</small>%s</div>' % (style, weight, 'italic' if 'Italic' in style else 'normal', style,
                                                   escape(text)))
    return ('<!doctype html><meta charset=utf-8><style>%s body{margin:16px;background:#fff;color:#000}'
            '.r{font-feature-settings:"ss02" 1;font-size:30px;white-space:pre;line-height:1.5}'
            'small{display:block;font:12px sans-serif;color:#666;line-height:1.2}</style>%s'
            % (face_css(), ''.join(rows)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paper', default='')
    a = ap.parse_args()
    REPORTS.mkdir(exist_ok=True)
    render(compare_page(), REPORTS / 'proof-ligatures.png', 900, '_lig1')
    render(styles_page(), REPORTS / 'proof-ligatures-styles.png', 1900, '_lig2')
    print('written', REPORTS / 'proof-ligatures.png', REPORTS / 'proof-ligatures-styles.png')
    if a.paper:
        render(compare_page(a.paper), REPORTS / 'proof-ligatures-vs-paper.png', 1400, '_lig3')
        print('written', REPORTS / 'proof-ligatures-vs-paper.png')


if __name__ == '__main__':
    main()
