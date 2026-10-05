"""Bounded curve fairing for hand-drawn outlines; no font serialization.

Work in 1000-upem design units. Preserve substantial corners, approximate
between them with cubic B-splines, then convert to TrueType quadratics.
"""
import numpy as np
from scipy.interpolate import splprep, splev
from skimage.measure import approximate_polygon
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from . import shapes


def _segment(points, pen, tolerance=3.5):
    chord = points[-1] - points[0]
    length = np.linalg.norm(chord)
    if length > 0:
        deviation = np.abs((points[:,0]-points[0,0])*chord[1] -
                           (points[:,1]-points[0,1])*chord[0]) / length
        if deviation.max() <= 2.0:
            pen.lineTo(tuple(points[-1]))
            return
    if len(points) < 4:
        for p in points[1:]:
            pen.lineTo(tuple(p))
        return
    weights = np.ones(len(points))
    weights[[0, -1]] = 10000
    tck, _ = splprep(points.T, w=weights, s=len(points)*tolerance**2, k=3)
    knots = np.unique(tck[0][3:-3])
    for a, b in zip(knots[:-1], knots[1:]):
        p0, p3 = np.array(splev(a, tck)), np.array(splev(b, tck))
        d0, d1 = np.array(splev(a, tck, der=1)), np.array(splev(b, tck, der=1))
        pen.curveTo(tuple(p0 + (b-a)*d0/3), tuple(p3 - (b-a)*d1/3), tuple(p3))


def restore_corners(points):
    """Replace tiny hand-traced bevels by the intersection of their sidewalls.

    Only compact, consistently turning clusters are eligible. This does not
    make broad curved strokes angular and does not borrow reference outlines.
    """
    p=np.array(points)
    for _ in range(32):
        n=len(p)
        turns=[]
        for i in range(n):
            a,b=p[i]-p[i-1],p[(i+1)%n]-p[i]
            turns.append(np.degrees(np.arctan2(a[0]*b[1]-a[1]*b[0],np.dot(a,b))))
        changed=False
        for i in range(n):
            if abs(turns[i])<18: continue
            for span in (2,1):
                ids=[(i+k)%n for k in range(span+1)]
                angles=np.array([turns[k] for k in ids])
                if not np.all(angles*np.sign(turns[i])>12):continue
                distance=sum(np.linalg.norm(p[ids[k+1]]-p[ids[k]]) for k in range(span))
                if distance>40 or not 65<=abs(angles.sum())<=125:continue
                a,b=p[(i-1)%n],p[i]
                c,d=p[ids[-1]],p[(ids[-1]+1)%n]
                u,v=b-a,d-c
                mat=np.column_stack([u,-v])
                if abs(np.linalg.det(mat))<1e-6:continue
                intersection=a+np.linalg.solve(mat,c-a)[0]*u
                if max(np.linalg.norm(intersection-p[k]) for k in ids)>28:continue
                # Rotate the polygon so a wrapping group is still replaced atomically.
                order=np.roll(p,-i,axis=0)
                p=np.vstack([intersection,order[span+1:]])
                changed=True
                break
            if changed:break
        if not changed:break
    return p


def fair(rec, tolerance=3.5):
    result = RecordingPen()
    pen = Cu2QuPen(result, max_err=0.3, reverse_direction=False)
    for contour in shapes.contours(rec):
        box = shapes.bbox(contour)
        if max(box[2]-box[0], box[3]-box[1]) < 270:
            # Dakuten/handakuten are already type-designed: do not refair them.
            for op, args in contour:
                getattr(pen, op)(*args)
            continue
        poly = shapes._flatten(contour, steps=24)[0]
        p = np.array(poly, dtype=float)
        p = p[np.r_[True, np.linalg.norm(np.diff(p, axis=0), axis=1)>1e-6]]
        if np.linalg.norm(p[0]-p[-1]) > 1e-6:
            p = np.vstack([p, p[0]])
        coarse = approximate_polygon(p, tolerance=2.5)[:-1]
        coarse = restore_corners(coarse)
        # Every restored corner is explicitly included in the resampled path.
        # Index mapping avoids moving corners onto nearby sample locations.
        samples, anchors = [], []
        for i, point in enumerate(coarse):
            v, w = point-coarse[i-1], coarse[(i+1)%len(coarse)]-point
            angle = np.degrees(np.arctan2(abs(v[0]*w[1]-v[1]*w[0]), np.dot(v,w)))
            if angle >= 55:
                anchors.append(len(samples))
            next_point=coarse[(i+1)%len(coarse)]
            count=max(1,int(np.ceil(np.linalg.norm(next_point-point)/3)))
            samples.extend(point+(next_point-point)*np.arange(count)[:,None]/count)
        q=np.array(samples)
        n=len(q)
        if len(anchors) < 2:
            # Smooth closed loops periodically: no seam or artificial corner.
            closed = np.vstack([q,q[0]])
            tck, _ = splprep(closed.T, s=len(closed)*tolerance**2, per=True, k=3)
            knots = np.unique(tck[0][3:-3])
            pen.moveTo(tuple(splev(knots[0],tck)))
            for a,b in zip(knots[:-1],knots[1:]):
                p0,p3=np.array(splev(a,tck)),np.array(splev(b,tck))
                d0,d1=np.array(splev(a,tck,der=1)),np.array(splev(b,tck,der=1))
                pen.curveTo(tuple(p0+(b-a)*d0/3),tuple(p3-(b-a)*d1/3),tuple(p3))
        else:
            anchors = sorted(set(anchors))
            pen.moveTo(tuple(q[anchors[0]]))
            for i,a in enumerate(anchors):
                b=anchors[(i+1)%len(anchors)]
                if b<=a: b+=n
                _segment(q[np.arange(a,b+1)%n],pen,tolerance)
        pen.closePath()
    out=result.value
    settled=shapes.remove_overlap(out,'fair')
    if shapes._contours(settled)!=shapes._contours(rec):
        raise ValueError('Fairing changed contour topology')
    ratio=abs(shapes.area(settled)/shapes.area(rec))
    if not 0.975<=ratio<=1.025:
        raise ValueError(f'Fairing changed ink area: {ratio}')
    return settled


def finish(rec, cell=1200):
    """Review candidate: fair the outline and balance horizontal bearings.

    Preserve the vertical ink-box centre rather than forcing unlike kana onto
    one lower edge. Advance and line metrics are the caller's responsibility.
    """
    out=fair(rec,tolerance=2.5)
    old,new=shapes.bbox(rec),shapes.bbox(out)
    return shapes.translate(out,cell/2-(new[0]+new[2])/2,
                            (old[1]+old[3]-new[1]-new[3])/2)
