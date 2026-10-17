"""Candidate Chip Equity (single season): 50% CEPM + 50% lead margin, steadied 40% toward the surrounding 3 seasons,
x share of competitive minutes x (1 + 0.35 (on-ball share ratio - 1))."""
src=open("grid_t25.py").read(); src=src[:src.index("MUST=")]; exec(src)
import sys
P3=pd.DataFrame({c:D["P"][c] for c in ("p","s","t","pos","fg2a","fg3a","fta","tov","ast")}); P3=P3[P3.t==0]; P3["ob"]=P3.fg2a+P3.fg3a+0.44*P3.fta+P3.tov+P3.ast
g3=P3.groupby(["p","s"])[["ob","pos"]].sum(); lg3=P3.groupby("s").apply(lambda x: x.ob.sum()/x.pos.sum(),include_groups=False)
OB={(ids[k],S[s]):min(2.0,max(0.5,(r.ob/r.pos)/lg3[s])) for (k,s),r in g3.iterrows() if r.pos>0}
d["obR"]=[OB.get((int(p),s),1.0) for p,s in zip(d.player,d.window_end)]
c3=pd.read_csv("../cepm/disp3.csv"); C3={(int(p),s):r for p,s,r in zip(c3.player,c3.window_end,c3.rapm)}
SI_={s:i for i,s in enumerate(S)}; LM={k:(r.lead,r.lead_poss) for k,r in MA.items()}
CENTER = "center" in sys.argv
def win_end(s):          # the 3-season window used to steady season s
    i=SI_[s]
    if CENTER: i=min(max(i+1,2),len(S)-1)   # surrounding seasons (s-1..s+1); clamp at the ends of the data
    elif i < 2: i = 2                        # no trailing 3-year window yet (1996-97, 1997-98): use the first full one
    return i
def c3v(p,s):
    i=win_end(s); return C3.get((int(p),S[i]),np.nan)
def lead3(p,s):
    i=win_end(s); num=den=0.0
    for x in range(i-2,i+1):
        if x<0: continue
        v=LM.get((int(p),S[x]))
        if v: num+=v[0]*v[1]; den+=v[1]
    return (num/den)*den/(den+9000) if den else 0.0
d["c3"]=[c3v(p,s) for p,s in zip(d.player,d.window_end)]; d["c3"]=d.c3.fillna(d.rapm); d["l3"]=[lead3(p,s) for p,s in zip(d.player,d.window_end)]
b,w,uo=0.4,0.5,0.35
ERA = "era" in sys.argv
if ERA:
    era=d.groupby("window_end").ld.apply(lambda x: x.nlargest(60).mean()); d["ld"]=d.ld*era.median()/d.window_end.map(era)
d["ce"]=((1-w)*((1-b)*d.rapm+b*d.c3)+w*((1-b)*d.m_lead+b*d.l3))*d.ld*(1+uo*(d.obR-1))
best=d.dropna(subset=["ce"]).sort_values("ce",ascending=False).drop_duplicates("player").reset_index(drop=True); rk={n:i+1 for i,n in enumerate(best.name)}
rho=spearmanr(range(len(T)),[rk.get(n,9999) for n in T]).correlation
print(("CENTERED" if CENTER else "TRAILING (first full window for 96-98)") + (" + era minutes" if ERA else ""), f"match {rho:.2f} | Blaylock #{rk.get('Mookie Blaylock')} Hardaway #{rk.get('Tim Hardaway')} Tatum #{rk['Jayson Tatum']} Westbrook #{rk['Russell Westbrook']}")
if 'show' in sys.argv:
    for i,r in best.head(25).iterrows(): print(f"{i+1:2d}. {r['name']} {r.window_end}: {r.ce:+.2f}")
