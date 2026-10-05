"""Friday Sans Light / SemiBold, step 3 of the RC3 chain (unified Inter merge).

Copy of comparisons/unified-sans-trial/build_trial.py with only these changes:
- STYLES are Light (Hiragino W2) and SemiBold (W5); outputs go to
  FridayFonts/scripts/build-weights/sans/unity, never to the trial folder.
- The Japanese reference is the CJK proof face of the new pickle
  (build-weights/sans-cjk), which holds the same outlines dist-1.1 held for
  R/M/B; the pickle comes from the same place.
- Inter's wght bisection starts at 100 (Light needs less than the old floor
  of 300); opsz is clamped to Inter's 14..32 if the target falls outside.
- The hint step copies no analysis cache (none exists for these weights)
  and uses chlorophytum/inori-sans-<Weight>.json.

Original docstring follows.

Inter + existing Friday Japanese, calibrated to Hiragino's script balance.

Only numerical measurements are taken from Hiragino. No reference outlines
are copied into the generated font. Production files remain untouched.
"""
from pathlib import Path
import argparse, copy, hashlib, inspect, json, pickle, shutil, statistics, sys
from fontTools.ttLib import TTFont

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'FridayFonts/scripts/build-weights/sans/unity'
CJK=ROOT/'FridayFonts/scripts/build-weights/sans-cjk'
BUILD=ROOT/'InoriMono-v3-build'
sys.path.insert(0,str(BUILD/'sans'))
import build_sans as b
sys.path.insert(0,str(ROOT/'FridayFonts/scripts'))
import cjkhint

# The production assembler assumes its original smaller Latin fits 1130/-370.
# Enlarged accent stacks need larger GDI clipping bounds, while hhea/Typo and
# Japanese geometry retain the 1.1 line arrangement. Keep its clipping check.
assembly_source=inspect.getsource(b.assemble).replace(
    'win_asc, win_desc = ASCENT, -DESCENT',
    'win_asc = max(ASCENT, max(bb[3] for nn, bb in boxes.items() if not nn.startswith("jp.")))\n'
    '    win_desc = max(-DESCENT, max(-bb[1] for nn, bb in boxes.items() if not nn.startswith("jp.")))')
# Kana (U+3000-30FF) keep their 1000 cell.  The hand-drawn ぶ ぷ reach a few
# units past the em at heavier weights; the proportional refit meant for Noto
# symbols widened them to 1064-1083 in the shipped Medium/Bold.
_refit='if adv and box and (box[0] < 0 or box[2] > adv):'
assert assembly_source.count(_refit)==1
assembly_source=assembly_source.replace(_refit,
    'if adv and box and (box[0] < 0 or box[2] > adv) and not (name.startswith("uni30") and len(name) == 7):')
exec(compile(assembly_source,str(OUT/'assembler-adaptation.py'),'exec'),b.__dict__)

STYLES=[('Light',300,'W2'),('SemiBold',600,'W5')]
FAMILY='Unity Sans Trial'
b.log=lambda message: print(message.replace('SF Pro Text','Hiragino balance target'),flush=True)

def rec(font,ch):
    return b._rec(font.getGlyphSet(),font.getBestCmap()[ord(ch)])

def box(font,ch):
    u=font['head'].unitsPerEm
    return [v*1000/u for v in b.shapes.bbox(rec(font,ch))]

def targets(style,hw):
    jp=TTFont(CJK/f'FridaySansCJKProof-{style}.ttf')
    ref=TTFont(f'/System/Library/Fonts/ヒラギノ角ゴシック {hw}.ttc',fontNumber=0)
    ratios=[]
    for ch in '日田目国中永本語東書':
        a,c=box(jp,ch),box(ref,ch)
        ratios.append((a[3]-a[1])/(c[3]-c[1]))
    size_ratio=statistics.median(ratios)
    density_ratios=[b.shapes.stem_of(rec(jp,ch))/b.shapes.stem_of(rec(ref,ch)) for ch in '日田目']
    density_ratio=statistics.median(density_ratios)
    cap=box(ref,'H'); cmap=ref.getBestCmap()
    metrics={
        'reference':f'Hiragino Sans {hw} (TTC index 0)',
        'japanese_height_ratio':size_ratio,
        'japanese_stem_ratio':density_ratio,
        'cap_span_target':(cap[3]-cap[1])*size_ratio,
        'x_span_target':(box(ref,'x')[3]-box(ref,'x')[1])*size_ratio,
        'latin_baseline_shift':round(cap[1]*size_ratio),
        'stem_n_target':b.shapes.stem_of(rec(ref,'n'))*density_ratio,
        'mean_lowercase_advance_target':statistics.mean(ref['hmtx'][cmap[ord(ch)]][0] for ch in b.LOWER),
        'japanese_height_samples':'日田目国中永本語東書',
        'japanese_stem_samples':'日田目',
    }
    jp.close();ref.close()
    return metrics

def optical_size_for(target):
    """Use Inter's designed axis to match x-height/cap-height proportions."""
    vf=TTFont(b.INTER_VF);cmap=vf.getBestCmap()
    want=target['x_span_target']/target['cap_span_target']
    def ratio(opsz):
        gs=vf.getGlyphSet(location={'opsz':opsz,'wght':400})
        boxes=[b.shapes.bbox(b._rec(gs,cmap[ord(ch)])) for ch in 'Hx']
        return (boxes[1][3]-boxes[1][1])/(boxes[0][3]-boxes[0][1])
    lo,hi=14.,32.
    if not ratio(hi)<=want<=ratio(lo):
        vf.close()
        print('opsz target outside Inter, clamped',want,ratio(hi),ratio(lo),flush=True)
        return 32.0 if want<ratio(hi) else 14.0
    for _ in range(18):
        mid=(lo+hi)/2
        if ratio(mid)>want:lo=mid
        else:hi=mid
    vf.close()
    return round((lo+hi)/2,3)

def shift_latin(font,dy):
    if not dy:return
    glyf=font['glyf']
    for name in font.getGlyphOrder():
        g=glyf[name]
        if g.numberOfContours>0:
            g.coordinates.translate((0,dy));g.recalcBounds(glyf)
    # Both ends of every mark attachment move with their glyph geometry.
    seen=set()
    def walk(obj):
        if obj is None or id(obj) in seen:return
        seen.add(id(obj))
        if hasattr(obj,'XCoordinate') and hasattr(obj,'YCoordinate'):
            obj.YCoordinate+=dy
        if isinstance(obj,(list,tuple)):
            for item in obj:walk(item)
        elif hasattr(obj,'__dict__'):
            for item in vars(obj).values():walk(item)
    if 'GPOS' in font:walk(font['GPOS'].table)

def solve_wght(style,s):
    """build_sans.solve_wght with the bisection floor at Inter's own 100."""
    vf=TTFont(b.INTER_VF);upem=vf['head'].unitsPerEm;n=vf.getBestCmap()[ord('n')]
    want=b.latin_target(style)[0]
    def stem(w):
        gs=vf.getGlyphSet(location={'opsz':b.INTER_OPSZ,'wght':w})
        return b.shapes.stem_of(b.shapes.scale(b._rec(gs,n),b.EM/upem*s))
    lo,hi=100.0,900.0
    for _ in range(24):
        mid=(lo+hi)/2.0
        if stem(mid)<want:lo=mid
        else:hi=mid
    w=round((lo+hi)/2.0,2);got=stem(w);vf.close()
    return w,got
b.solve_wght=solve_wght

def build():
    (OUT/'fonts-unhinted').mkdir(parents=True,exist_ok=True)
    measurements={}
    b.FAMILY=FAMILY;b.VERSION='Version 0.001';b.REVISION=.001
    b.DESCRIPTION='Trial combining Inter Latin with Friday Japanese, calibrated to Hiragino script proportions. Not a Windows-validated release.'
    for style,weight,hw in STYLES:
        t=targets(style,hw)
        b.INTER_OPSZ=optical_size_for(t)
        t['inter_opsz']=b.INTER_OPSZ
        b.SF_TEXT_CAP=t['cap_span_target']
        b.latin_target=lambda _style, target=t: (target['stem_n_target'],target['mean_lowercase_advance_target'])
        upem,scale,cap=b.inter_scale()
        print('\n'+style+' targets '+json.dumps(t,ensure_ascii=False),flush=True)
        latin,report=b.latin_face(style,upem,scale)
        shift_latin(latin,t['latin_baseline_shift'])
        with open(CJK/f'cjk-{style}.pkl','rb') as fh:cjk=pickle.load(fh)
        path=OUT/f'fonts-unhinted/UnitySansTrial-{style}.ttf'
        b.assemble(style,weight,latin,cjk,str(path))
        font=TTFont(path,recalcTimestamp=False)
        for name in font['name'].names:
            value=name.toUnicode().replace('FridaySans-', 'UnitySansTrial-')
            if name.nameID==3:value=f'0.001;INOR;UnitySansTrial-{style}'
            name.string=value.encode(name.getEncoding(),errors='replace')
        font.save(path)
        # dist-1.1 has no Light/SemiBold; check against the R/M/B-era Regular
        # for layout identity and against the pickle for the Japanese outlines.
        original=TTFont(ROOT/'FridayFonts/releases/archive/sans-1.1/ttf/FridaySans-Regular.ttf')
        # Japanese half: every pickle glyph present with the pickle's advance;
        # layout skeleton identical to the R/M/B faces.
        count=0
        cjk_names={n for cp,n in cjk['cmap'].items() if (0x3041<=cp<=0x30FF or 0x4E00<=cp<=0x9FFF) and not b.mono.zero_advance(cp)}
        for name,(r,adv) in cjk['glyphs'].items():
            jn='jp.'+name
            # Cell glyphs keep the pickle's cell; build_sans re-spaces the
            # Noto-proportional symbols (ink + 100) exactly as it did for R/M/B.
            if jn in font['hmtx'].metrics and name in cjk_names:
                assert font['hmtx'][jn][0]==adv,jn
                count+=1
        assert count>20000-12000,count
        assert font.getBestCmap()==original.getBestCmap()
        assert font.getGlyphOrder()==original.getGlyphOrder()
        for field in ['ascent','descent','lineGap']:
            assert getattr(font['hhea'],field)==getattr(original['hhea'],field),field
        measured={'cap_top':box(font,'H')[3],'cap_bottom':box(font,'H')[1],
                  'x_top':box(font,'x')[3],'x_bottom':box(font,'x')[1],
                  'stem_n':b.shapes.stem_of(rec(font,'n')),
                  'mean_lowercase_advance':statistics.mean(font['hmtx'][font.getBestCmap()[ord(ch)]][0] for ch in b.LOWER),
                  'win_ascent':font['OS/2'].usWinAscent,'win_descent':font['OS/2'].usWinDescent}
        measurements[style]={'targets':t,'inter':report,'actual':measured,'japanese_glyphs_unchanged':count,
                             'source_sha256':hashlib.sha256((CJK/f'cjk-{style}.pkl').read_bytes()).hexdigest()}
        print(style+' actual '+json.dumps(measured)+'; Japanese unchanged '+str(count),flush=True)
        font.close();original.close();latin.close()
    (OUT/'measurements.json').write_text(json.dumps(measurements,ensure_ascii=False,indent=2))

def hint():
    import subprocess,os
    destination=OUT/'fonts-hinted';destination.mkdir(exist_ok=True)
    for style,_,_ in STYLES:
        shutil.copyfile(OUT/f'fonts-unhinted/UnitySansTrial-{style}.ttf',destination/f'UnitySansTrial-{style}.ttf')
    subprocess.run([sys.executable,str(ROOT/'FridayFonts/scripts/rehint.py'),'--dir',str(destination)],check=True)
    cjkhint.TOOL=str(BUILD/'chlorophytum')
    cjkhint.CACHE=str(OUT/'hint-cache');Path(cjkhint.CACHE).mkdir(exist_ok=True)
    os.environ['FRIDAY_CJK_CONFIG']='inori-sans'
    for style,_,_ in STYLES:
        path=str(destination/f'UnitySansTrial-{style}.ttf')
        cjkhint.hint(path)
        assert cjkhint.report(path)
        a=TTFont(OUT/f'fonts-unhinted/UnitySansTrial-{style}.ttf');h=TTFont(path)
        assert a.getBestCmap()==h.getBestCmap()
        assert a.getTableData('hmtx')==h.getTableData('hmtx')
        for name in a.getGlyphOrder():
            assert a['glyf'][name].getCoordinates(a['glyf'])==h['glyf'][name].getCoordinates(h['glyf']),name
        print(style+' hinted: all outlines and widths preserved',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--hint',action='store_true');args=parser.parse_args()
    hint() if args.hint else build()
