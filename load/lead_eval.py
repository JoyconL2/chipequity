import os, json, numpy as np
g={}; exec(open('po_test.py').read().split('if __name__')[0], g)
res={w: g['match'](g['board'](w,2,'t','rs')) for w in (1,3,5)}
print(os.environ.get('LEADBY','r1'), 'match', [round(res[w][0],3) for w in (1,3,5)], 'mean', round(np.mean([res[w][0] for w in (1,3,5)]),3))
for w in (1,5): print('  ', w, 'y:', {n.split()[-1]: res[w][1].get(n) for n in g['T']})
B=g['board'](1,2,'t','rs'); nm=g['nm']
for who in ('Kobe Bryant','Lamar Odom','Draymond Green','Derrick White'):
    p=[k for k,v in nm.items() if v==who][0]; x=B[B.p==p].sort_values('v',ascending=False).head(3)
    print('  ', who, [(s, round(v,2)) for s,v in zip(x.s,x.v)])
x=B[B.s=='2008-09'].sort_values('v',ascending=False).head(6); print('   2008-09 top:', [(nm[p], round(v,2)) for p,v in zip(x.p,x.v)])
