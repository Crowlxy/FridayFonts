"""Select restrained kana fits; local FreeType diagnostics, not Windows proof.

All encoded fullwidth kana, their vertical forms and marks are considered.
Selection requires <=5% ink change, no lost alpha128 counter and <=0.5px Y
movement. A fit must reduce low-alpha ink by at least 0.75 percentage points.
"""
import json
from fontTools.ttLib import TTFont
from kana_hint_common import *

def delta(d,strength,phase):
    # TrueType MUL rounds a signed fixed-point product to the nearest integer.
    value=np.sign(d)*((np.abs(d)*strength+32)//64)
    return np.clip(np.clip(value,-24,24)+phase,-32,32)

result=[]
for style in ['Regular','Medium','Bold']:
    bp=ROOT/f'FridayFonts/sans/grid-trial-2.1/ttf/FridaySans-{style}.ttf'
    npth=ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{style}.ttf'
    base=TTFont(bp);native=TTFont(npth);bf=face(bp);nf=face(npth)
    reverse={n:chr(cp) for cp,n in charset(base).items()}
    for index,n in enumerate(sorted(kana_names(base))):
        assert code(native,n) and base['glyf'][n].numberOfContours>0
        gid=base.getGlyphID(n);ngid=native.getGlyphID(n);settings={};diagnostics=[]
        for px in range(11,19):
            org=points(bf,gid,px);fit=points(nf,ngid,px)
            assert np.array_equal(org[:,0],fit[:,0]),(style,n,px,'unexpected X hints')
            a=raster(bf,gid,px)[0];a_ink=float(a.sum());a_soft=softness(a);a_holes=holes(a)
            best=(0.,0,0,a_soft,0.,a_holes)
            for strength in (0,16,32,48,64):
                for phase in (-16,-8,0,8,16):
                    coords=org.copy();shift=delta(fit[:,1]-org[:,1],strength,phase);coords[:,1]+=shift
                    b=render_points(bf,gid,px,coords)[0]
                    ink=(float(b.sum())/a_ink-1)*100 if a_ink else 0
                    soft=softness(b);h=holes(b)
                    if abs(ink)>5 or h<a_holes or not b.size:continue
                    benefit=a_soft-soft
                    if benefit<.75:continue
                    score=benefit-abs(ink)*.35-np.max(np.abs(shift))/64*.25-strength/64*.15
                    if score>best[0]:best=(float(score),strength,phase,soft,float(ink),h)
            _,strength,phase,soft,ink,h=best
            settings[str(px)]=[strength,phase]
            diagnostics.append({'ppem':px,'baseline_softness':a_soft,'trial_softness':soft,'ink_change_percent':ink,'alpha128_counters':[a_holes,h]})
        result.append({'style':style,'glyph':n,'char':reverse.get(n),'settings':settings,'initial_candidate_diagnostics':diagnostics})
        if (index+1)%100==0:print(style,index+1,'kana considered',flush=True)
    r.FT.FT_Done_Face(bf);r.FT.FT_Done_Face(nf);base.close();native.close()
    print(style,'done',flush=True)
(WORK/'settings.json').write_text(json.dumps({'policy':{'range':[11,18],'max_ink_change_percent':5,'max_y_shift_pixels':.5,'max_phase_pixels':.25,'min_softness_improvement_pp':.75,'counter_threshold':128,'engine':'FreeType '+r.version,'windows_verified':False},'glyphs':result},ensure_ascii=False,indent=2)+'\n')
for style in ['Regular','Medium','Bold']:
    for px in [12,14,16]:
        rows=[d for g in result if g['style']==style and g['char'] and unicodedata.category(g['char'])=='Lo' for d in g['initial_candidate_diagnostics'] if d['ppem']==px]
        print(style,px,'low alpha medians',np.median([d['baseline_softness'] for d in rows]),np.median([d['trial_softness'] for d in rows]),'ink p10/50/90',np.percentile([d['ink_change_percent'] for d in rows],[10,50,90]),flush=True)
