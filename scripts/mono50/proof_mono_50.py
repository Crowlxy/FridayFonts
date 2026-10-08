"""Proof images for Friday Mono 5.0 (FreeType through Pillow, hinted).

    py scripts/mono50/proof_mono_50.py

Writes into work/mono-5.0/reports/.  These are FreeType renders, not
screenshots of an application; the Windows GDI numbers are in
gdi-heights.json (scripts/mono50/windows/gdi_heights.ps1).
"""
import io
import json
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_mono_50 import ASCENT, DESCENT, OUT, STYLES, ZIP, COVERAGE  # noqa: E402

UI = 'C:/Windows/Fonts/segoeui.ttf'
REPORTS = OUT / 'reports'
INK, PAPER, MUTED, GRID = (20, 20, 20), (255, 255, 255), (110, 110, 110), (222, 228, 236)


def old_font(style, tmp):
    data = zipfile.ZipFile(ZIP).read('FridayMono-4.93/ttf/FridayMono-%s.ttf' % style)
    path = tmp / ('FridayMono493-%s.ttf' % style)
    path.write_bytes(data)
    return str(path)


def label(draw, xy, text, size=15, fill=MUTED):
    draw.text(xy, text, font=ImageFont.truetype(UI, size), fill=fill)


def heights_proof(tmp):
    """Round letters against flat ones at text sizes, enlarged 4x."""
    fonts = [('4.93 Regular', old_font('Regular', tmp)),
             ('5.0 Regular', str(OUT / 'ttf/FridayMono-Regular.ttf')),
             ('Cascadia Mono', 'C:/Windows/Fonts/CascadiaMono.ttf'),
             ('Consolas', 'C:/Windows/Fonts/consola.ttf')]
    text = 'HCOGSD xoces'
    sizes = (11, 13, 16)
    scale = 4
    col_w = 16 * 8 * scale
    img = Image.new('RGB', (180 + col_w * len(sizes), 60 + len(fonts) * 130), PAPER)
    d = ImageDraw.Draw(img)
    label(d, (20, 16), 'Round vs flat letters (FreeType, hinted, enlarged 4x). Blue lines: ink top and bottom of H and x.', 16, INK)
    for c, px in enumerate(sizes):
        label(d, (180 + c * col_w, 40), '%d px' % px)
    for r, (name, path) in enumerate(fonts):
        y0 = 70 + r * 130
        label(d, (20, y0 + 40), name, 16, INK)
        for c, px in enumerate(sizes):
            face = ImageFont.truetype(path, px)
            small = Image.new('L', (px * 8, px * 2), 0)
            sd = ImageDraw.Draw(small)
            sd.text((2, int(px * 1.5)), text, font=face, fill=255, anchor='ls')
            big = small.resize((small.width * scale, small.height * scale), Image.NEAREST)
            tile = Image.new('RGB', big.size, PAPER)
            tile.paste(INK, mask=big)
            td = ImageDraw.Draw(tile)
            for ch in 'Hx':
                box = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((2, int(px * 1.5)), ch, font=face, anchor='ls')
                probe = Image.new('L', small.size, 0)
                ImageDraw.Draw(probe).text((2, int(px * 1.5)), ch, font=face, fill=255, anchor='ls')
                b = probe.getbbox()
                for yy in (b[1], b[3]):
                    td.line((0, yy * scale, tile.width, yy * scale), fill=(70, 120, 220), width=1)
            img.paste(tile, (180 + c * col_w, y0))
    img.save(REPORTS / 'proof-round-letters.png')


def linebox_proof(tmp):
    """Where text sits in the 1.28 em line, 4.93 and 5.0, with box drawing."""
    px = 28
    cell_h = round((ASCENT - DESCENT) * px / 1000)
    rows = ['Hxgp CO 0123', '│ ─┼─ █▀▄ ╭─╮', '└──┴──┘ ░▒▓']
    img = Image.new('RGB', (1060, 70 + 3 * cell_h * 2 + 80), PAPER)
    d = ImageDraw.Draw(img)
    label(d, (20, 14), 'Line box (shaded) at 28 px. 4.93: ascent 880 / descent -400.  5.0: ascent 968 / descent -312, same 1.28 em.', 16, INK)
    for col, (name, path, asc) in enumerate([('4.93', old_font('Regular', tmp), 880),
                                              ('5.0', str(OUT / 'ttf/FridayMono-Regular.ttf'), ASCENT)]):
        x0 = 20 + col * 520
        label(d, (x0, 44), name, 16, INK)
        face = ImageFont.truetype(path, px)
        for i, line in enumerate(rows):
            top = 70 + i * cell_h
            d.rectangle((x0, top, x0 + 480, top + cell_h - 1), fill=GRID if i % 2 == 0 else (236, 240, 245))
            d.text((x0 + 6, top + round(asc * px / 1000)), line, font=face, fill=INK, anchor='ls')
    img.save(REPORTS / 'proof-line-box.png')


def styles_proof():
    """New characters and a sample line in all ten styles."""
    coverage = json.loads(COVERAGE.read_text(encoding='utf-8'))
    added = ''.join(chr(int(r['cp'][2:], 16)) for r in coverage['add'])
    px = 24
    img = Image.new('RGB', (1500, 40 + len(STYLES) * 44), PAPER)
    d = ImageDraw.Draw(img)
    label(d, (20, 10), 'Friday Mono 5.0, ten styles. Right: the 22 characters added in 5.0.', 16, INK)
    for i, (style, _) in enumerate(STYLES):
        y = 40 + i * 44
        face = ImageFont.truetype(str(OUT / 'ttf' / ('FridayMono-%s.ttf' % style)), px)
        label(d, (20, y + 6), style)
        d.text((170, y + 28), 'COGS ocs 0O Il1 {}=>', font=face, fill=INK, anchor='ls')
        d.text((600, y + 28), added, font=face, fill=INK, anchor='ls')
    img.save(REPORTS / 'proof-styles.png')


def proportions_proof(tmp):
    """4.93 and 5.0 side by side with the x-height, cap height and ascender."""
    px = 72
    text = 'Hamburg Il1 fbdk 0123 Åé'
    img = Image.new('RGB', (1500, 60 + 2 * 150), PAPER)
    d = ImageDraw.Draw(img)
    label(d, (20, 12), 'Vertical proportions at 72 px.  4.93: cap / x 1.41.  5.0: cap / x 1.333 and '
          'ascender / cap 1.047, the ratios of SF Mono.  Lines: x-height, cap height, ascender.', 16, INK)
    for row, (name, path, x, cap, asc) in enumerate([
            ('4.93', old_font('Regular', tmp), 522, 737, 772),
            ('5.0', str(OUT / 'ttf/FridayMono-Regular.ttf'), 522, 696, 729)]):
        base = 60 + row * 150 + 110
        label(d, (20, base - 30), name, 16, INK)
        for h, col in ((0, GRID), (x, (190, 210, 245)), (cap, (180, 225, 180)), (asc, (235, 200, 160))):
            y = base - round(h * px / 1000)
            d.line((90, y, 1480, y), fill=col, width=1)
        d.text((90, base), text, font=ImageFont.truetype(path, px), fill=INK, anchor='ls')
    img.save(REPORTS / 'proof-proportions.png')


def main():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    REPORTS.mkdir(parents=True, exist_ok=True)
    heights_proof(tmp)
    linebox_proof(tmp)
    styles_proof()
    proportions_proof(tmp)
    print('proofs written to', REPORTS)


if __name__ == '__main__':
    main()
