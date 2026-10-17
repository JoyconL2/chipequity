"""Exhaustive search for a single 'Chip Equity' stat. Levers:
  w   lead-margin weight (0 = plain CEPM)          a   minutes exponent on competitive share (0 = pure per-100 rate)
  uo  on-ball bonus                                b   single-season steadying toward the 3-season window
  sh  single-season shrinkage: lighter for heavy-minute players (current) or uniform
Score: rank correlation with a private evaluation list on the best single season, best 3-year and best 5-year boards."""
import json, itertools, numpy as np, pandas as pd
from scipy.stats import spearmanr
D=json.load(open("../site/data.json")); S=D["seasons"]; SI={s:i for i,s in enumerate(S)}; ids=[int(x) for x in D["ids"]]; nm={p:D["names"][k] for k,p in enumerate(ids)}
M=pd.read_csv("margin_attr.csv"); LEAD={(int(p),s):(v,n) for p,s,v,n in zip(M.p,M.season,M.lead,M.lead_poss)}
C=pd.read_csv("comp_share.csv"); COMP={(int(p),s):(a,b) for p,s,a,b in zip(C.p,C.season,C.comp,C.t_comp)}
P=pd.DataFrame({c:D["P"][c] for c in ("p","s","t","pos","fg2a","fg3a","fta","tov","ast")}); P=P[P.t==0]; P["ob"]=P.fg2a+P.fg3a+0.44*P.fta+P.tov+P.ast
lgr=(P.groupby("s").ob.sum()/P.groupby("s").pos.sum()).to_dict(); g=P.groupby(["p","s"])[["ob","pos"]].sum()
OBC={(ids[k],S[s]):(r.ob,r.pos,lgr[s]) for (k,s),r in g.iterrows()}
import json as _j, os as _o; _EV = next((_j.load(open(_f)) for _f in ("eval_list.json", "../load/eval_list.json") if _o.path.exists(_f)), {}); T = _EV.get("T", [])   # private evaluation list, kept out of the repo
MINP={1:1500,3:4500,5:7500}
def comps(p,seas,K):
    ln=lnn=ca=cb=ob=pos=lpos=0.0
    for s in seas:
        v=LEAD.get((p,s)); c=COMP.get((p,s)); o=OBC.get((p,s))
        if v: ln+=v[0]*v[1]; lnn+=v[1]
        if c: ca+=c[0]; cb+=c[1]
        if o: ob+=o[0]; pos+=o[1]; lpos+=o[2]*o[1]
    if cb<=0 or pos<=0: return None
    return ((ln/lnn)*lnn/(lnn+K) if lnn else 0.0), ca/cb, min(2,max(.5,(ob/pos)/(lpos/pos)))
disp={1:pd.read_csv("../cepm/disp1.csv"),"1u":pd.read_csv("../cepm/disp1_uniform.csv"),3:pd.read_csv("../cepm/disp3.csv"),5:pd.read_csv("../cepm/disp5.csv")}
C3={(int(p),s):r for p,s,r in zip(disp[3].player,disp[3].window_end,disp[3].rapm)}
# precompute rows: (player, window, cepm, lead, share, ob, c3, l3)
pre={}
for key,win in ((1,1),("1u",1),(3,3),(5,5)):
    d=disp[key]; d=d[d.poss>=MINP[win]]
    if win==1: d=d[d.window_end!="1996-97"]
    rows=[]
    for p,r,we in zip(d.player,d.rapm,d.window_end):
        p=int(p); si=SI[we]; c=comps(p,[S[x] for x in range(max(0,si-win+1),si+1)],3000)
        if c is None: continue
        c3=l3=None
        if win==1:
            j=max(si,2); c3=C3.get((p,S[j]),r); x=comps(p,[S[x] for x in range(j-2,j+1)],9000); l3=x[0] if x else c[0]
        rows.append((p,we,r,c[0],c[1],c[2],c3,l3))
    pre[key]=pd.DataFrame(rows,columns=["p","we","r","lead","share","ob","c3","l3"])
def board(df,w,a,uo,b):
    r=df.r if b==0 else (1-b)*df.r+b*df.c3; lm=df.lead if b==0 else (1-b)*df.lead+b*df.l3
    v=((1-w)*r+w*lm)*df.share**a*(1+uo*(df.ob-1))
    best=pd.DataFrame({"p":df.p,"v":v}).sort_values("v",ascending=False).drop_duplicates("p")
    rk={nm[p]:i+1 for i,p in enumerate(best.p)}
    return spearmanr(range(len(T)),[rk.get(n,9999) for n in T]).correlation, rk
res=[]
for w,a,uo,b,sh in itertools.product((0,.25,.35,.5,.65),(0,.5,1),(0,.2,.35,.5),(0,.4),(1,"1u")):
    m1,rk1=board(pre[sh],w,a,uo,b); m3,rk3=board(pre[3],w,a,uo,0); m5,rk5=board(pre[5],w,a,uo,0)
    res.append(dict(w=w,a=a,uo=uo,b=b,sh="lighter" if sh==1 else "uniform",m1=m1,m3=m3,m5=m5,mean=(m1+m3+m5)/3,
                    lebron1=rk5["LeBron James"],curry=rk5["Stephen Curry"],kobe=rk5["Kobe Bryant"],harden=rk5["James Harden"],nash=rk5["Steve Nash"],
                    s_lebron=rk1["LeBron James"],s_curry=rk1["Stephen Curry"],s_kobe=rk1["Kobe Bryant"],s_harden=rk1["James Harden"],s_nash=rk1["Steve Nash"],s_embiid=rk1["Joel Embiid"],s_tatum=rk1.get("Jayson Tatum")))
R=pd.DataFrame(res).sort_values("mean",ascending=False); R.to_csv("big_search.csv",index=False)
pd.set_option("display.width",250)
print(len(R),"combinations"); print(R.head(15).round(2).to_string(index=False))
print("--- best pure per-100 rate (a=0)"); print(R[R.a==0].head(5).round(2).to_string(index=False))
