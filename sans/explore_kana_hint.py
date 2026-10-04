"""Measure softened native kana fits against the unchanged 2.1 glyphs."""
import json
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.ttProgram import Program
from kana_hint_common import *

rows=[];summary=[]
for style in ['Regular','Medium','Bold']:
    base_path=ROOT/f'FridayFonts/sans/grid-trial-2.1/ttf/FridaySans-{style}.ttf'
    native=TTFont(ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{style}.ttf')
    base=TTFont(base_path);names=kana_names(base);cm=charset(base)
    compatible=[];missing=[]
    for n in sorted(names):
        if n not in native['glyf'] or not code(native,n):missing.append(n);continue
        assert base['glyf'][n].getCoordinates(base['glyf'])==native['glyf'][n].getCoordinates(native['glyf']),n
        assert base['glyf'][n].numberOfContours>0,n
        compatible.append(n)
    bf=face(base_path)
    for strength in [16,32,48,64]:
        f=TTFont(base_path)
        for n in compatible:
            g=f['glyf'][n];p=Program();p.fromBytecode(gated_program(code(native,n),len(g.coordinates),strength))
            g.program=p
        f['maxp'].maxStackElements+=12
        path=WORK/f'{style}-s{strength}.ttf';f.save(path);ff=face(path)
        for px in range(11,19):
            values=[];soft=[]
            for cp,n in cm.items():
                gid=f.getGlyphID(n);a=raster(bf,gid,px)[0];b=raster(ff,gid,px)[0]
                ink=float((b.sum()/a.sum()-1)*100) if a.sum() else 0
                change=softness(b)-softness(a)
                row={'style':style,'strength':strength,'px':px,'cp':cp,'char':chr(cp),'glyph':n,'ink_change':ink,'softness_change':change,'softness_base':softness(a),'softness_trial':softness(b)}
                rows.append(row);values.append(ink);soft.append(change)
            summary.append({'style':style,'strength':strength,'px':px,'ink_p10_median_p90':list(map(float,np.percentile(values,[10,50,90]))),'ink_abs_max':float(max(abs(x) for x in values)),'softness_change_median':float(np.median(soft))})
        r.FT.FT_Done_Face(ff);f.close()
        print(style,strength,'done',flush=True)
    r.FT.FT_Done_Face(bf)
    print(style,'compatible',len(compatible),'missing',missing,flush=True)
    base.close();native.close()
(WORK/'exploration.json').write_text(json.dumps({'summary':summary,'rows':rows},ensure_ascii=False,indent=2)+'\n')
for s in summary:
    if s['px'] in (12,14,16):print(s)
