"""Kana hint trial utilities. Native outlines are never rewritten.

After the existing ideograph hinter, soften its Y adjustments towards the
scaled original outline. Use standard GC/MUL/SCFS instructions, so the native
hint engine still computes the fit at the actual scale and transform.
"""
from pathlib import Path
import ctypes as C, sys, unicodedata
import numpy as np
from fontTools.ttLib.tables.ttProgram import Program
from scipy import ndimage

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'comparisons/kana-hint-2.2'
WORK.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'comparisons/friday-sans-2.0'))
import raster_support as r
r.FT.FT_Load_Glyph.argtypes=[r.FacePtr,C.c_uint,C.c_int32]
r.FT.FT_Render_Glyph.argtypes=[C.c_void_p,C.c_int]
r.FT.FT_Set_Char_Size.argtypes=[r.FacePtr,C.c_long,C.c_long,C.c_uint,C.c_uint]
r.FT.FT_Property_Set.argtypes=[C.c_void_p,C.c_char_p,C.c_char_p,C.c_void_p]

class Outline(C.Structure):
    _fields_=[('n_contours',C.c_short),('n_points',C.c_short),
              ('points',C.POINTER(r.Vector)),('tags',C.POINTER(C.c_char)),
              ('contours',C.POINTER(C.c_short)),('flags',C.c_int)]
class FullSlot(C.Structure):
    _fields_=r.Slot._fields_+[('outline',Outline)]

def face(path):
    f=r.FacePtr();assert r.FT.FT_New_Face(r.library,str(path).encode(),0,C.byref(f))==0
    return f

def raster(f,gid,px,flags=4|8):
    assert r.FT.FT_Set_Pixel_Sizes(f,0,px)==0
    return loaded_raster(f,gid,flags)

def loaded_raster(f,gid,flags=4|8):
    err=r.FT.FT_Load_Glyph(f,gid,flags);assert err==0,(gid,flags,err)
    s=f.contents.glyph.contents;b=s.bitmap
    raw=C.string_at(b.buffer,abs(b.pitch)*b.rows) if b.width and b.rows else b''
    a=np.frombuffer(raw,dtype=np.uint8).reshape(b.rows,abs(b.pitch))[:,:b.width].copy() if raw else np.zeros((0,0),dtype=np.uint8)
    if b.pitch<0:a=a[::-1]
    return a,s.left,s.top

def fractional_raster(f,gid,ppem,flags=4|8):
    assert r.FT.FT_Set_Char_Size(f,0,round(ppem*64),72,72)==0
    return loaded_raster(f,gid,flags)

def points(f,gid,px,flags=8):
    assert r.FT.FT_Set_Pixel_Sizes(f,0,px)==0
    assert r.FT.FT_Load_Glyph(f,gid,flags)==0
    o=C.cast(f.contents.glyph,C.POINTER(FullSlot)).contents.outline
    return np.array([(o.points[i].x,o.points[i].y) for i in range(o.n_points)],dtype=np.int64)

def code(font,name):
    g=font['glyf'][name]
    return g.program.getBytecode() if hasattr(g,'program') else b''

def asm(lines):
    p=Program();p.fromAssembly(lines);return p.getBytecode()

def push(n):return ['PUSHB[ ]' if 0<=n<=255 else 'PUSHW[ ]',str(n)]

def soften_program(native,point_count,strength,cap=24):
    """Strength 0..64; cap maximum Y movement at cap/64 device pixels.

    Each point is set to original + clamp((fitted-original)*strength/64).
    Phantom points are left alone. SZPS restores access to glyph zone 1.
    """
    # ClearType compatibility can suppress late point moves after both IUP
    # axes have run. Delay the no-op X interpolation until after softening.
    # These CJK programs only fit Y; retain their Y interpolation first.
    original=Program();original.fromBytecode(native)
    native_asm=original.getAssembly()
    delayed=[line for line in native_asm if line.startswith('IUP[1]')]
    assert len(delayed)<=1
    out=bytearray(asm([line for line in native_asm if not line.startswith('IUP[1]')]))
    lines=['SVTCA[0]']+push(1)+['SZPS[ ]']+push(1)+['SLOOP[ ]']
    for i in range(point_count):
        lines+=push(i)+['DUP[ ]','GC[1]']+push(i)+['GC[0]']+push(i)+['GC[1]','SUB[ ]']
        if strength!=64:lines+=push(strength)+['MUL[ ]']
        if cap is not None:lines+=push(cap)+['MIN[ ]']+push(-cap)+['MAX[ ]']
        lines+=['ADD[ ]','SCFS[ ]']
    out+=asm(lines)
    out+=asm(delayed)
    return bytes(out)

def gated_program(native,point_count,strength,cap=24):
    return asm(['MPPEM[ ]']+push(11)+['GTEQ[ ]','MPPEM[ ]']+push(18)+['LTEQ[ ]','AND[ ]','IF[ ]'])+soften_program(native,point_count,strength,cap)+b'\x59'

def kana_names(font):
    cm=font.getBestCmap()
    selected={n for cp,n in cm.items() if 0x3040<=cp<=0x30ff or 0x31f0<=cp<=0x31ff}
    # Vertical alternates inherit the same kana policy, not ideograph policy.
    for feature in font['GSUB'].table.FeatureList.FeatureRecord:
        if feature.FeatureTag not in ('vert','vrt2'):continue
        for index in feature.Feature.LookupListIndex:
            for st in font['GSUB'].table.LookupList.Lookup[index].SubTable:
                for a,b in getattr(st,'mapping',{}).items():
                    if a in selected:selected.add(b)
    return selected

def charset(font):
    return {cp:n for cp,n in font.getBestCmap().items() if 0x3040<=cp<=0x30ff or 0x31f0<=cp<=0x31ff}

def softness(a):return float(a[a<128].sum()/a.sum()*100) if a.sum() else 0.

def holes(a):
    binary=np.pad(a>=128,1);lab,n=ndimage.label(~binary)
    return n-1

def render_points(f,gid,px,coords):
    assert r.FT.FT_Set_Pixel_Sizes(f,0,px)==0
    assert r.FT.FT_Load_Glyph(f,gid,8|2)==0
    s=C.cast(f.contents.glyph,C.POINTER(FullSlot)).contents
    assert s.outline.n_points==len(coords)
    for i,(x,y) in enumerate(coords):s.outline.points[i].x=int(x);s.outline.points[i].y=int(y)
    assert r.FT.FT_Render_Glyph(f.contents.glyph,0)==0
    s=f.contents.glyph.contents;b=s.bitmap
    raw=C.string_at(b.buffer,abs(b.pitch)*b.rows) if b.width and b.rows else b''
    a=np.frombuffer(raw,dtype=np.uint8).reshape(b.rows,abs(b.pitch))[:,:b.width].copy() if raw else np.zeros((0,0),dtype=np.uint8)
    if b.pitch<0:a=a[::-1]
    return a,s.left,s.top

def controlled_program(native,point_count,settings,storage):
    """Per-PPEM gentle Y fit and whole-glyph phase, with a half-pixel cap.

    Scratch storage is beyond the original font's reserved storage range.
    Set parameters after the old code runs, then read them for every point.
    """
    old=Program();old.fromBytecode(native);lines=old.getAssembly()
    delayed=[l for l in lines if l.startswith('IUP[1]')];assert len(delayed)<=1
    data=bytearray(asm(['MPPEM[ ]']+push(11)+['GTEQ[ ]','MPPEM[ ]']+push(18)+['LTEQ[ ]','AND[ ]','IF[ ]']))
    setup=['SVTCA[0]']+push(1)+['SZPS[ ]']+push(1)+['SLOOP[ ]']
    for px,(strength,phase) in sorted(settings.items()):
        setup+=['MPPEM[ ]']+push(px)+['EQ[ ]','IF[ ]']+push(storage)+push(strength)+['WS[ ]']+push(storage+1)+push(phase)+['WS[ ]','EIF[ ]']
    data+=asm(setup)
    # A phase-only fit needs no legacy hinter. In particular, do not execute
    # its unused point-reference code for tiny rings and punctuation.
    data+=asm(push(storage)+['RS[ ]','IF[ ]'])
    data+=asm([l for l in lines if not l.startswith('IUP[1]')])+b'\x59'
    setup=['SVTCA[0]']+push(1)+['SZPS[ ]']+push(1)+['SLOOP[ ]']
    for i in range(point_count):
        setup+=push(i)+['DUP[ ]','GC[1]']+push(i)+['GC[0]']+push(i)+['GC[1]','SUB[ ]']
        setup+=push(storage)+['RS[ ]','MUL[ ]']+push(24)+['MIN[ ]']+push(-24)+['MAX[ ]']
        setup+=push(storage+1)+['RS[ ]','ADD[ ]']+push(32)+['MIN[ ]']+push(-32)+['MAX[ ]','ADD[ ]','SCFS[ ]']
    data+=asm(setup)+asm(delayed)+b'\x59'
    return bytes(data)
