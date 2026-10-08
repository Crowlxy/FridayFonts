"""Look for spikes the height change could leave in 5.0 outlines.

    py scripts/mono50/spike_check.py

A spike is a point whose two neighbours are both on the same side of it and
much closer to each other than to it, with both arms short (8-80 units): a
thin needle sticking out of the outline, like the one the first emboldening
left inside the hook of Bold f.  4.93 is checked the same way so only new ones count.
"""
import io
import json
import math
import sys
import zipfile
from pathlib import Path

from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_mono_50 import OUT, STYLES, ZIP  # noqa: E402


# Flagged and checked by eye (old and new outlines overlaid), 2026-10-08:
REVIEWED = {
    'braceleft': 'designed point of the brace, a little sharper after the vertical scale',
    'braceright': 'same as braceleft',
    'six': 'designed joint of the stroke and the bowl',
    'nine': 'designed joint of the stroke and the bowl',
    'eight': 'designed joint of the two bowls (italic)',
    'Uogonek': 'designed joint of the ogonek',
    'uni20A9': 'designed inner notches of the W in the won sign',
    'germandbls': 'designed joint of the stem and the bowl (italic)',
    'registered': 'designed foot of the R inside the ring',
}


# Same, for a base letter and every accented form of it.
REVIEWED_BASES = {
    'A': 'designed apex of the counter of A (italic), sharper after the vertical scale',
    'V': 'designed crotch of V (italic)',
}


def reviewed(font, name):
    import unicodedata
    from fontTools.agl import toUnicode
    if name in REVIEWED:
        return True
    reverse = {g: cp for cp, g in font.getBestCmap().items()}
    cp = reverse.get(name)
    if cp is None:
        text = toUnicode(name.split('.')[0])
        cp = ord(text) if len(text) == 1 else None
    return cp is not None and unicodedata.normalize('NFD', chr(cp))[0] in REVIEWED_BASES


def spikes(font, names):
    glyf = font['glyf']
    found = {}
    for name in names:
        g = glyf[name]
        if g.numberOfContours <= 0:
            continue
        coords, ends, _ = g.getCoordinates(glyf)
        start = 0
        for end in ends:
            pts = [coords[i] for i in range(start, end + 1)]
            start = end + 1
            n = len(pts)
            for k in range(n):
                a, p, b = pts[k - 1], pts[k], pts[(k + 1) % n]
                pa, pb = math.dist(a, p), math.dist(p, b)
                # a needle: two short arms (8-80 units) folding back on each
                # other.  Long arms are a designed sharp corner (M, W, braces)
                if min(pa, pb) < 8 or max(pa, pb) > 80:
                    continue
                # angle at p
                v1 = (a[0] - p[0], a[1] - p[1])
                v2 = (b[0] - p[0], b[1] - p[1])
                cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (pa * pb)
                if cos > 0.9 and math.dist(a, b) < 0.5 * min(pa, pb):       # < ~25 degrees
                    found.setdefault(name, []).append((round(p[0]), round(p[1])))
    return found


def main():
    archive = zipfile.ZipFile(ZIP)
    report, bad = {}, False
    for style, _ in STYLES:
        old = TTFont(io.BytesIO(archive.read('FridayMono-4.93/ttf/FridayMono-%s.ttf' % style)))
        new = TTFont(OUT / 'unhinted' / ('FridayMono-%s.ttf' % style))
        before = spikes(old, old.getGlyphOrder())
        after = spikes(new, new.getGlyphOrder())
        added = {n: v for n, v in after.items() if len(v) > len(before.get(n, []))}
        unexplained = {n: v for n, v in added.items() if not reviewed(new, n)}
        report[style] = {'spikes_4.93': len(before), 'spikes_5.0': len(after), 'new': added,
                         'new_unreviewed': unexplained}
        bad |= bool(unexplained)
        print('%-15s glyphs with spikes 4.93 %d, 5.0 %d, new %d, unreviewed %s'
              % (style, len(before), len(after), len(added), list(unexplained)[:8]))
    report['reviewed'] = REVIEWED
    report['reviewed_bases'] = REVIEWED_BASES
    (OUT / 'reports').mkdir(exist_ok=True)
    (OUT / 'reports' / 'spike-check.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
