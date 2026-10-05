"""One fixed Inori skeleton for all weights, with Noto-derived weight matching."""
import json
from pathlib import Path
from statistics import median
import pathops
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from . import shapes,handdrawn

MASTER_PATH=Path(__file__).resolve().parent.parent/'drawings/vector-masters.json'
DATA=json.loads(MASTER_PATH.read_text())
BASES='とさきふや'
DERIVED={'ど':('と',-25),'ざ':('さ',-75),'ぎ':('き',-65),'ぶ':('ふ',-40),'ぷ':('ふ',-40)}

def width(rec):
    mask,scale=handdrawn.raster(rec,1600)
    return handdrawn.stroke_width(mask)/scale

def quadratic(rec):
    out=RecordingPen();pen=Cu2QuPen(out,max_err=.20)
    for op,args in rec:getattr(pen,op)(*args)
    return out.value

def draw(ch,stem,calibration=False):
    master=DATA['glyphs'][ch]
    if 'outline_master' in master:
        # Keep the accepted Ya design as one immutable master. Symmetric
        # parallel offsets vary its ink, never fit an independent weight shape.
        rec=master['outline_master']
        amount=stem-master['outline_reference_width']
        if abs(amount)<1e-6:return quadratic(rec)
        out,ok=shapes.dilate_checked(rec,amount,ch)
        if not ok:raise ValueError(f'{ch}: shared outline offset failed')
        return quadratic(out)
    paths=[]
    strokes=master.get('weight_reference_strokes',master['strokes']) if calibration else master['strokes']
    for stroke in strokes:
        p=pathops.Path()
        for op,*values in stroke['ops']:
            if op=='M':p.moveTo(*values)
            elif op=='L':p.lineTo(*values)
            else:p.cubicTo(*values)
        join=pathops.LineJoin.MITER_JOIN if stroke.get('join')=='miter' else pathops.LineJoin.BEVEL_JOIN
        p.stroke(stem*stroke['weight_ratio'],pathops.LineCap.BUTT_CAP,join,4.0 if stroke.get('join')=='miter' else 1.4)
        paths.append(p)
    out=pathops.Path();pathops.union(paths,out.getPen())
    return quadratic(shapes.from_path(out))

def build(targets):
    # The scalar changes with weight. Every centreline coordinate stays fixed.
    stem=median(width(targets[ch]) for ch in 'しつか')
    result={};glyph_stems={}
    for ch in BASES + ('ゃ' if 'ゃ' in DATA['glyphs'] else ''):
        target_width=width(targets[ch]);ink_stem=stem
        for _ in range(4):
            outline=draw(ch,ink_stem,calibration=True);achieved=width(outline)
            if abs(achieved-target_width)<.35:break
            ink_stem*=target_width/achieved
        result[ch]=draw(ch,ink_stem);glyph_stems[ch]=ink_stem
    for ch,(base,dx) in DERIVED.items():
        design=ch if ch in DATA['glyphs'] else base
        source_body,marks=handdrawn._split_mark(targets[ch])
        if ch!='ぷ' and shapes._contours(marks)!=2:
            # Noto's ざ can have one dakuten fused to its bar. Use this same
            # source face's intact pair, positioned by the surviving right mark.
            _,pair=handdrawn._split_mark(targets['ど'])
            a,b=shapes.bbox(pair),shapes.bbox(marks)
            marks=shapes.translate(pair,b[2]-a[2],b[3]-a[3])
        # Voiced kana use the same centreline, with the source face's optical
        # weight for their body. This may differ slightly from the plain kana.
        target_width=width(source_body);ink_stem=glyph_stems[base]
        for _ in range(4):
            body=draw(design,ink_stem);achieved=width(body)
            if abs(achieved-target_width)<.35:break
            ink_stem*=target_width/achieved
        glyph_stems[ch]=ink_stem
        body=shapes.translate(draw(design,ink_stem),dx)
        merged=shapes.remove_overlap(body+marks,ch)
        expected=shapes._contours(body)+shapes._contours(marks)
        if shapes._contours(merged)!=expected:
            raise ValueError(f'{ch}: a mark touches the body; revise fixed placement')
        result[ch]=quadratic(merged)
    return result,{"reference_stem":stem,"glyph_stems":glyph_stems}
