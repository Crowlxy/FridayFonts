"""Check source parity, Plain-only-zero differences and non-JP subsetting."""
from pathlib import Path
import json, sys, subprocess, unicodedata as ud
import numpy as np
from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'FridayFonts/dist-mono-4.91'
sys.path.insert(0,str(ROOT/'FridayFonts-WindowsTest/tools'))
import font_raster as raster

def shape(path, text, features=None):
    args = ['hb-shape',str(path),'--output-format=json','--no-glyph-names',text]
    if features: args.append('--features='+features)
    return json.loads(subprocess.check_output(args,text=True))

def clean(v): return [{k:x for k,x in g.items() if k!='cl'} for g in v]

def main():
    rows=json.loads((OUT/'font-manifest.json').read_text());results=[]
    assert len(rows)==18
    assert not any(r['plain'] and not r['jp'] for r in rows)
    raster.interpreter(40)
    for row in rows:
        p=OUT/row['ttf'];f=TTFont(p);base=TTFont(ROOT/row['source']);cm=f.getBestCmap()
        assert not any('WinProof' in rec.toUnicode() for rec in f['name'].names)
        changed=[]
        for n in f.getGlyphOrder():
            expected={'zero':'zero.alt','zero.alt':'zero'}.get(n,n) if row['plain'] else n
            assert n in base['glyf']
            assert f['glyf'][n].getCoordinates(f['glyf'])==base['glyf'][expected].getCoordinates(base['glyf']), (p.name,n)
            a=getattr(f['glyf'][n],'program',None);b=getattr(base['glyf'][expected],'program',None)
            assert (a.getBytecode() if a else b'')==(b.getBytecode() if b else b''),(p.name,n)
            assert f['hmtx'][n]==base['hmtx'][expected]
            if 'vmtx' in f: assert f['vmtx'][n]==base['vmtx'][expected]
            if expected!=n:changed.append(n)
        for tag in ('fpgm','prep','cvt ','gasp'):
            assert f.getTableData(tag)==base.getTableData(tag),(p.name,tag)
        if row['jp']:
            for tag in ('GPOS','GDEF','OS/2','hhea','vhea'):
                assert f.getTableData(tag)==base.getTableData(tag),(p.name,tag)
            if not row['plain']:
                for tag in ('glyf','loca','hmtx','vmtx','GSUB','cmap'):
                    assert f.getTableData(tag)==base.getTableData(tag),(p.name,tag)
        assert shape(p,'0')[0]['g']==f.getGlyphID('zero')
        for feature in ('ss01','cv01'):
            assert shape(p,'0',feature+'=1')[0]['g']==f.getGlyphID('zero.alt')
        if row['plain']:
            assert shape(p,'0','zero=1')[0]['g']==f.getGlyphID('zero.alt')
        expected='zero.alt' if row['plain'] else 'zero'
        assert shape(p,'0\ufe00')[0]['g']==f.getGlyphID(expected)
        pairs=[(chr(c),ud.normalize('NFD',chr(c))) for c in cm if ud.normalize('NFC',chr(c))==chr(c)
               and ud.normalize('NFD',chr(c))!=chr(c) and all(ord(x) in cm for x in ud.normalize('NFD',chr(c)))]
        corpus=OUT/'reports'/'canonical-current.txt'
        corpus.write_text('\n'.join(s for pair in pairs for s in pair)+'\n')
        shaped=subprocess.check_output(['hb-shape',str(p),'--text-file='+str(corpus),'--output-format=json','--no-glyph-names'],text=True).splitlines()
        assert len(shaped)==len(pairs)*2
        for i,pair in enumerate(pairs):
            assert clean(json.loads(shaped[2*i]))==clean(json.loads(shaped[2*i+1])),(p.name,pair)
        # The JP glyph programs are inherited exactly from RC3. Raster-screen
        # every subset glyph at small sizes because subsetting changes IDs.
        sizes=(9,12,14,16,20,32) if not row['jp'] else (12,14,16)
        names=f.getGlyphOrder() if not row['jp'] else ['zero','zero.alt']
        face=raster.face(p);src=raster.face(ROOT/row['source']);checks=0
        for size in sizes:
            raster.size(face,size);raster.size(src,size)
            for n in names:
                expected={'zero':'zero.alt','zero.alt':'zero'}.get(n,n) if row['plain'] else n
                err,a=raster.bitmap(face,f.getGlyphID(n));err2,b=raster.bitmap(src,base.getGlyphID(expected))
                assert not err and not err2,(p.name,n,size,err,err2)
                assert raster.signature(a)==raster.signature(b),(p.name,n,size)
                checks+=1
        raster.FT.FT_Done_Face(face);raster.FT.FT_Done_Face(src)
        results.append(dict(file=p.name,source_outline_hint_metric_parity=True,changed_zero_glyphs=changed,
                            canonical_pairs=len(pairs),canonical_mismatches=0,raster_sizes=list(sizes),
                            source_raster_parity_cases=checks,raster_errors=0,
                            zero_features_and_standardized_variation=True))
        f.close();base.close();print(p.name,'PASS',checks,'rasters',len(pairs),'canonical pairs',flush=True)
    (OUT/'reports/validation.json').write_text(json.dumps(dict(results=results,
      limitation='FreeType and HarfBuzz on macOS; no new Windows native rendering certification for 4.91. Upright RC3 data preserved; italic repairs independently applied and tested.'),indent=2)+'\n')
    corpus.unlink()
    proof(rows)

def proof(rows):
    im=Image.new('RGB',(1180,2200),'#f7f7f5');d=ImageDraw.Draw(im)
    latin='0O1Il  {value: 0123456789}  != <= ->  abc XYZ'
    international='Caf\u00e9 \u0100\u0101 \u0110\u0111 \u0178\u017f  \u0391\u03b2\u03b3\u03a9  \u0410\u0431\u0432\u042f  $ \u20ac \u00a5 \u00a3'
    terminal='\u250c\u2500\u252c\u2500\u2510 \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588  \u2190\u2191\u2192\u2193  \u00b1\u00d7\u00f7\u2212'
    y=16
    for row in rows:
        d.text((20,y),row['family']+' / '+row['style'],fill='#222222');y+=22
        path=OUT/row['ttf'];f=TTFont(path);face=raster.face(path);cm=f.getBestCmap();raster.size(face,20)
        lines=[latin,international, '日本語 ひらがな カタカナ 𠮷 きぎ とど フブプ ０１２' if row['jp'] else terminal]
        for line in lines:
            x=24;baseline=y+20
            for c in line:
                if ord(c) not in cm:continue
                _,bm=raster.bitmap(face,f.getGlyphID(cm[ord(c)]));a,left,top=bm
                if a.size:
                    mask=Image.fromarray(a);im.paste('#151515',(round(x)+left,baseline-top),mask)
                x+=f['hmtx'][cm[ord(c)]][0]/f['head'].unitsPerEm*20
            y+=24
        y+=13;raster.FT.FT_Done_Face(face);f.close()
    im.crop((0,0,1180,y+10)).save(OUT/'reports/proof.png')

if __name__=='__main__': main()
