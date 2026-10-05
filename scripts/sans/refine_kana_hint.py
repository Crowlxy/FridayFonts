"""Reject integer-selected fits that fail fractional-size density guards."""
import json
from collections import Counter
from fontTools.ttLib import TTFont
from kana_hint_common import *
from build_kana_trial_2_2 import OUT,build

data=json.loads((WORK/'settings.json').read_text());removed=[]
for style in ['Regular','Medium','Bold']:
    base_path=ROOT/f'FridayFonts/releases/archive/sans-grid-trial-2.1/ttf/FridaySans-{style}.ttf'
    trial_path=OUT/f'ttf/FridaySansKanaTrial-{style}.ttf'
    f=TTFont(base_path);bf=face(base_path);tf=face(trial_path)
    for row in data['glyphs']:
        if row['style']!=style:continue
        gid=f.getGlyphID(row['glyph'])
        for px in range(11,19):
            s,p=row['settings'][str(px)]
            if not (s or p):continue
            failures=[]
            for fraction in [-.5,-.4375,-.375,-.25,-.125,0,.125,.25,.375,.4375]:
                size=px+fraction
                a=fractional_raster(bf,gid,size)[0];b=fractional_raster(tf,gid,size)[0]
                ink=(float(b.sum())/float(a.sum())-1)*100 if a.sum() else 0
                if abs(ink)>5.05 or holes(b)<holes(a):
                    failures.append({'ppem':size,'ink':ink,'counters':[holes(a),holes(b)]})
            if failures:
                row['settings'][str(px)]=[0,0]
                removed.append({'style':style,'glyph':row['glyph'],'char':row['char'],'integer_ppem':px,'old_settings':[s,p],'failures':failures})
    r.FT.FT_Done_Face(bf);r.FT.FT_Done_Face(tf);f.close()
    print(style,'fractional guards complete',flush=True)
data['fractional_refinements']=data.get('fractional_refinements',[])+removed
data['policy']['fractional_guards']='Each integer bucket: -0.5, -0.4375, -0.375, -0.25, -0.125, 0, 0.125, 0.25, 0.375, 0.4375 ppem; <=5.05% ink change and no alpha128 counter loss'
(WORK/'settings.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Rejected size/glyph fits',len(removed),'by style',Counter(row['style'] for row in removed),flush=True)
build()
