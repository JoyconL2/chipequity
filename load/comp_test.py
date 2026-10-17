import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
D=json.load(open("../site/data.json")); S=D["seasons"]; SI={s:i for i,s in enumerate(S)}; ids=[int(x) for x in D["ids"]]; nm={p:D["names"][k] for k,p in enumerate(ids)}
c=pd.read_csv("comp_share.csv"); SH={(int(p),s):(a,b,ca,cb) for p,s,a,b,ca,cb in zip(c.p,c.season,c.sec,c.t_all,c.comp,c.t_comp)}
def load(p, end, w, mode):
    a=b=ca=cb=0.0; si=SI[end]
    for x in range(si-w+1, si+1):
        v=SH.get((p,S[x]))
        if v: a+=v[0]; b+=v[1]; ca+=v[2]; cb+=v[3]
    if b==0: return np.nan
    return a/b if mode=="all" else ca/cb
import json as _j, os as _o; _EV = next((_j.load(open(_f)) for _f in ("eval_list.json", "../load/eval_list.json") if _o.path.exists(_f)), {}); T = _EV.get("T", [])   # private evaluation list, kept out of the repo
MINP={1:1500,3:4500,5:7500}
for mode,lab in (("all","all minutes (now)"),("comp","competitive minutes only")):
    for w,f in ((1,"disp1.csv"),(5,"disp5.csv"),(3,"disp3.csv")):
        d=pd.read_csv(f"../cepm/{f}"); d=d[d.poss>=MINP[w]].copy()
        d["ld"]=[load(int(p),s,w,mode) for p,s in zip(d.player,d.window_end)]; d["ce"]=d.rapm*d.ld; d["name"]=d.player.map(nm)
        best=d.dropna(subset=["ce"]).sort_values("ce",ascending=False).drop_duplicates("player").reset_index(drop=True)
        rk={n:i+1 for i,n in enumerate(best.name)}
        sub=[rk.get(n,9999) for n in T]; rho=spearmanr(range(len(T)),sub).correlation
        cur=best[best.name=="Stephen Curry"].iloc[0]
        top=", ".join(f"{n.split()[-1]} {v:+.1f}" for n,v in zip(best.name[:8],best.ce[:8]))
        print(f"{lab:26s} {w}-yr: Curry #{rk['Stephen Curry']} ({cur.window_end} {cur.ce:+.2f}) | match with your list {rho:.2f} | top: {top}")
print("--- adding the margin his team builds with him on the floor (on-court net, shrunk by sample) ---")
oo=pd.read_csv("onoff.csv"); oo=oo[oo.on_net.notna()]
g=oo.groupby(["p","season"]).apply(lambda x: pd.Series({"on":np.average(x.on_net,weights=x.op),"n":x.op.sum()}),include_groups=False).reset_index()
ON={(int(p),s):(v,n) for p,s,v,n in zip(g.p,g.season,g.on,g.n)}
d=pd.read_csv("../cepm/disp1.csv"); d=d[d.poss>=1500].copy(); d["name"]=d.player.map(nm)
d["ld"]=[load(int(p),s,1,"comp") for p,s in zip(d.player,d.window_end)]
d["onn"]=[ (lambda v: v[0]*v[1]/(v[1]+3000) if v else np.nan)(ON.get((int(p),s))) for p,s in zip(d.player,d.window_end)]
for wgt in (0.0,0.25,0.5):
    d["ce"]=((1-wgt)*d.rapm+wgt*d.onn)*d.ld
    best=d.dropna(subset=["ce"]).sort_values("ce",ascending=False).drop_duplicates("player").reset_index(drop=True); rk={n:i+1 for i,n in enumerate(best.name)}
    rho=spearmanr(range(len(T)),[rk.get(n,9999) for n in T]).correlation
    print(f"  {int(wgt*100)}% on-court margin: Curry #{rk['Stephen Curry']} | match {rho:.2f} | top: "+", ".join(f"{n.split()[-1]} {v:+.1f}" for n,v in zip(best.name[:10],best.ce[:10])))
