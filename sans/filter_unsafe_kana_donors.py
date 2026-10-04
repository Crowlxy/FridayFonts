"""Drop legacy fit strengths whose donor fails strict bytecode execution."""
import json
from fontTools.ttLib import TTFont
from kana_hint_common import *
from build_kana_trial_2_2 import build

data=json.loads((WORK/'settings.json').read_text());rejects=[]
for style in ['Regular','Medium','Bold']:
    path=ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{style}.ttf';f=TTFont(path)
    rows={g['glyph']:g for g in data['glyphs'] if g['style']==style}
    for px in range(11,19):
        ff=face(path);r.FT.FT_Set_Pixel_Sizes(ff,0,px)
        for n in sorted(rows):
            error=r.FT.FT_Load_Glyph(ff,f.getGlyphID(n),4|8|128)
            if error:
                strength,phase=rows[n]['settings'][str(px)]
                rejects.append({'style':style,'glyph':n,'ppem':px,'donor_error':error,'old_strength':strength})
                rows[n]['settings'][str(px)]=[0,phase]
        r.FT.FT_Done_Face(ff)
    f.close()
data['unsafe_donor_filters']=rejects
data['policy']['phase_only_skips_legacy_program']=True
(WORK/'settings.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('Filtered strict donor failures:',len(rejects),flush=True)
build()
