import sys,json
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_unhinted as A
import numpy as np
groups={
 'x-height flat tops (u v w x y z)':('top',list('uvwxyz')),
 'x-height round tops (c e o s)':('top',list('ceos')),
 'x-height all (a c e m n o r s u v w x z)':('top',list('acemnorsuvwxz')),
 'cap flat tops (E F H I K L M N T V W X Y Z)':('top',list('EFHIKLMNTVWXYZ')),
 'cap round tops (C G O Q S)':('top',list('CGOQS')),
 'cap all (A-Z)':('top',list(A.UPPER)),
 'digit tops (0-9)':('top',list(A.DIGITS)),
 'baseline flat bottoms (E F H I K L M N Z b d h i k l m n r u v w x z)':('bot',list('EFHIKLMNZbdhiklmnruvwxz')),
 'baseline round bottoms (C G O S c e o s 0 6 8 3)':('bot',list('CGOSceos0683')),
 'baseline all A-Za-z0-9 excl. descenders':('bot',list('ABCDEFGHIKLMNOPRSTUVWXZabcdefhiklmnorstuvwxz0123456789')),
}
rows={}
for name in ('Friday Sans 3.0','Friday Sans 2.5','Hiragino W3','Noto Sans JP','Inter','SF Pro Text'):
    p,i,_=A.FACES[name];f=A.Face(name,p,i)
    em={g:(max if k=='top' else min)(0,0) for g,(k,_) in groups.items()}
    out={}
    for g,(k,chars) in groups.items():
        vals=[]
        for c in chars:
            b=A.bounds(f,c)
            if b: vals.append(b[0] if k=='top' else b[1])
        out[g]=(max(vals)-min(vals),np.std(vals),np.median(vals))
    xh=A.bounds(f,'x')[0];cap=A.bounds(f,'H')[0];dg=A.bounds(f,'1')[0]
    out['_o']=A.bounds(f,'o')[0];out['_O']=A.bounds(f,'O')[0]
    out['_lines']=(xh,cap,dg,A.bounds(f,'0')[0])
    rows[name]=out
names=list(rows)
print('値は em の千分率(‰)。12px 換算は ×0.012 px/‰ → 1‰=0.012px(12px)、0.016px(16px)')
print(' '*58,' '.join(n[:15].ljust(15) for n in names))
for g in groups:
    print(g[:58].ljust(58),' '.join(f"range{rows[n][g][0]*1000:5.1f}‰ sd{rows[n][g][1]*1000:4.1f}".ljust(15) for n in names))
print('x-height overshoot o - x (‰) / O - H (‰)'.ljust(58),' '.join(('%d / %d'%(round((rows[n]['_o']-rows[n]['_lines'][0])*1000),round((rows[n]['_O']-rows[n]['_lines'][1])*1000))).ljust(15) for n in names))
print('x/cap/digit1/zero top (‰)'.ljust(58),' '.join(('%d/%d/%d/%d'%tuple(round(v*1000) for v in rows[n]['_lines'])).ljust(15) for n in names))
