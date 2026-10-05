"""Verify geometry, hint isolation, shaping and restrained kana rasters."""
import hashlib,json,subprocess
from fontTools.ttLib import TTFont
from kana_hint_common import *
from build_kana_trial_2_2 import OUT

SIZES=[9,10,11,12,13,14,15,16,17,18,19,20,24,32]
FRACTIONS=[-.5,-.4375,-.375,-.25,-.125,0,.125,.25,.375,.4375]

def signature(bm):return (bm[0].shape,bm[0].tobytes(),bm[1],bm[2])
def shape(p,text,features=None):
    args=['hb-shape',str(p),text,'--output-format=json']
    if features:args+=['--features='+features]
    return json.loads(subprocess.check_output(args,text=True))

def main():
    records=[];metrics=[];fractional=[];secondary=[];strict=[]
    manifest=json.loads((OUT/'font-manifest.json').read_text())
    property_value=C.c_uint(40)
    assert r.FT.FT_Property_Set(r.library,b'truetype',b'interpreter-version',C.byref(property_value))==0
    for style in ['Regular','Medium','Bold']:
        bp=ROOT/f'FridayFonts/releases/archive/sans-grid-trial-2.1/ttf/FridaySans-{style}.ttf';tp=OUT/f'ttf/FridaySansKanaTrial-{style}.ttf'
        b=TTFont(bp,checkChecksums=2);t=TTFont(tp,checkChecksums=2)
        order=t.getGlyphOrder();baseline_order=b.getGlyphOrder()
        assert order[:len(baseline_order)]==baseline_order
        private=next(v for v in manifest if v['style']==style)['private_unhinted_components']
        component_map={v['glyph']:v['original_body'] for v in private}
        assert len(component_map)==14 and len(order)==len(baseline_order)+14
        changed=[]
        for n in order:
            source=component_map.get(n,n)
            assert b['glyf'][source].getCoordinates(b['glyf'])==t['glyf'][n].getCoordinates(t['glyf']),(style,n,'outline')
            assert b['hmtx'][source]==t['hmtx'][n] and b['vmtx'][source]==t['vmtx'][n],n
            if n not in component_map and code(b,n)!=code(t,n):changed.append(n)
        assert set(changed)<=kana_names(b)
        affected=set(changed)
        for _ in range(4):
            affected.update(n for n in order if t['glyf'][n].isComposite() and any(c.glyphName in affected for c in t['glyf'][n].components))
        for tag in ['hhea','vhea','OS/2','fpgm','prep','cvt ','gasp','GPOS','GSUB','GDEF','cmap']:
            assert b.getTableData(tag)==t.getTableData(tag),(style,tag)
        assert t['name'].getDebugName(16)=='Friday Sans Kana Trial'
        for tag in t.keys():
            if tag!='GlyphOrder':t[tag].compile(t)
        w=TTFont(OUT/f'web/FridaySansKanaTrial-{style}.woff2')
        for tag in ['glyf','fpgm','prep','cvt ','GPOS','GSUB','GDEF','cmap','hmtx','vmtx']:
            assert w.getTableData(tag)==t.getTableData(tag),(style,'woff2',tag)
        w.close()
        bf=face(bp);tf=face(tp);render_cases=0;isolated=0
        for px in SIZES:
            for gid,n in enumerate(order):
                bm=raster(tf,gid,px);render_cases+=1
                g=t['glyf'][n]
                coords=g.getCoordinates(t['glyf'])[0]
                if len(coords):assert bm[0].size and bm[0].sum(),(style,px,n,'empty')
                if n not in affected or px<11 or px>18:
                    source=component_map.get(n,n)
                    assert signature(raster(bf,b.getGlyphID(source),px))==signature(bm),(style,n,px,'isolated raster')
                    isolated+=1
        for px in [11,12,13,14,15,16,17,18]:
            for group,test in [('hiragana',(0x3040,0x309f)),('katakana',(0x30a0,0x30ff)),('small_katakana',(0x31f0,0x31ff))]:
                pairs=[(cp,n) for cp,n in charset(t).items() if test[0]<=cp<=test[1] and unicodedata.category(chr(cp))=='Lo']
                values=[];soft=[[],[]];items=[]
                for cp,n in pairs:
                    gid=t.getGlyphID(n);a=raster(bf,gid,px)[0];bb=raster(tf,gid,px)[0]
                    ink=(float(bb.sum())/float(a.sum())-1)*100
                    values.append(ink);soft[0].append(softness(a));soft[1].append(softness(bb))
                    assert abs(ink)<=5.05 and holes(bb)>=holes(a),(style,chr(cp),px,ink,'integer guard')
                    items.append({'char':chr(cp),'ink_change':ink,'softness':[softness(a),softness(bb)]})
                metrics.append({'style':style,'group':group,'ppem':px,'n':len(pairs),'low_alpha_ink_median_percent':[float(np.median(v)) for v in soft],
                                'ink_change_p10_median_p90':list(map(float,np.percentile(values,[10,50,90]))),'max_abs_ink_change':float(max(map(abs,values))), 'glyphs':items})
        cases=0;largest=0.;worst=[];max_move=0
        for n in kana_names(t):
            gid=t.getGlyphID(n)
            for px in range(11,19):
                a=points(bf,gid,px);bb=points(tf,gid,px)
                assert np.array_equal(a[:,0],bb[:,0]),(style,n,px,'X moved')
                move=int(np.max(np.abs(bb[:,1]-a[:,1])))
                assert move<=32,(style,n,px,move);max_move=max(max_move,move)
                for fraction in FRACTIONS:
                    size=px+fraction;a=fractional_raster(bf,gid,size)[0];bb=fractional_raster(tf,gid,size)[0]
                    ink=(float(bb.sum())/float(a.sum())-1)*100
                    assert abs(ink)<=5.05 and holes(bb)>=holes(a),(style,n,size,ink,'fractional guard')
                    largest=max(largest,abs(ink));cases+=1
        fractional.append({'style':style,'cases':cases,'max_abs_ink_change':largest,'max_point_y_move_64ths':max_move,'lost_alpha128_counters':0,'range':[10.5,18.4375]})
        record=next(v for v in manifest if v['style']==style)
        composite=[]
        for pair in record['shaping']['ccmp_pairs']:
            text=pair['base']+'\u309a';sh=shape(tp,text)
            assert sh==shape(bp,text) and len(sh)==1
            gid=t.getGlyphID(sh[0]['g'])
            for px in range(11,19):
                a=raster(bf,gid,px)[0];bb=raster(tf,gid,px)[0]
                assert bb.size and bb.sum(),(style,text,px,'empty composition')
                assert holes(bb)>=holes(a),(style,text,px,'lost composition counter')
                composite.append({'text':text,'ppem':px,'ink_change':float((bb.sum()/a.sum()-1)*100),'counters':[holes(a),holes(bb)]})
        for text in ['あいうえお きさふとや ぎざぷどゃ','アイウエオ シツソン リルレロ','がぱ カ゚キ き゚ㇷ゚','AV To 0123456789','𠮷野家 𠮷\U000e0100','ｶﾀｶﾅ ｶﾞﾊﾟ']:
            assert shape(tp,text)==shape(bp,text),(style,text,'shaping')
        assert len({g['ax'] for g in shape(tp,'0123456789','tnum=1')})==1
        strict_cases=0
        for px in range(11,19):
            # Fresh size contexts avoid the old prep's inherited strict-only
            # reference failure on some size transitions. New kana programs
            # themselves must pass FT_LOAD_PEDANTIC without any such error.
            sf=face(tp)
            for n in changed+[v['glyph'] for v in record['shaping']['ccmp_pairs']]:
                raster(sf,t.getGlyphID(n),px,4|8|128);strict_cases+=1
            r.FT.FT_Done_Face(sf)
        strict.append({'style':style,'pedantic_kana_cases':strict_cases,'new_glyph_program_errors':0})
        records.append({'style':style,'sha256':hashlib.sha256(tp.read_bytes()).hexdigest(),'glyphs':len(order),'changed_kana_programs':len(changed),
                        'affected_composite_glyphs':sorted(affected-set(changed)),
                        'render_cases':render_cases,'raster_errors':0,'isolated_raster_matches':isolated,'all_outlines_and_metrics_preserved':True,'composites':composite})
        r.FT.FT_Done_Face(bf);r.FT.FT_Done_Face(tf);b.close();t.close()
        print(style,'full-font and fractional guards passed',flush=True)
    # Older bytecode interpreter as an independent compatibility diagnostic.
    # Its result is not Microsoft GDI emulation and has a different ink profile.
    property_value=C.c_uint(35)
    assert r.FT.FT_Property_Set(r.library,b'truetype',b'interpreter-version',C.byref(property_value))==0
    for style in ['Regular','Medium','Bold']:
        bp=ROOT/f'FridayFonts/releases/archive/sans-grid-trial-2.1/ttf/FridaySans-{style}.ttf';tp=OUT/f'ttf/FridaySansKanaTrial-{style}.ttf'
        f=TTFont(tp);bf=face(bp);tf=face(tp);cases=0;max_move=0
        names=kana_names(f)|{row['glyph'] for row in next(v for v in manifest if v['style']==style)['shaping']['ccmp_pairs']}
        for n in names:
            gid=f.getGlyphID(n)
            for px in SIZES:
                bb=raster(tf,gid,px)[0];assert bb.size and bb.sum(),(style,n,px,'interpreter35')
                if not f['glyf'][n].isComposite():
                    a=points(bf,gid,px);b=points(tf,gid,px)
                    assert np.array_equal(a[:,0],b[:,0])
                    move=int(np.max(np.abs(b[:,1]-a[:,1])));assert move<=32
                    max_move=max(max_move,move)
                cases+=1
        secondary.append({'style':style,'interpreter':35,'render_cases':cases,'raster_errors':0,'max_point_y_move_64ths':max_move})
        r.FT.FT_Done_Face(bf);r.FT.FT_Done_Face(tf);f.close()
    property_value=C.c_uint(40);r.FT.FT_Property_Set(r.library,b'truetype',b'interpreter-version',C.byref(property_value))
    result={'engine':'FreeType '+r.version,'interpreter':40,'windows_verified':False,'faces':records,'matched_metrics':metrics,'fractional_guards':fractional,'secondary_interpreter':secondary,'strict_new_kana_programs':strict,
            'inherited_global_limit':'Strict FreeType PEDANTIC execution can report reference error 134 on certain size transitions with unchanged legacy programs in the 2.1 baseline too. Normal rendering checks pass. Global programs are unchanged; newly added kana programs are checked separately in fresh size contexts.'}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('KANA TRIAL CHECKS PASSED',sum(r['render_cases'] for r in records),'full-font cases',flush=True)

if __name__=='__main__':main()
