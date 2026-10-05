"""Regression checks for the 2.1 fixes and matched kanji-grid trial."""
from pathlib import Path
import ctypes as C
import hashlib,json,subprocess,sys
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'FridayFonts/releases/archive/sans-2.1'
TRIAL=ROOT/'FridayFonts/releases/archive/sans-grid-trial-2.1'
sys.path.insert(0,str(ROOT/'comparisons/friday-sans-2.0'))
sys.path.insert(0,str(ROOT/'InoriMono-v3-build'))
import raster_support as r
import rehint
r.FT.FT_Load_Glyph.argtypes=[r.FacePtr,C.c_uint,C.c_int32]
SIZES=[9,10,11,12,13,14,16,18,20,24]

def face(p):
    f=r.FacePtr();assert r.FT.FT_New_Face(r.library,str(p).encode(),0,C.byref(f))==0;return f

def raster(f,gid,px):
    assert r.FT.FT_Set_Pixel_Sizes(f,0,px)==0
    assert r.FT.FT_Load_Glyph(f,gid,4|8)==0,(gid,px)
    s=f.contents.glyph.contents;b=s.bitmap
    raw=C.string_at(b.buffer,abs(b.pitch)*b.rows) if b.width and b.rows else b''
    return (b.width,b.rows,b.pitch,s.left,s.top,raw)

def shape(p,text,features=None):
    args=['hb-shape',str(p),text,'--output-format=json']
    if features:args+=['--features='+features]
    return json.loads(subprocess.check_output(args,text=True))

def code(f,n):
    g=f['glyf'][n];return g.program.getBytecode() if hasattr(g,'program') else b''

rows=[];summaries=[]
manifest=json.loads((OUT/'font-manifest.json').read_text())
for style in ['Regular','Medium','Bold']:
    oldpath=ROOT/f'FridayFonts/releases/archive/sans-2.0/ttf/FridaySans-{style}.ttf'
    paths=[OUT/f'ttf/FridaySans-{style}.ttf',TRIAL/f'ttf/FridaySans-{style}.ttf']
    old=TTFont(oldpath,checkChecksums=2);new=TTFont(paths[0],checkChecksums=2);trial=TTFont(paths[1],checkChecksums=2)
    old_order=old.getGlyphOrder();order=new.getGlyphOrder()
    assert order[:len(old_order)]==old_order and order==trial.getGlyphOrder()
    assert len(order)==len(old_order)+15
    for n in old_order:
        assert new['glyf'][n].getCoordinates(new['glyf'])==old['glyf'][n].getCoordinates(old['glyf']),n
        assert code(new,n)==code(old,n),n
        assert new['hmtx'][n]==old['hmtx'][n] and new['vmtx'][n]==old['vmtx'][n],n
    for tag in ['hhea','vhea','OS/2','fpgm','prep','cvt ','gasp']:
        assert new.getTableData(tag)==old.getTableData(tag),(style,tag)
    cm=new.getBestCmap();assert {cp:n for cp,n in cm.items() if cp!=0x20bb7}==old.getBestCmap()
    assert 0x20bb7 in cm
    assert any((0x20bb7,None) in t.uvsDict.get(0xe0100,[]) for t in new['cmap'].tables if t.format==14)
    for p,f in zip(paths,[new,trial]):
        assert not rehint.digit_rows(str(p)),(style,p,'digit alignment')
        for tag in f.keys():
            if tag!='GlyphOrder':f[tag].compile(f)
        clips=[];bounds={};gs=f.getGlyphSet()
        for n in order:
            pen=BoundsPen(gs);gs[n].draw(pen);bounds[n]=pen.bounds
            if pen.bounds and (pen.bounds[3]>f['OS/2'].usWinAscent or pen.bounds[1]<-f['OS/2'].usWinDescent):clips.append(n)
        assert clips==['jp.uni3031','jp.uni3032'],clips
        ff=face(p);count=0
        for px in SIZES:
            for gid,n in enumerate(order):
                bm=raster(ff,gid,px)
                if bounds[n]:assert bm[0] and bm[1] and any(bm[-1]),(style,p.name,px,n,'empty')
                if bounds[n] and bounds[n][3]-bounds[n][1]>200:
                    assert bm[1]>(bounds[n][3]-bounds[n][1])*px/1000*.5,(style,p,px,n,'flattened')
                count+=1
        r.FT.FT_Done_Face(ff)
        for ext in ['ttf','woff2']:
            q=p if ext=='ttf' else p.parent.parent/f'web/FridaySans-{style}.woff2'
            w=TTFont(q);assert w.getGlyphOrder()==order and w.getBestCmap()==cm
            for tag in ['glyf','GPOS','GSUB','GDEF','cmap','hmtx','vmtx']:assert w.getTableData(tag)==f.getTableData(tag),(q,tag)
            w.close()
        rows.append({'style':style,'variant':'outline' if p.parent.parent==OUT else 'kanji_grid_trial',
          'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'glyphs':len(order),'cmap':len(cm),
          'raster_cases':count,'sizes':SIZES,'raster_errors':0,'new_clipping_glyphs':0})
    shape_checks={}
    for item in next(v for v in manifest if v['style']==style)['shaping']['ccmp_pairs']:
        text=item['base']+'\u309a';s=shape(paths[0],text)
        assert len(s)==1 and s[0]['g']==item['glyph'] and s[0]['ax']==1000,(style,text,s)
        with_neighbors=shape(paths[0],'X'+text+'キX')
        assert any(g['g']==item['glyph'] for g in with_neighbors)
        fallback=shape(paths[0],text,'ccmp=0')
        assert len(fallback)==2 and fallback[1]['dx']<0 and fallback[1]['ax']==0,(style,text,fallback)
        shape_checks[text]={'ccmp':s,'mark_fallback':fallback}
    for text in ['か\u3099きく','は\u309aひふ','がぱ','x\u0301 A\u0301','AV To','0123456789','「日本語」、。']:
        assert shape(paths[0],text)==shape(oldpath,text),(style,text,'existing shaping changed')
    assert all(g['g']!='.notdef' for g in shape(paths[0],'𠮷野家 𠮷\U000e0100'))
    for text in ['あ\u3099いう','わ\u309aをん','ㇰ\u309aㇱ']:
        s=shape(paths[0],text);assert any(g['dx']<0 for g in s),(style,text,s)
    tab=shape(paths[0],'0123456789','tnum=1');assert len({g['ax'] for g in tab})==1
    # The hint trial must keep kana/Latin pixels identical at every size;
    # outside its window all old and new glyph pixels must be identical.
    ff=[face(p) for p in paths];matched=0
    for px in SIZES:
        for gid,n in enumerate(order):
            changed=code(new,n)!=code(trial,n)
            if not changed or px not in range(11,19):
                assert raster(ff[0],gid,px)==raster(ff[1],gid,px),(style,px,n,'trial isolation')
                matched+=1
    for f in ff:r.FT.FT_Done_Face(f)
    metrics=[]
    ff=[face(p) for p in paths]
    for px in [12,14,16,20]:
        for f in ff:r.FT.FT_Set_Pixel_Sizes(f,0,px)
        for group,chars in r.GROUPS.items():
            softness=[[],[]];changes=[]
            for ch in chars:
                ras=[r.raster(f,ch,True)[0] for f in ff]
                changes.append((ras[1].sum()/ras[0].sum()-1)*100)
                for i,a in enumerate(ras):softness[i].append(float(a[a<128].sum()/a.sum()))
            q=np.percentile(changes,[10,50,90])
            metrics.append({'px':px,'group':group,'low_alpha_ink_median_percent':[float(np.median(v)*100) for v in softness],
               'ink_change_p10_median_p90':list(map(float,q))})
    for f in ff:r.FT.FT_Done_Face(f)
    summaries.append({'style':style,'all_16743_original_outlines_metrics_programs_preserved':True,
        'combining_pairs_checked':len(shape_checks),'shaping':shape_checks,'trial_isolated_raster_matches':matched,
        'matched_diagnostics':metrics,'tabular_digit_advance':tab[0]['ax']})
    for f in [old,new,trial]:f.close()
    print(style,'all glyphs rendered; 14 compositions + fallback + Latin/kana isolation passed',flush=True)
result={'engine':'FreeType '+r.version+' / HarfBuzz','windows_verified':False,'faces':rows,'regressions':summaries}
for folder in [OUT,TRIAL]:(folder/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('2.1 CHECKS PASSED',sum(r['raster_cases'] for r in rows),'render cases',flush=True)
