# -*- coding: utf-8 -*-
import statistics
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen

def flatten(pen_value, steps=24):
    """return list of closed polygons (list of (x,y))"""
    polys=[]; cur=[]; start=None; last=None
    def bez2(p0,p1,p2):
        for i in range(1,steps+1):
            t=i/steps; mt=1-t
            yield (mt*mt*p0[0]+2*mt*t*p1[0]+t*t*p2[0], mt*mt*p0[1]+2*mt*t*p1[1]+t*t*p2[1])
    def bez3(p0,p1,p2,p3):
        for i in range(1,steps+1):
            t=i/steps; mt=1-t
            yield (mt**3*p0[0]+3*mt*mt*t*p1[0]+3*mt*t*t*p2[0]+t**3*p3[0],
                   mt**3*p0[1]+3*mt*mt*t*p1[1]+3*mt*t*t*p2[1]+t**3*p3[1])
    for op,args in pen_value:
        if op=="moveTo":
            if cur: polys.append(cur)
            cur=[args[0]]; last=args[0]
        elif op=="lineTo":
            cur.append(args[0]); last=args[0]
        elif op=="qCurveTo":
            pts=list(args)
            if pts[-1] is None:
                # TrueType all-offcurve special case
                on=[( (pts[0][0]+pts[-2][0])/2,(pts[0][1]+pts[-2][1])/2 )]
                pts=pts[:-1]+on; last=on[0]
            on=pts[-1]; off=pts[:-1]
            prev=last
            for i,c in enumerate(off):
                if i<len(off)-1:
                    nxt=((c[0]+off[i+1][0])/2,(c[1]+off[i+1][1])/2)
                else: nxt=on
                cur.extend(bez2(prev,c,nxt)); prev=nxt
            last=on
        elif op=="curveTo":
            pts=list(args); prev=last
            if len(pts)==3:
                cur.extend(bez3(prev,pts[0],pts[1],pts[2])); last=pts[2]
            else:
                cur.extend(pts); last=pts[-1]
        elif op=="closePath":
            if cur: polys.append(cur); cur=[]
    if cur: polys.append(cur)
    return polys

def spans(polys, y):
    xs=[]
    for poly in polys:
        n=len(poly)
        for i in range(n):
            x0,y0=poly[i]; x1,y1=poly[(i+1)%n]
            if y0==y1: continue
            if (y0<=y<y1) or (y1<=y<y0):
                t=(y-y0)/(y1-y0); xs.append((x0+t*(x1-x0), 1 if y1>y0 else -1))
    xs.sort()
    out=[]; w=0; s=None
    for x,d in xs:
        if w==0: s=x
        w+=d
        if w==0 and s is not None: out.append((s,x)); s=None
    return out

def spans_v(polys, x):
    ys=[]
    for poly in polys:
        n=len(poly)
        for i in range(n):
            x0,y0=poly[i]; x1,y1=poly[(i+1)%n]
            if x0==x1: continue
            if (x0<=x<x1) or (x1<=x<x0):
                t=(x-x0)/(x1-x0); ys.append((y0+t*(y1-y0), 1 if x1>x0 else -1))
    ys.sort()
    out=[]; w=0; s=None
    for y,d in ys:
        if w==0: s=y
        w+=d
        if w==0 and s is not None: out.append((s,y)); s=None
    return out

def get(font, ch):
    cmap=font.getBestCmap(); n=cmap.get(ord(ch))
    if not n: return None
    gs=font.getGlyphSet(); p=RecordingPen(); gs[n].draw(p)
    return flatten(p.value)
