"""Run the 4.91 Mono checks (verify_mono_49, audit_italic_rc3) on the new 4.93 faces.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/weights/verify_mono_weights.py

Both scripts are loaded with asserted path edits only, plus one rule change:
the new faces carry the 4.92 descender (-400), so hhea / OS/2 are compared
field by field with only the descender fields allowed to differ.
"""
from pathlib import Path
import json, sys

HERE = Path(__file__).resolve().parent
FF = HERE.parent
sys.path.insert(0, str(HERE))
from build_weights import load
from fontTools.ttLib import TTFont

DIST = FF / 'dist-mono-4.93'
NEW = ('Light', 'SemiBold', 'LightItalic', 'SemiBoldItalic')

verify = load(FF / 'verify_mono_49.py', [
    ("OUT = ROOT/'FridayFonts/dist-mono-4.91'", "OUT = ROOT/'FridayFonts/dist-mono-4.93'"),
    ("    rows=json.loads((OUT/'font-manifest.json').read_text());results=[]\n    assert len(rows)==18\n",
     "    rows=[r for r in json.loads((OUT/'font-manifest.json').read_text()) if r['style'] in NEW];results=[]\n    assert len(rows)==12\n"),
    ("            for tag in ('GPOS','GDEF','OS/2','hhea','vhea'):", "            for tag in ('GPOS','GDEF','vhea'):"),
    ("    (OUT/'reports/validation.json').write_text(", "    (OUT/'reports/validation-new-weights.json').write_text("),
    ("no new Windows native rendering certification for 4.91.", "no Windows native rendering certification for the 4.93 Light/SemiBold faces."),
    ("    im.crop((0,0,1180,y+10)).save(OUT/'reports/proof.png')", "    im.crop((0,0,1180,y+10)).save(OUT/'reports/proof-new-weights.png')"),
], name='verify_mono_49_weights')
verify.NEW = NEW

italic = load(FF / 'audit_italic_rc3.py', [
    ("OUT=ROOT/'FridayFonts/dist-mono-4.91/reports'", "OUT=ROOT/'FridayFonts/dist-mono-4.93/reports'"),
    ("        path=ROOT/f'FridayFonts/rc3-italic/ttf/mono-RC3-{style}.ttf'",
     "        path=ROOT/f'FridayFonts/build-weights/rc3-italic/ttf/mono-RC3-{style}.ttf'"),
    ("        old=ROOT/f'FridayFonts/dist-v48/ttf/FridayMono-{style}.ttf'",
     "        old=ROOT/f'FridayFonts/build-weights/mono-v48/FridayMono-{style}.ttf'"),
], name='audit_italic_rc3_weights')


def metrics_only_descender():
    allowed = {'hhea': {'descent'}, 'OS/2': {'sTypoDescender'}}
    for row in json.loads((DIST / 'font-manifest.json').read_text()):
        if row['style'] not in NEW:
            continue
        f, base = TTFont(DIST / row['ttf']), TTFont(FF.parent / row['source'])
        for tag, ok in allowed.items():
            a, b = vars(f[tag]), vars(base[tag])
            same = lambda x, y: vars(x) == vars(y) if hasattr(x, '__dict__') else x == y
            diff = {k for k in set(a) | set(b) if k not in ('ulUnicodeRange1', 'ulUnicodeRange2', 'ulUnicodeRange3', 'ulUnicodeRange4')
                    and not same(a.get(k), b.get(k))}
            if not row['jp']:
                diff -= {'usFirstCharIndex', 'usLastCharIndex', 'advanceWidthMax', 'minLeftSideBearing',
                         'minRightSideBearing', 'xMaxExtent', 'numberOfHMetrics', 'usMaxContext',
                         'ulCodePageRange1', 'ulCodePageRange2'}
            assert diff <= ok, (row['ttf'], tag, diff)
        assert f['hhea'].descent == f['OS/2'].sTypoDescender == -400
    print('hhea / OS/2: only the descender differs from the RC3 source')


if __name__ == '__main__':
    metrics_only_descender()
    verify.main()
    sys.argv = [sys.argv[0], 'LightItalic', 'SemiBoldItalic']
    italic.main()
