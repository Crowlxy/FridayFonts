"""Apply the RC3 repair policy to the original, independently hinted italics.

Keep italic Latin and the italic CVT/prep. Kanji motion caps are measured
against the italic outlines; upright bytecode is never transplanted.
"""
from pathlib import Path
import copy, json, math, sys
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.ttProgram import Program
from fontTools.ttLib.tables import otTables
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.misc.transform import Transform

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'FridayFonts-WindowsTest/windows-lab/tools'))
sys.path.insert(0,str(ROOT/'FridayFonts-WindowsTest/tools'))
from build_candidate import safe_cap, post_guard, SIZES, CAPS, is_kanji
from build_kanji_guard_trial import helper, code
import font_raster as raster
DEST=ROOT/'FridayFonts/rc3-italic'
SHEAR=-math.tan(math.radians(-10.0)); PIVOT=704.6/2

def outline(g,f): return g.getCoordinates(f['glyf'])

def leaned(f,n):
    pen=TTGlyphPen(None)
    f.getGlyphSet()[n].draw(TransformPen(pen,Transform(1,0,SHEAR,1,-SHEAR*PIVOT,0)))
    g=pen.glyph();g.program=Program();g.program.fromBytecode(b'');g.recalcBounds(None)
    return g

def boxes(f):
    gs=f.getGlyphSet(); result={}
    for n in f.getGlyphOrder():
        p=BoundsPen(gs);gs[n].draw(p);result[n]=p.bounds
    return result

def centered_enclosers(f,bounds):
    cm=f.getBestCmap();marks={cm[0x20dd],cm[0x20de]};table=f['GPOS'].table
    for lookup in table.LookupList.Lookup:
        for sub in lookup.SubTable:
            if hasattr(sub,'ExtSubTable'):sub=sub.ExtSubTable
            for cov,arr in [('MarkCoverage','MarkArray'),('Mark1Coverage','Mark1Array')]:
                if not hasattr(sub,cov):continue
                names=getattr(sub,cov).glyphs;indices=[i for i,n in enumerate(names) if n not in marks]
                getattr(sub,cov).glyphs=[names[i] for i in indices]
                a=getattr(sub,arr);a.MarkRecord=[a.MarkRecord[i] for i in indices];a.MarkCount=len(indices)
    for n in marks:
        f['hmtx'][n]=(0,f['glyf'][n].xMin);f['GDEF'].table.GlyphClassDef.classDefs[n]=3
    def anchor(b):
        a=otTables.Anchor();a.Format=1;a.XCoordinate=round((b[0]+b[2])/2);a.YCoordinate=round((b[1]+b[3])/2);return a
    bases=sorted({n for cp,n in cm.items() if __import__('unicodedata').category(chr(cp)).startswith(('L','N')) and bounds[n]},key=f.getGlyphID)
    names=sorted(marks,key=f.getGlyphID)
    lookup=otTables.Lookup();lookup.LookupType=9;lookup.LookupFlag=0;lookup.SubTable=[]
    for first in range(0,len(bases),400):
        sub=otTables.MarkBasePos();sub.Format=1;sub.ClassCount=1
        sub.MarkCoverage=otTables.Coverage();sub.MarkCoverage.glyphs=names[:]
        sub.MarkArray=otTables.MarkArray();sub.MarkArray.MarkRecord=[]
        for n in names:
            record=otTables.MarkRecord();record.Class=0;record.MarkAnchor=anchor(bounds[n]);sub.MarkArray.MarkRecord.append(record)
        sub.MarkArray.MarkCount=len(names)
        sub.BaseCoverage=otTables.Coverage();sub.BaseCoverage.glyphs=bases[first:first+400]
        sub.BaseArray=otTables.BaseArray();sub.BaseArray.BaseRecord=[]
        for n in sub.BaseCoverage.glyphs:
            record=otTables.BaseRecord();record.BaseAnchor=[anchor(bounds[n])];sub.BaseArray.BaseRecord.append(record)
        sub.BaseArray.BaseCount=len(sub.BaseArray.BaseRecord)
        ext=otTables.ExtensionPos();ext.Format=1;ext.ExtensionLookupType=4;ext.ExtSubTable=sub;lookup.SubTable.append(ext)
    lookup.SubTableCount=len(lookup.SubTable)
    index=len(table.LookupList.Lookup);table.LookupList.Lookup.append(lookup);table.LookupList.LookupCount=index+1
    features=[r for r in table.FeatureList.FeatureRecord if r.FeatureTag=='mark'];assert features
    for fr in features:fr.Feature.LookupListIndex.append(index);fr.Feature.LookupCount=len(fr.Feature.LookupListIndex)
    return dict(lookup=index,bases=len(bases),marks=names)

def build(style,path,report_path):
    source=ROOT/f'FridayFonts/dist-v48/ttf/FridayMono-{style}.ttf'
    upright_style={'Italic':'Regular','MediumItalic':'Medium','BoldItalic':'Bold'}[style]
    old=TTFont(ROOT/f'FridayFonts/dist-v48/ttf/FridayMono-{upright_style}.ttf')
    rc3=TTFont(ROOT/f'FridayFonts-WindowsTest/shipping-audit/rc3/fonts/mono-RC3-{upright_style}.ttf')
    f=TTFont(source,recalcTimestamp=False);base=TTFont(source,recalcTimestamp=False)
    changes=[n for n in old.getGlyphOrder() if outline(old['glyf'][n],old)!=outline(rc3['glyf'][n],rc3)]
    added=[n for n in rc3.getGlyphOrder() if n not in old.getGlyphOrder()]
    assert added==['jp.shipping.u20BB7']
    assert all(n.startswith('jp.') for n in changes+added)
    shifts={};cm=f.getBestCmap();horizontal=set(cm.values())
    for n in changes+added:
        g=leaned(rc3,n)
        if n in changes:
            a,tsb=f['vmtx'][n];origin=tsb+f['glyf'][n].yMax
            if n in horizontal and n!=cm[0x20de]:
                dy=g.yMin-f['glyf'][n].yMin
                if dy:shifts[n]=(round(SHEAR*dy),dy)
        else:
            order=f.getGlyphOrder();f.setGlyphOrder(order+[n]);a,tsb=rc3['vmtx'][n];origin=tsb+rc3['glyf'][n].yMax
        f['glyf'][n]=g;f['hmtx'][n]=(rc3['hmtx'][n][0],g.xMin);f['vmtx'][n]=(a,origin-g.yMax)
    for tag in ('cmap','GSUB','GDEF'):f[tag]=copy.deepcopy(rc3[tag])
    for lookup in f['GPOS'].table.LookupList.Lookup:
        for sub in lookup.SubTable:
            if hasattr(sub,'ExtSubTable'):sub=sub.ExtSubTable
            if hasattr(sub,'BaseCoverage'):
                for n,record in zip(sub.BaseCoverage.glyphs,sub.BaseArray.BaseRecord):
                    if n in shifts:
                        dx,dy=shifts[n]
                        for anchor in record.BaseAnchor:
                            if anchor:anchor.XCoordinate+=dx;anchor.YCoordinate+=dy
    stripped=[n for n in old.getGlyphOrder() if code(old,n) and not code(rc3,n)]
    for n in stripped:
        g=f['glyf'][n]
        if hasattr(g,'program'):g.program=Program();g.program.fromBytecode(b'')
    # Apply the same adaptive motion limit policy, measured on italic glyphs.
    raster.interpreter(40);face=raster.face(source)
    caps={n:(32 if len(g.coordinates)<=72 and g.numberOfContours<=8 else 16)
          for cp,n in f.getBestCmap().items() if is_kanji(cp) and (g:=f['glyf'][n]).numberOfContours>0 and code(f,n)}
    indices={n:(base.getGlyphID(n),list(f['glyf'][n].endPtsOfContours)) for n in caps}
    skipped=set();checks=0
    for px in SIZES:
        raster.size(face,px)
        for n,(gid,ends) in indices.items():
            a=raster.points(face,gid);b=raster.points(face,gid,8|2);checks+=1
            if not np.array_equal(a[:,0],b[:,0]):skipped.add(n);continue
            caps[n]=safe_cap(a,b,ends,caps[n])
    raster.FT.FT_Done_Face(face)
    for n in skipped:caps.pop(n)
    lines=f['fpgm'].program.getAssembly();ids=[int(lines[i-1]) for i,line in enumerate(lines) if line.startswith('FDEF')]
    first=max(ids)+1;functions={cap:first+i for i,cap in enumerate(CAPS)}
    f['fpgm'].program.fromBytecode(f['fpgm'].program.getBytecode()+b''.join(helper(functions[c],c) for c in CAPS))
    for n,cap in caps.items():
        p=Program();p.fromBytecode(post_guard(code(f,n),len(f['glyf'][n].coordinates),functions[cap]));f['glyf'][n].program=p
    f['maxp'].maxFunctionDefs=max(f['maxp'].maxFunctionDefs+len(CAPS),first+len(CAPS))
    f['maxp'].maxStackElements+=12
    bounds=boxes(f);enclosure=centered_enclosers(f,bounds)
    f['OS/2'].usWinAscent=max(f['OS/2'].usWinAscent,math.ceil(max(b[3] for b in bounds.values() if b)))
    f['OS/2'].usWinDescent=max(f['OS/2'].usWinDescent,math.ceil(-min(b[1] for b in bounds.values() if b)))
    f['OS/2'].recalcUnicodeRanges(f)
    path.parent.mkdir(parents=True,exist_ok=True);f.save(path)
    # Serialize before trusting caps; FreeType must execute the final bytecode.
    serialized=TTFont(path);face=raster.face(path);tested=0
    for px in (11,12,12.5,14,16,17.5,18):
        raster.size(face,px)
        for n,cap in caps.items():
            gid=serialized.getGlyphID(n);a=raster.points(face,gid);b=raster.points(face,gid,8|2)
            assert np.max(np.abs(a[:,1]-b[:,1]))<=cap,(style,n,px,cap)
            tested+=1
    raster.FT.FT_Done_Face(face)
    for n in base.getGlyphOrder():
        if n not in changes:
            assert outline(serialized['glyf'][n],serialized)==outline(base['glyf'][n],base),(style,n)
            if n not in stripped and n not in caps:assert code(serialized,n)==code(base,n),(style,n,'program')
            if n not in (cm[0x20dd],cm[0x20de]):assert serialized['hmtx'][n]==base['hmtx'][n]
    for tag in ('prep','cvt ','gasp'):assert serialized.getTableData(tag)==base.getTableData(tag),(style,tag)
    for tag in ('hhea','vhea'):
        for attr in ('ascent','descent','lineGap','caretSlopeRise','caretSlopeRun','caretOffset'):
            assert getattr(serialized[tag],attr)==getattr(base[tag],attr),(style,tag,attr)
    report=dict(style=style,source=str(source.relative_to(ROOT)),outlines_changed=changes,added=added,
                changed_horizontal_anchors=shifts,hint_programs_stripped=stripped,kanji_caps=caps,
                cap_selection_cases=checks,cap_execution_cases=tested,skipped_x_motion=sorted(skipped),
                enclosure=enclosure,italic_latin_outlines_hints_metrics_preserved=True,
                italic_cvt_prep_preserved=True,windows_verified=False)
    report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for font in (f,base,old,rc3,serialized):font.close()
    print('ITALIC RC3',style,len(changes),'outlines',len(stripped),'stripped',len(caps),'guarded kanji',flush=True)
    return dict(style=style,source=str(path.relative_to(ROOT)),policy='RC3 fixes applied to independently hinted italic masters')
