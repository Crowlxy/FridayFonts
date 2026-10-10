"""Compare every glyph outline of 4.93 and 5.0 by area.

    py scripts/mono50/compare_outlines.py

The outline repair moves a few points by a few units; this catches a broken
contour (wrong point order, lost point, flipped direction) that a bounding-box
check would miss.  For each character both outlines are filled with the
non-zero rule and the area of their symmetric difference is divided by the
4.93 ink area.  Rasterising with Pillow is not used: it places glyphs by the
rounded ascender, which 5.0 changed, so whole glyphs move by a fraction of a
pixel and every edge looks different.

Box drawing, the two redrawn triangles, the glyphs whose heights move to
SF Mono's proportions (heights.py, listed in build-log.json) and the 4.93
defects repaired by inherited_fixes.py (build-log.json) are skipped
because they change on purpose; verify_mono_50.py checks their heights and
stroke thickness instead.  New characters have no 4.93 counterpart.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import pathops
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_mono_50 import BOX, OUT, STYLES, ZIP  # noqa: E402

LIMIT = 0.01          # area(old XOR new) / area(old)
LIMIT_WIDENED = 0.25  # a Light face widened by light_stem.py differs by the offset (about 8 %); a broken contour is far above


def path_of(font, name):
    path = pathops.Path()
    font.getGlyphSet()[name].draw(path.getPen())
    path.simplify(fix_winding=True)
    return path


def main():
    archive = zipfile.ZipFile(ZIP)
    report = {}
    failed = False
    for style, _ in STYLES:
        old = TTFont(io.BytesIO(archive.read('FridayMono-4.93/ttf/FridayMono-%s.ttf' % style)))
        new = TTFont(OUT / 'ttf' / ('FridayMono-%s.ttf' % style))
        ocmap, ncmap = old.getBestCmap(), new.getBestCmap()
        log = json.loads((OUT / 'build-log.json').read_text())['styles'][style]
        planned = set(log['height_plans'])
        repaired = {int(k[2:], 16) for k in log['inherited_fixes'] if k.startswith('U+')}
        rows = []
        for cp in sorted(set(ocmap) & set(ncmap)):
            if BOX[0] <= cp <= BOX[1] or cp in (0x25B2, 0x25BC) or ncmap[cp] in planned or cp in repaired:
                continue
            a, b = path_of(old, ocmap[cp]), path_of(new, ncmap[cp])
            ink = abs(a.area)
            if not ink:
                rows.append((0.0 if not abs(b.area) else 1.0, 'U+%04X' % cp))
                continue
            xor = pathops.op(a, b, pathops.PathOp.XOR)
            rows.append((abs(xor.area) / ink, 'U+%04X' % cp))
        rows.sort(reverse=True)
        limit = LIMIT_WIDENED if log['inherited_fixes'].get('light_stem') else LIMIT
        bad = [r for r in rows if r[0] > limit]
        failed |= bool(bad)
        report[style] = {'compared': len(rows), 'limit': limit, 'over_limit': bad,
                         'worst': rows[:5],
                         'mean': sum(r[0] for r in rows) / len(rows)}
        print('%-15s compared %4d  over %.1f%%: %d  mean %.4f%%  worst %s'
              % (style, len(rows), limit * 100, len(bad), report[style]['mean'] * 100,
                 [(round(r * 100, 3), c) for r, c in rows[:3]]), flush=True)
    (OUT / 'reports').mkdir(exist_ok=True)
    (OUT / 'reports' / 'outline-compare.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
