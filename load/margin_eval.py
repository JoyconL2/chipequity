import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
D=json.load(open("../site/data.json")); S=D["seasons"]; ids=[int(x) for x in D["ids"]]; nm={p:D["names"][k] for k,p in enumerate(ids)}
c=pd.read_csv("comp_share.csv"); LD={(int(p),s):cb and ca/cb for p,s,ca,cb in zip(c.p,c.season,c.comp,c.t_comp)}
M=pd.read_csv("margin_attr.csv"); MA={(int(p),s):r for p,s,r in zip(M.p,M.season,M.itertuples())}
import json as _j, os as _o; _EV = next((_j.load(open(_f)) for _f in ("eval_list.json", "../load/eval_list.json") if _o.path.exists(_f)), {}); T = _EV.get("T", [])   # private evaluation list, kept out of the repo
d=pd.read_csv("../cepm/disp1.csv"); d=d[d.poss>=1500].copy(); d["name"]=d.player.map(nm); d["ld"]=[LD.get((int(p),s),np.nan) for p,s in zip(d.player,d.window_end)]
def mval(p,s,meth,K=3000):
    r=MA.get((int(p),s))
    if r is None: return 0.0
    if meth=="lead": return r.lead*r.lead_poss/(r.lead_poss+K)
    v=getattr(r,meth); return v*r.poss/(r.poss+K)
res=[]
for meth in ("on","share","lead"):
    d["m_"+meth]=[mval(p,s,meth) for p,s in zip(d.player,d.window_end)]
for meth in ("on","share","lead"):
    for w in (0.25,0.5,0.75):
        d["ce"]=((1-w)*d.rapm+w*d["m_"+meth])*d.ld
        best=d.dropna(subset=["ce"]).sort_values("ce",ascending=False).drop_duplicates("player").reset_index(drop=True); rk={n:i+1 for i,n in enumerate(best.name)}
        rho=spearmanr(range(len(T)),[rk.get(n,9999) for n in T]).correlation
        res.append((rho,meth,w,rk["Stephen Curry"],rk.get("Draymond Green"),", ".join(f"{n.split()[-1]} {v:+.1f}" for n,v in zip(best.name[:10],best.ce[:10]))))
for r in sorted(res,reverse=True): print(f"match {r[0]:.2f} | {r[1]:5s} {int(r[2]*100)}% | Curry #{r[3]} Draymond #{r[4]} | {r[5]}")
