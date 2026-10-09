import sys,numpy as np,random
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_unhinted as A
random.seed(7)
kanji=random.sample(A.jis1_kanji(),600)
cls={'lower':list(A.LOWER),'upper':list(A.UPPER),'digit':list(A.DIGITS),'hiragana':A.HIRA,'katakana':A.KATA,'kanji':kanji}
F={n:A.Face(n,*A.FACES[n][:2]) for n in ('Friday Sans 3.0','Friday Sans 2.5','Hiragino W3','Noto Sans JP','Inter','SF Pro Text')}
def ink(f,c):
    cons=f.contours(c)
    return sum(A.area(x)*-1 for x in cons) if cons else None   # clockwise = ink => negative area
def table(a,b,label):
    print('==',label)
    for c,chars in cls.items():
        r=[]
        for ch in chars:
            if F[a].has(ch) and F[b].has(ch):
                x,y=ink(F[a],ch),ink(F[b],ch)
                if x and y and x>0 and y>0: r.append(x/y)
        if len(r)<5: continue
        r=np.array(r);m=np.median(r)
        dev=np.abs(r/m-1)
        print('  %-9s n=%3d median ratio %.3f | per-glyph p5 %.3f p95 %.3f | glyphs off the class median by >10%%: %3d (%.1f%%), >20%%: %d, worst %.0f%%'%(c,len(r),m,np.percentile(r,5),np.percentile(r,95),(dev>.1).sum(),100*(dev>.1).mean(),(dev>.2).sum(),100*dev.max()))
table('Friday Sans 3.0','Friday Sans 2.5','Friday 3.0 / Friday 2.5  (ink area, same character)')
table('Friday Sans 3.0','Hiragino W3','Friday 3.0 / Hiragino W3')
table('Friday Sans 3.0','Noto Sans JP','Friday 3.0 / Noto Sans JP 400')
table('Friday Sans 2.5','Hiragino W3','(参考) Friday 2.5 / Hiragino W3')
table('Friday Sans 3.0','Inter','Friday 3.0 / Inter')
table('Friday Sans 3.0','SF Pro Text','Friday 3.0 / SF Pro Text')
table('Noto Sans JP','Hiragino W3','(参考) Noto / Hiragino W3')
