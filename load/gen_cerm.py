import sys, json, pandas as pd
src=open("big_search.py").read(); exec(src[src.index("import json"):src.index("disp={1:")])
rs3=pd.read_csv("../cepm/cepm3_rs.csv")
for tag,(w,a,uo) in {"A":(.35,1,0),"B":(.35,1,.2),"C":(.5,1,.35),"D":(.35,0,0),"E":(0,0,0)}.items():
    out=[]
    for p,r,we in zip(rs3.player,rs3.rapm,rs3.window_end):
        p=int(p); si=SI.get(we)
        if si is None or p not in ids: continue
        c=comps(p,[S[x] for x in range(max(0,si-2),si+1)],3000)
        if c: out.append([ids.index(p),si,((1-w)*r+w*c[0])*c[1]**a*(1+uo*(c[2]-1))])
    json.dump(out,open(f"cerm_{tag}.json","w"))
print("ok")
