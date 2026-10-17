src=open("margin_eval.py").read(); exec(src[:src.index("res=[]")])
from scipy.stats import spearmanr
P2=pd.DataFrame({c:D["P"][c] for c in ("p","s","t","pos","usg")}); P2=P2[P2.t==0]; P2["up"]=P2.usg*P2.pos
g=P2.groupby(["p","s"])[["up","pos"]].sum(); g["usg"]=g.up/g.pos
lg=P2.groupby("s").apply(lambda x:(x.up.sum()/x.pos.sum()),include_groups=False)
SIx={s:i for i,s in enumerate(S)}; kOf={p:k for k,p in enumerate(ids)}
USG={}
for (k,s),r in g.iterrows(): USG[(ids[k],S[s])]=min(2.0,max(0.5,r.usg/lg[s]))
d["usgR"]=[USG.get((int(p),s),1.0) for p,s in zip(d.player,d.window_end)]
d["m_lead"]=[mval(p,s,"lead") for p,s in zip(d.player,d.window_end)]
MUST=_EV.get("MUST", [])
res=[]
for w in (0.25,0.35,0.5):
    for u in (0.0,0.15,0.25,0.35,0.5):
        d["ce"]=((1-w)*d.rapm+w*d.m_lead)*d.ld*(1+u*(d.usgR-1))
        best=d.dropna(subset=["ce"]).sort_values("ce",ascending=False).drop_duplicates("player").reset_index(drop=True); rk={n:i+1 for i,n in enumerate(best.name)}
        rho=spearmanr(range(len(T)),[rk.get(n,9999) for n in T]).correlation
        res.append((sum(rk.get(n,999)<=25 for n in MUST),rho,w,u,{n.split()[-1]:rk.get(n) for n in MUST},rk["Stephen Curry"],rk.get("Draymond Green")))
for r in sorted(res,key=lambda x:(-x[0],-x[1]))[:10]: print(f"{r[0]}/5 in top 25 | match {r[1]:.2f} | margin {int(r[2]*100)}% usage {int(r[3]*100)}% | {r[4]} | Curry #{r[5]} Draymond #{r[6]}")
