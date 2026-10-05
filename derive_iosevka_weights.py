"""Derive Iosevka Custom Light / SemiBold masters from the shipped static masters.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/derive_iosevka_weights.py.

Iosevka's parametric build (npm) is not run here.  Its weights keep the
skeleton and vertical zones and change the pen width, so the nearest shipped
master is offset by the stem difference and every edge that sat on a zone
(baseline, x-height, cap, ascender, descender) is put back on it.  The
result feeds build_inori_v3.py exactly like a real Iosevka static master:
it measures the achieved stem, and the width rhythm and bar correction are
applied there per SF Mono column.
"""
from pathlib import Path
import argparse, hashlib, json, sys
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / 'tools'))
sys.path.insert(0, str(HERE))
import shapes
import build_inori_v3 as mono

SRC = ROOT / 'Source/Iosevka'
OUT = SRC / 'derived'

# style -> (base master, nominal OS/2 weight).  The stem target is SF Mono's
# stem of that weight times STEM_CORRECTION, the same ideal plan_latin uses.
SF_SEMIBOLD = (116.2, 103.0)
PLAN = {'Light': ('Regular', 300), 'SemiBold': ('Medium', 600)}


def ideal(style):
    stem = SF_SEMIBOLD[0] if style == 'SemiBold' else mono.SF[style][0]
    return stem * mono.STEM_CORRECTION


def master(prefix, style, italic):
    name = ('Italic' if style == 'Regular' else style + 'Italic') if italic else style
    return SRC / f'{prefix}-{name}.ttf'


def invariant(prefix, italic):
    """Glyphs Iosevka draws identically in Regular, Medium and Bold.

    Block elements, shades, Powerline and legacy-computing cells, centre
    lines and a few marks are fixed geometry in Iosevka: they tile or align
    to the cell and do not follow the pen width.  They stay exactly as drawn.
    """
    fonts = [TTFont(master(prefix, s, italic)) for s in ('Regular', 'Medium', 'Bold')]
    sets = [f.getGlyphSet() for f in fonts]
    same = set()
    for name in fonts[0].getGlyphOrder():
        g = fonts[0]['glyf'][name]
        if g.isComposite() or g.numberOfContours <= 0:
            continue
        recs = []
        for gs in sets:
            pen = DecomposingRecordingPen(gs)
            gs[name].draw(pen)
            recs.append(pen.value)
        if recs[0] == recs[1] == recs[2]:
            same.add(name)
    return same


def zone_map(font, d):
    """Piecewise-linear y map that returns zone edges moved by d/2 to the zone."""
    cm, glyf = font.getBestCmap(), font['glyf']

    def edge(ch, top):
        g = glyf[cm[ord(ch)]]
        g.recalcBounds(glyf)
        return g.yMax if top else g.yMin
    zones = sorted({edge('p', False), 0, edge('x', True), edge('H', True), edge('l', True)})
    # Bottom edges of a zone sit below it (descender, baseline): they moved by
    # -d/2; top edges (x-height, cap, ascender) by +d/2.  Use the side the
    # zone is ink-bounded on: below for the lowest two, above for the rest.
    src, dst = [], []
    for z in zones:
        off = -d / 2 if z <= 0 else d / 2
        src.append(z + off)
        dst.append(z)
    src = [src[0] - 2000] + src + [src[-1] + 2000]
    dst = [dst[0] - 2000] + dst + [dst[-1] + 2000]

    def f(y):
        for i in range(len(src) - 1):
            if src[i] <= y <= src[i + 1]:
                t = (y - src[i]) / (src[i + 1] - src[i])
                return dst[i] + (dst[i + 1] - dst[i]) * t
        return y
    return f


def remap(rec, f):
    out = []
    for op, args in rec:
        out.append((op, tuple(None if p is None else (p[0], f(p[1])) for p in args)))
    return out


def derive(prefix, style, italic):
    base_style, weight = PLAN[style]
    path = master(prefix, base_style, italic)
    font = TTFont(path, recalcTimestamp=False)
    gs = font.getGlyphSet()
    h = font.getBestCmap()[ord('H')]
    pen = DecomposingRecordingPen(gs)
    gs[h].draw(pen)
    if italic:
        angle = float(font['post'].italicAngle)
        stem = shapes.stem_of(shapes.shear(pen.value, 0.0, pivot_y=mono.SF_CAP / 2,
                                           src_angle_deg=angle))
    else:
        stem = shapes.stem_of(pen.value)
    d = ideal(style) - stem
    fy = zone_map(font, d)
    glyf, hmtx = font['glyf'], font['hmtx']
    failures, changed = [], 0
    fixed = invariant(prefix, italic)
    del shapes.failures[:]
    for name in font.getGlyphOrder():
        g = glyf[name]
        if g.isComposite() or g.numberOfContours <= 0 or name in fixed:
            continue
        pen = DecomposingRecordingPen(gs)
        gs[name].draw(pen)
        rec = pen.value
        if not rec:
            continue
        res, frac = shapes.dilate_graded(rec, d, name, steps=(1.0, .85, .7, .55, .4))
        if frac < 1.0:
            # A hairline the offset cannot carry keeps as much of it as
            # survives (or the base drawing); listed with the fraction.
            failures.append([name, frac])
            if not frac:
                continue
        res = remap(res, fy)
        tt = TTGlyphPen(None)
        cu = Cu2QuPen(tt, max_err=0.25, reverse_direction=False)
        for op, args in res:
            getattr(cu, op)(*args)
        new = tt.glyph()
        new.recalcBounds(glyf)
        glyf[name] = new
        adv, _ = hmtx[name]
        hmtx[name] = (adv, getattr(new, 'xMin', 0))
        changed += 1
    # Composites follow their components; refresh their bounds and lsb.
    for name in font.getGlyphOrder():
        g = glyf[name]
        if g.isComposite():
            g.recalcBounds(glyf)
            hmtx[name] = (hmtx[name][0], g.xMin)
    font['OS/2'].usWeightClass = weight
    if 'hdmx' in font:
        del font['hdmx']
    if 'LTSH' in font:
        del font['LTSH']
    for tag in ('fpgm', 'prep', 'cvt ', 'gasp'):
        if tag in font:
            del font[tag]
    for g in glyf.glyphs.values():
        if hasattr(g, 'program'):
            g.program.fromBytecode(b'')
    out_name = ('Italic' if style == 'Regular' else style + 'Italic') if italic else style
    target = OUT / f'{prefix}-{out_name}.ttf'
    target.parent.mkdir(exist_ok=True)
    font.save(target)
    check = TTFont(target)
    cgs = check.getGlyphSet()
    pen = DecomposingRecordingPen(cgs)
    cgs[h].draw(pen)
    rec = pen.value
    if italic:
        rec = shapes.shear(rec, 0.0, pivot_y=mono.SF_CAP / 2, src_angle_deg=angle)
    got = shapes.stem_of(rec)
    return dict(output=str(target.relative_to(ROOT)), base=str(path.relative_to(ROOT)),
                base_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                stem_base=round(stem, 2), stem_target=round(ideal(style), 2),
                stem_result=round(got, 2), offset=round(d, 2), changed=changed,
                weight_invariant_kept=len(fixed), kept_base_drawing=failures)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*', default=list(PLAN))
    args = ap.parse_args()
    rows = []
    for prefix in ('IosevkaCustom', 'IosevkaCustomUnslashed'):
        for style in args.only:
            for italic in (False, True):
                r = derive(prefix, style, italic)
                print(r['output'], r['stem_base'], '->', r['stem_result'],
                      'target', r['stem_target'], 'kept', len(r['kept_base_drawing']), flush=True)
                rows.append(r)
    (OUT / 'derivation.json').write_text(json.dumps(rows, indent=2) + '\n')


if __name__ == '__main__':
    main()
