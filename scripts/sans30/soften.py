"""Corner-softening for TrueType quadratic outlines (fixed cut distance fillets).
Sharp ink-convex corners get a quadratic fillet cut back by d_convex; ink-concave by d_concave."""
import math
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

def _len(a,b): return math.hypot(b[0]-a[0],b[1]-a[1])
def _lerp(a,b,t): return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
def _q(p0,c,p1,t):
    a=_lerp(p0,c,t);b=_lerp(c,p1,t);return _lerp(a,b,t)
def _split_q(p0,c,p1,t):
    a=_lerp(p0,c,t);b=_lerp(c,p1,t);m=_lerp(a,b,t)
    return (p0,a,m),(m,b,p1)
def _seglen(s):
    if s[0]=='l': return _len(s[1],s[2])
    p0,c,p1=s[1:]
    return (_len(p0,c)+_len(c,p1)+_len(p0,p1))/2  # rough arc length
def _tan_start(s):
    if s[0]=='l': v=(s[2][0]-s[1][0],s[2][1]-s[1][1])
    else:
        p0,c,p1=s[1:];v=(c[0]-p0[0],c[1]-p0[1])
        if v==(0,0): v=(p1[0]-p0[0],p1[1]-p0[1])
    n=math.hypot(*v) or 1;return (v[0]/n,v[1]/n)
def _tan_end(s):
    if s[0]=='l': v=(s[2][0]-s[1][0],s[2][1]-s[1][1])
    else:
        p0,c,p1=s[1:];v=(p1[0]-c[0],p1[1]-c[1])
        if v==(0,0): v=(p1[0]-p0[0],p1[1]-p0[1])
    n=math.hypot(*v) or 1;return (v[0]/n,v[1]/n)
def _cut_end(s,d):
    """shorten segment s so that it ends d (euclid) before its end point; return new segment"""
    if s[0]=='l':
        p0,p1=s[1:];L=_len(p0,p1);t=1-d/L
        return ('l',p0,_lerp(p0,p1,t))
    p0,c,p1=s[1:]
    lo,hi=0.0,1.0
    for _ in range(30):
        mid=(lo+hi)/2
        if _len(_q(p0,c,p1,mid),p1)>d: lo=mid
        else: hi=mid
    a,_b=_split_q(p0,c,p1,lo);return ('q',)+a
def _cut_start(s,d):
    if s[0]=='l':
        p0,p1=s[1:];L=_len(p0,p1);t=d/L
        return ('l',_lerp(p0,p1,t),p1)
    p0,c,p1=s[1:]
    lo,hi=0.0,1.0
    for _ in range(30):
        mid=(lo+hi)/2
        if _len(_q(p0,c,p1,mid),p0)<d: lo=mid
        else: hi=mid
    _a,b=_split_q(p0,c,p1,hi);return ('q',)+b

def contours_from(glyphset,name):
    pen=RecordingPen();glyphset[name].draw(pen)
    cons=[];cur=None;start=None
    for op,args in pen.value:
        if op=='moveTo': cur=[];start=args[0];pos=start
        elif op=='lineTo':
            cur.append(('l',pos,args[0]));pos=args[0]
        elif op=='qCurveTo':
            pts=list(args)
            if pts[-1] is None:  # closed contour made only of off-curve points
                offs=pts[:-1];m=len(offs)
                mids=[_lerp(offs[i],offs[(i+1)%m],0.5) for i in range(m)]
                cur=[('q',mids[i-1],offs[i],mids[i]) for i in range(m)]
                pos=start=mids[-1]
                continue
            offs=pts[:-1];end=pts[-1]
            for i,c in enumerate(offs):
                nxt=end if i==len(offs)-1 else _lerp(c,offs[i+1],0.5)
                cur.append(('q',pos,c,nxt));pos=nxt
        elif op=='curveTo': return None
        elif op in('closePath','endPath'):
            if pos!=start: cur.append(('l',pos,start))
            cons.append(cur)
    return cons

def soften_contour(segs,dv,dc,ang=20.0,minseg=1.0):
    n=len(segs)
    if n<2: return segs
    cut_s=[0.0]*n;cut_e=[0.0]*n;kind=[None]*n  # corner at start of seg i (between i-1 and i)
    cos_t=math.cos(math.radians(ang))
    L=[_seglen(s) for s in segs]
    for i in range(n):
        a=segs[i-1];b=segs[i]
        ta=_tan_end(a);tb=_tan_start(b)
        dot=ta[0]*tb[0]+ta[1]*tb[1]
        if dot>cos_t: continue
        cross=ta[0]*tb[1]-ta[1]*tb[0]
        d=dv if cross<0 else dc
        if d<=0: continue
        lim=0.4*min(L[i-1],L[i])
        dd=min(d,lim)
        if dd<2: continue
        kind[i]=dd
    # a segment can be cut at both ends; ensure total <=0.8 len
    out=[]
    for i in range(n):
        s=segs[i]
        ds=kind[i] or 0
        de=kind[(i+1)%n] or 0
        tot=ds+de
        if tot>0.85*L[i]:
            f=0.85*L[i]/tot; 
            # shrink both corner cuts proportionally (store)
            if kind[i]: kind[i]*=f
            if kind[(i+1)%n]: kind[(i+1)%n]*=f
    segs2=[]
    for i in range(n):
        s=segs[i]
        ds=kind[i] or 0;de=kind[(i+1)%n] or 0
        if ds: s=_cut_start(s,ds)
        if de: s=_cut_end(s,de)
        segs2.append(s)
    res=[]
    for i in range(n):
        res.append(segs2[i])
        j=(i+1)%n
        if kind[j]:
            V=segs[i][-1]
            res.append(('q',segs2[i][-1],V,segs2[j][1]))
    return res

def build_glyph(cons):
    pen=TTGlyphPen(None)
    for segs in cons:
        pen.moveTo(tuple(round(v) for v in segs[0][1]))
        for s in segs:
            if s[0]=='l': pen.lineTo(tuple(round(v) for v in s[2]))
            else: pen.qCurveTo(tuple(round(v) for v in s[2]),tuple(round(v) for v in s[3]))
        pen.closePath()
    return pen.glyph()
