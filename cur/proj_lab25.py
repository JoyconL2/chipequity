"""Next-season team prediction with each candidate's per-100 rating (the projection supplies minutes)."""
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
import json
src=open("../load/big_search.py").read(); g={}
exec(src[src.index("import json"):src.index("disp={1:")].replace('"../site/data.json"','"../site/data.json"').replace('pd.read_csv("margin_attr.csv")','pd.read_csv("../load/margin_attr.csv")').replace('pd.read_csv("comp_share.csv")','pd.read_csv("../load/comp_share.csv")'), g)
comps=g["comps"]; SS=g["S"]
d1=pd.read_csv(f"{SP}/cepm/disp1.csv"); C1v={(int(p),s):r for p,s,r in zip(d1.player,d1.window_end,d1.rapm)}
d3=pd.read_csv(f"{SP}/cepm/disp3.csv"); C3v={(int(p),s):r for p,s,r in zip(d3.player,d3.window_end,d3.rapm)}
SIl={s:i for i,s in enumerate(SS)}
cache={}
def rate(p,s,w,uo,b):
    key=(p,s,w,uo,b)
    if key in cache: return cache[key]
    r=C1v.get((p,s))
    if r is None: cache[key]=np.nan; return np.nan
    si=SIl[s]; c=comps(p,[s],3000)
    if c is None: cache[key]=np.nan; return np.nan
    lm=c[0]
    if b:
        j=max(si,2); r=(1-b)*r+b*C3v.get((p,SS[j]),r); x=comps(p,[SS[t] for t in range(j-2,j+1)],9000); lm=(1-b)*lm+b*(x[0] if x else lm)
    v=((1-w)*r+w*lm)*(1+uo*(c[2]-1)); cache[key]=v; return v
for tag,(w,uo,b) in {"E plain 1-yr CEPM":(0,0,0),"A/D lead 35%, steadied":(.35,0,.4),"B lead 35%, on-ball 20%, steadied":(.35,.2,.4),"C (shipped) lead 50%, on-ball 35%, steadied":(.5,.35,.4)}.items():
    rows=[]
    for (s,t),gg in R.groupby(["season","tid"]):
        sp_=S[SI[s]-1]; c=np.array([rate(int(p),sp_,w,uo,b) for p in gg.p]); k=~np.isnan(c)&(gg.gp1.values>=5)
        raw=np.where(k,np.nan_to_num(gg.mpg1.values),UMPG_ALL[s]); m=allocate(raw); sh=m/48
        rows.append({"season":s,"tid":t,"X":(sh*np.nan_to_num(c))[k].sum(),"U":sh[~k].sum()})
    F=add_targets(pd.DataFrame(rows)); F=F[F.prev.notna()&(F.season>="1999-00")].reset_index(drop=True)
    p=loso(F,["X","U"]); p=p-p.groupby(F.season).transform("mean"); score(F,p,tag)
