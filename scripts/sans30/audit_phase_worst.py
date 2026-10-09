import sys
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_unhinted as A
import numpy as np
for name in ('Friday Sans 3.0','Friday Sans 2.5','Hiragino W3','Noto Sans JP','Inter','SF Pro Text'):
    p,i,_=A.FACES[name];f=A.Face(name,p,i)
    for px in (12,14):
        res=[]
        for ch in A.LOWER+A.UPPER+A.DIGITS:
            r=A.raster_stats(f,ch,px)
            if r: res.append((r['Erange'],ch,round(r['E'],3)))
        res.sort(reverse=True)
        print(name.ljust(16),px,'worst:',' '.join(f'{c}:{e:.2f}' for e,c,_ in res[:10]),'| mean range %.3f'%np.mean([e for e,_,_ in res]))
