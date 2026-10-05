"""Keep U+309A unhinted: its ccmp uses scale the same component down."""
import json
from fontTools.ttLib import TTFont
from kana_hint_common import *
from build_kana_trial_2_2 import build,OUT

data=json.loads((WORK/'settings.json').read_text())
for style in ['Regular','Medium','Bold']:
    f=TTFont(ROOT/f'FridayFonts/releases/archive/sans-grid-trial-2.1/ttf/FridaySans-{style}.ttf');ring=f.getBestCmap()[0x309a];f.close()
    for row in data['glyphs']:
        if row['style']==style and row['glyph']==ring:row['settings']={str(px):[0,0] for px in range(11,19)}
data['policy']['unhinted_combining_ring']='U+309A: retain original raster for scaled ccmp components. Precomposed voiced/half-voiced kana still use their own restrained fits.'
(WORK/'settings.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
build()
manifest=json.loads((OUT/'font-manifest.json').read_text());failures=[]
for style in ['Regular','Medium','Bold']:
    bp=ROOT/f'FridayFonts/releases/archive/sans-grid-trial-2.1/ttf/FridaySans-{style}.ttf';tp=OUT/f'ttf/FridaySansKanaTrial-{style}.ttf'
    f=TTFont(tp);bf=face(bp);tf=face(tp)
    for pair in next(row for row in manifest if row['style']==style)['shaping']['ccmp_pairs']:
        gid=f.getGlyphID(pair['glyph'])
        for px in range(11,19):
            for fraction in [-.5,-.25,0,.25,.4375]:
                size=px+fraction;a=fractional_raster(bf,gid,size)[0];b=fractional_raster(tf,gid,size)[0]
                if holes(b)<holes(a):failures.append((style,pair['base'],size,holes(a),holes(b)))
    r.FT.FT_Done_Face(bf);r.FT.FT_Done_Face(tf);f.close()
print('Composite counter changes:',failures,flush=True)
assert not failures
