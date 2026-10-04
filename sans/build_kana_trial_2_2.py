"""Build Friday Sans Kana Trial 2.201, leaving published 2.1 untouched."""
import copy,hashlib,json,shutil
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.ttProgram import Program
from kana_hint_common import *
from build_2_1 import rename

OUT=ROOT/'FridayFonts/sans/kana-trial-2.2'
FAMILY='Friday Sans Kana Trial'
PREFIX='FridaySansKanaTrial'

def save_trial(font,style):
    for sub in ['ttf','web']:(OUT/sub).mkdir(parents=True,exist_ok=True)
    path=OUT/f'ttf/{PREFIX}-{style}.ttf';font.flavor=None;font.save(path)
    font.flavor='woff2';font.save(OUT/f'web/{PREFIX}-{style}.woff2');font.flavor=None
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    settings=json.loads((WORK/'settings.json').read_text())
    manifest=json.loads((ROOT/'FridayFonts/sans/dist-2.1/font-manifest.json').read_text())
    records=[]
    for style in ['Regular','Medium','Bold']:
        base_path=ROOT/f'FridayFonts/sans/grid-trial-2.1/ttf/FridaySans-{style}.ttf'
        font=TTFont(base_path,recalcTimestamp=False)
        native_path=ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{style}.ttf'
        native=TTFont(native_path);storage=font['maxp'].maxStorage
        assert all(font.getTableData(t)==native.getTableData(t) for t in ['fpgm','prep','cvt '])
        stable_record=next(r for r in manifest if r['style']==style)
        private_components=[]
        # ccmp can scale/reposition components before their hints run. Retain
        # their original small-ring rendering with private unhinted bodies.
        # The visible outline, cmap, substitution glyph and metrics stay the
        # same; only the component reference points to an identical copy.
        for pair in stable_record['shaping']['ccmp_pairs']:
            composite=font['glyf'][pair['glyph']]
            component=composite.components[0];body=component.glyphName
            name='jp.ccmp.component.'+body+'.outline'
            assert not code(font,body)
            glyph=copy.deepcopy(font['glyf'][body]);glyph.program=Program();glyph.program.fromBytecode(b'')
            font.setGlyphOrder(font.getGlyphOrder()+[name]);font['glyf'][name]=glyph
            font['hmtx'][name]=font['hmtx'][body];font['vmtx'][name]=font['vmtx'][body]
            component.glyphName=name
            private_components.append({'glyph':name,'original_body':body,'composition':pair['glyph']})
        changed=[];unchanged=[]
        for row in settings['glyphs']:
            if row['style']!=style:continue
            n=row['glyph'];params={int(k):v for k,v in row['settings'].items()}
            if not any(s or p for s,p in params.values()):unchanged.append(n);continue
            g=font['glyf'][n];assert g.getCoordinates(font['glyf'])==native['glyf'][n].getCoordinates(native['glyf']),n
            p=Program();p.fromBytecode(controlled_program(code(native,n),len(g.coordinates),params,storage))
            g.program=p;changed.append(n)
        font['maxp'].maxStorage+=2;font['maxp'].maxStackElements+=12
        rename(font,FAMILY,'2.201',2.201)
        font['name'].setName('Small-size kana Y fitting with restrained density and preserved outlines. Windows trial.',10,3,1,0x409)
        digest=save_trial(font,style)
        records.append({'style':style,'ttf_sha256':digest,'source_sha256':hashlib.sha256(base_path.read_bytes()).hexdigest(),
                        'native_sha256':hashlib.sha256(native_path.read_bytes()).hexdigest(),
                        'kana_programs':len(changed),'changed_glyphs':changed,'unchanged_kana_glyphs':unchanged,
                        'shaping':stable_record['shaping'],'private_unhinted_components':private_components,
                        'policy':settings['policy'],'family':FAMILY,'windows_verified':False})
        print(style,len(changed),'kana programs built',flush=True)
        font.close();native.close()
    for p in (ROOT/'FridayFonts/sans/dist-2.1').glob('*'):
        if p.is_file() and (p.name.startswith('LICENSE') or p.name.startswith('OFL')):shutil.copy2(p,OUT/p.name)
    if (ROOT/'FridayFonts/sans/dist-2.1/licenses').exists():shutil.copytree(ROOT/'FridayFonts/sans/dist-2.1/licenses',OUT/'licenses',dirs_exist_ok=True)
    (OUT/'font-manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    (OUT/'hint-settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':build()
