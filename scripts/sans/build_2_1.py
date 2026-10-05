"""Incremental Friday Sans 2.1 fixes; keep release 2.0 immutable.

Japanese shaping is built from the current kana and Noto's own ccmp pairs.
The optional grid trial restores only original kanji hints, at 11-18 ppem.
"""
from pathlib import Path
import copy, hashlib, json, pickle, shutil, sys, unicodedata
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.misc.transform import Transform
from fontTools.otlLib.builder import buildAnchor, buildLookup, buildMarkBasePosSubtable

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'FridayFonts/releases/archive/sans-2.0'
OUT=ROOT/'FridayFonts/releases/archive/sans-2.1'
TRIAL=ROOT/'FridayFonts/releases/archive/sans-grid-trial-2.1'
sys.path.insert(0,str(ROOT/'InoriMono-v3-build'))
sys.path.insert(0,str(ROOT/'InoriMono-v3-build/tools'))
import build_inori_v3 as mono
import shapes

STYLES=['Regular','Medium','Bold']
EXTRA_CODEPOINTS={0x20BB7}  # 𠮷: explicitly required for everyday personal names.

def rec(gs,n):
    p=DecomposingRecordingPen(gs);gs[n].draw(p);return p.value

def bounds(font,n):return shapes.bbox(rec(font.getGlyphSet(),n))

def append_glyph(font,name,glyph,advance=1000):
    if name in font.getGlyphOrder():return name
    order=list(font.getGlyphOrder());order.append(name);font.setGlyphOrder(order)
    font['glyf'][name]=glyph;glyph.recalcBounds(font['glyf'])
    font['hmtx'][name]=(advance,getattr(glyph,'xMin',0))
    sample=font.getBestCmap()[ord('日')]
    origin=font['vmtx'][sample][1]+font['glyf'][sample].yMax
    font['vmtx'][name]=(1000,origin-getattr(glyph,'yMax',0))
    return name

def attach_feature(font,table_tag,tag,lookup,scripts):
    table=font[table_tag].table
    table.LookupList.Lookup.append(lookup);table.LookupList.LookupCount=len(table.LookupList.Lookup)
    li=table.LookupList.LookupCount-1
    feature=next((i for i,f in enumerate(table.FeatureList.FeatureRecord) if f.FeatureTag==tag),None)
    if feature is None:
        fr=ot.FeatureRecord();fr.FeatureTag=tag;fr.Feature=ot.Feature();fr.Feature.FeatureParams=None
        fr.Feature.LookupListIndex=[];fr.Feature.LookupCount=0
        table.FeatureList.FeatureRecord.append(fr);feature=len(table.FeatureList.FeatureRecord)-1
    f=table.FeatureList.FeatureRecord[feature].Feature
    f.LookupListIndex=list(f.LookupListIndex)+[li];f.LookupCount=len(f.LookupListIndex)
    table.FeatureList.FeatureCount=len(table.FeatureList.FeatureRecord)
    have={s.ScriptTag:s for s in table.ScriptList.ScriptRecord}
    for script in scripts:
        if script not in have:
            sr=ot.ScriptRecord();sr.ScriptTag=script;sr.Script=ot.Script()
            sr.Script.DefaultLangSys=None;sr.Script.LangSysRecord=[];sr.Script.LangSysCount=0
            table.ScriptList.ScriptRecord.append(sr);have[script]=sr
        sr=have[script]
        if sr.Script.DefaultLangSys is None:
            ls=ot.LangSys();ls.LookupOrder=None;ls.ReqFeatureIndex=0xFFFF;ls.FeatureIndex=[];ls.FeatureCount=0
            sr.Script.DefaultLangSys=ls
        for ls in [sr.Script.DefaultLangSys]+[l.LangSys for l in sr.Script.LangSysRecord]:
            if feature not in ls.FeatureIndex:ls.FeatureIndex=list(ls.FeatureIndex)+[feature]
            ls.FeatureCount=len(ls.FeatureIndex)
    table.ScriptList.ScriptRecord.sort(key=lambda s:s.ScriptTag)
    table.ScriptList.ScriptCount=len(table.ScriptList.ScriptRecord)

def ring_parts(record):
    """Identify the outer ring and its counter by concentric bounding boxes."""
    parts=shapes.contours(record);boxes=[shapes.bbox(p) for p in parts]
    for i,b in enumerate(boxes):
        if not b:continue
        w,h=b[2]-b[0],b[3]-b[1]
        if not (90<w<340 and .85<w/h<1.15 and b[0]>550 and b[1]>350):continue
        for j,c in enumerate(boxes):
            if i==j or not c:continue
            if b[0]<c[0]<c[2]<b[2] and b[1]<c[1]<c[3]<b[3]:
                if abs((b[0]+b[2])-(c[0]+c[2]))<12 and abs((b[1]+b[3])-(c[1]+c[3]))<12:
                    return [parts[i],parts[j]],[p for k,p in enumerate(parts) if k not in (i,j)]
    raise ValueError('Could not identify a genuine handakuten ring')

def add_shaping(font,noto,cjk,scale):
    cm=font.getBestCmap();scm=noto.getBestCmap();gs=font.getGlyphSet()
    marks={}
    for cls,cp in enumerate([0x3099,0x309A]):
        n=cm[cp];b=bounds(font,n)
        marks[n]=(cls,buildAnchor(round((b[0]+b[2])/2),round((b[1]+b[3])/2)))
    bases={};anchor_report={}
    for cp,n in cm.items():
        if not (0x3041<=cp<=0x30FA or 0x31F0<=cp<=0x31FF):continue
        if unicodedata.category(chr(cp))!='Lo':continue
        b=bounds(font,n)
        if not b:continue
        # Fallback attachment for combinations without a source ligature.
        x=min(940,max(800,b[2]));y=min(820,b[3]-45)
        bases[n]={0:buildAnchor(round(x),round(y)),1:buildAnchor(round(x),round(y))}
        anchor_report[n]=[round(x),round(y)]
    ligatures={};lig_report=[]
    for feature in noto['GSUB'].table.FeatureList.FeatureRecord:
        if feature.FeatureTag!='ccmp':continue
        for index in feature.Feature.LookupListIndex:
            for st in noto['GSUB'].table.LookupList.Lookup[index].SubTable:
                for src,ls in getattr(st,'ligatures',{}).items():
                    for lig in ls:
                        if lig.Component!=[scm[0x309A]]:continue
                        cps=[cp for cp,n in scm.items() if n==src and cp in cm and cp in range(0x3041,0x3200)]
                        for cp in cps:ligatures[cp]=lig.LigGlyph
    for cp,dst in sorted(ligatures.items()):
        axis=cjk['report']['source_wght']['hira' if cp<0x30A0 else 'kata']
        ngs=noto.getGlyphSet(location={'wght':axis})
        source=rec(ngs,scm[cp]);combined=rec(ngs,dst)
        rings,body=ring_parts(combined)
        sb=shapes.bbox(source);bb=shapes.bbox([op for p in body for op in p])
        rb=shapes.bbox([op for p in rings for op in p]);n=cm[cp];ob=bounds(font,n)
        # The current hand-drawn body is retained, including ki and its curves.
        dx=round(((bb[0]+bb[2])-(sb[0]+sb[2]))/2*scale)
        dy=round(((bb[1]+bb[3])-(sb[1]+sb[3]))/2*scale)
        tx=(ob[0]+ob[2])/2-(sb[0]+sb[2])/2*scale
        ty=(ob[1]+ob[3])/2-(sb[1]+sb[3])/2*scale
        cx=(rb[0]+rb[2])/2*scale+tx;cy=(rb[1]+rb[3])/2*scale+ty
        mn=cm[0x309A];mb=bounds(font,mn)
        # Uniform scale keeps the ring circular, including the small Ainu kana.
        k=(rb[2]-rb[0])*scale/(mb[2]-mb[0])
        mtx=cx-(mb[0]+mb[2])/2*k;mty=cy-(mb[1]+mb[3])/2*k
        p=TTGlyphPen(font.getGlyphSet());p.addComponent(n,(1,0,0,1,dx,dy));p.addComponent(mn,(k,0,0,k,mtx,mty))
        name=f'jp.ccmp.u{cp:04X}.handakuten';append_glyph(font,name,p.glyph())
        lig_report.append({'base':chr(cp),'glyph':name,'body_shift':[dx,dy],'mark_center':[round(cx,2),round(cy,2)],'mark_scale':k})
        # Explicit mark=1,ccmp=0 also attaches correctly to the unshifted body.
        bases[n][1]=buildAnchor(round(cx),round(cy))
        anchor_report[n]=[round(cx),round(cy)]
    sub=ot.LigatureSubst();sub.ligatures={}
    for row in lig_report:
        cp=ord(row['base']);lig=ot.Ligature();lig.LigGlyph=row['glyph'];lig.Component=[cm[0x309A]];lig.CompCount=2
        sub.ligatures.setdefault(cm[cp],[]).append(lig)
    attach_feature(font,'GSUB','ccmp',buildLookup([sub]),['DFLT','kana','hani'])
    sub=buildMarkBasePosSubtable(marks,bases,font.getReverseGlyphMap())
    attach_feature(font,'GPOS','mark',buildLookup([sub]),['DFLT','kana','hani','latn'])
    classes=font['GDEF'].table.GlyphClassDef.classDefs
    classes.update({n:1 for n in bases});classes.update({n:3 for n in marks})
    classes.update({r['glyph']:2 for r in lig_report})
    return {'ccmp_pairs':lig_report,'fallback_base_count':len(bases),'anchors':anchor_report}

def add_coverage(font,noto,cjk):
    target,frame,centre=cjk['targets'];scm=noto.getBestCmap()
    kw,_,_=mono.plan_cjk_wghts(noto,target,frame)
    gs=noto.getGlyphSet(location={'wght':kw})
    samples={scm[ord(ch)]:rec(gs,scm[ord(ch)]) for ch in set(mono.FRAME_SAMPLE+mono.KANJI_SAMPLE)}
    sw,sh,sc=mono.frame_of(samples,scm,mono.FRAME_SAMPLE)
    stem=mono.median_stem(samples,scm,mono.KANJI_SAMPLE,shapes.CJK_CUTS)
    scale=1.0
    for _ in range(8):
        delta=target-stem*scale;scale=((frame[0]-delta)/sw+(frame[1]-delta)/sh)/2
    assert abs(target-stem*scale)<.25,'New glyphs require a nontrivial weight pass'
    added=[]
    for cp in sorted(EXTRA_CODEPOINTS):
        name='jp.'+scm[cp]
        source=rec(gs,scm[cp])
        transformed=shapes.transform(source,Transform(scale,0,0,scale,500-gs[scm[cp]].width*scale/2,centre-sc*scale))
        transformed=shapes.remove_overlap(transformed,name)
        append_glyph(font,name,mono.to_glyf(transformed))
        for t in font['cmap'].tables:
            if t.isUnicode() and t.format in (4,12) and (cp<=0xffff or t.format==12):t.cmap[cp]=name
        font['GDEF'].table.GlyphClassDef.classDefs[name]=1
        for st in noto['cmap'].tables:
            if st.format!=14:continue
            for selector,pairs in st.uvsDict.items():
                for base,dst in pairs:
                    if base!=cp:continue
                    assert dst is None,'A new nondefault UVS needs its own outline'
                    for t in font['cmap'].tables:
                        if t.format==14:
                            t.uvsDict.setdefault(selector,[]).append((cp,None));t.uvsDict[selector].sort()
        added.append({'char':chr(cp),'cp':cp,'glyph':name})
    return {'added':added,'noto_kanji_axis':kw,'scale':scale,'translation_y':centre-sc*scale},scale

def rename(font,family,version,revision):
    style=font['name'].getDebugName(17);legacy=family+' Medium' if style=='Medium' else family
    ps=family.replace(' ','')+'-'+style
    vals={1:legacy,2:'Regular' if style=='Medium' else style,3:f'{version};INOR;{ps}',
      4:family if style=='Regular' else family+' '+style,5:'Version '+version,6:ps,16:family,17:style,
      10:'Japanese combining marks and Yoshida-name ideograph coverage fixed. Latin outlines and hinting retained.',
      19:family+' 日本語 English 𠮷野家'}
    for record in font['name'].names:
        if record.nameID in vals:record.string=vals[record.nameID].encode(record.getEncoding(),errors='replace')
    for nid,value in vals.items():font['name'].setName(value,nid,3,1,0x409)
    font['head'].fontRevision=revision

def save(font,folder,style):
    for d in ['ttf','web']:(folder/d).mkdir(parents=True,exist_ok=True)
    p=folder/f'ttf/FridaySans-{style}.ttf';font.flavor=None;font.save(p)
    font.flavor='woff2';font.save(folder/f'web/FridaySans-{style}.woff2');font.flavor=None
    return hashlib.sha256(p.read_bytes()).hexdigest()

def make_grid_trial(font,style):
    native=TTFont(ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{style}.ttf')
    for tag in ['fpgm','prep','cvt ']:assert font.getTableData(tag)==native.getTableData(tag),tag
    def ideograph(cp):return 0x2e80<=cp<=0x2fdf or 0x3400<=cp<=0x9fff or 0xf900<=cp<=0xfaff or 0x20000<=cp<=0x3ffff
    selected={n for cp,n in font.getBestCmap().items() if ideograph(cp)}
    for t in font['cmap'].tables:
        if t.format==14:selected.update(n for pairs in t.uvsDict.values() for cp,n in pairs if n and ideograph(cp))
    prefix=Program();prefix.fromAssembly(['MPPEM[]','PUSHB[ ]','11','GTEQ[]','MPPEM[]','PUSHB[ ]','18','LTEQ[]','AND[]','IF[]'])
    hinted=0;missing=[]
    for n in sorted(selected):
        if n not in native['glyf']:missing.append(n);continue
        a,b=font['glyf'][n],native['glyf'][n]
        assert a.getCoordinates(font['glyf'])==b.getCoordinates(native['glyf']),n
        code=b.program.getBytecode() if hasattr(b,'program') else b''
        if not code:continue
        a.program=Program();a.program.fromBytecode(prefix.getBytecode()+code+b'\x59');hinted+=1
    font['maxp'].maxStackElements+=8
    rename(font,'Friday Sans Grid Trial','2.101',2.101)
    return {'kanji_programs_restored':hinted,'unhinted_new_ideographs':missing,'ppem_range':[11,18],'kana_programs_restored':0,'windows_verified':False}

def main():
    manifest=[]
    noto=TTFont(ROOT/'Source/noto-cjk/NotoSansCJKjp-VF.ttf')
    for style in STYLES:
        src=BASE/f'ttf/FridaySans-{style}.ttf';font=TTFont(src,recalcTimestamp=False)
        cjk=pickle.load(open(ROOT/f'InoriMono-v3-build/sans/work/cjk-{style}.pkl','rb'))
        coverage,scale=add_coverage(font,noto,cjk)
        shaping=add_shaping(font,noto,cjk,scale)
        rename(font,'Friday Sans','2.100',2.1)
        stable_hash=save(font,OUT,style)
        trial_report=make_grid_trial(font,style);trial_hash=save(font,TRIAL,style)
        manifest.append({'style':style,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
          'ttf_sha256':stable_hash,'trial_sha256':trial_hash,'coverage':coverage,'shaping':shaping,'grid_trial':trial_report})
        font.close();print(style,len(shaping['ccmp_pairs']),'Japanese ccmp pairs; 𠮷 added; grid trial built',flush=True)
    noto.close()
    for folder in [OUT,TRIAL]:
        (folder/'licenses').mkdir(parents=True,exist_ok=True)
        shutil.copyfile(BASE/'OFL.txt',folder/'OFL.txt')
        for p in (BASE/'licenses').iterdir():
            if p.is_file():shutil.copyfile(p,folder/'licenses'/p.name)
        (folder/'font-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
