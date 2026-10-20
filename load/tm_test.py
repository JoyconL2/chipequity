"""Teammate-adjusted lead margin: lead - beta x (teammates' 3-year o + d, centred on the season average). Ranking check."""
import os, json, numpy as np, pandas as pd
BETA = float(os.environ.get("BETA", "0"))
g = {}; exec(open("po_test.py").read().split('if __name__ == "__main__":')[0], g)
TM = pd.read_csv("tm_sums.csv"); TM["tm"] = TM.tmo + TM.tmd
cen = (TM.assign(w=TM.tm * TM.n).groupby(["stype", "season"]).w.sum() / TM.groupby(["stype", "season"]).n.sum()).to_dict()
TMD = {(int(p), s, t): v - cen[(t, s)] for p, s, t, v in zip(TM.p, TM.season, TM.stype, TM.tm)}
chk = TM[TM.stype == "rs"].merge(g["M"], on=["p", "season"]); print("n match rs:", round(float((chk.n - chk.lead_poss).abs().max()), 1))
L = g["LEAD"]; 
for (p, s), (n, v) in list(L.items()): L[(p, s)] = (n, v - BETA * TMD.get((p, s, "rs"), 0.0))
for (p, s), q in g["POL"].items(): q["lead_t"] = q["lead_t"] - BETA * TMD.get((p, s, "po"), 0.0) if q["n"] > 0 else q["lead_t"]
res = {w: g["match"](g["board"](w, 2, "t", "rs")) for w in (1, 3, 5)}
nm = g["nm"]; T = g["T"]
print(f"beta {BETA}: match", [round(res[w][0], 3) for w in (1, 3, 5)], "mean", round(np.mean([res[w][0] for w in (1, 3, 5)]), 3))
B1 = g["board"](1, 2, "t", "rs"); B1 = B1.sort_values("v", ascending=False).reset_index(drop=True)
pid = {v: k for k, v in nm.items()}
for who, s in (("Kevin Garnett", "2002-03"), ("Kevin Garnett", "2003-04"), ("Kevin Garnett", "2004-05"), ("LeBron James", "2017-18"), ("LeBron James", "2008-09"), ("Stephen Curry", "2016-17"), ("Draymond Green", "2015-16")):
    x = B1[(B1.p == pid[who]) & (B1.s == s)]
    if len(x): print(f"   {who} {s}: {x.v.iloc[0]:+.2f}  (#{x.index[0] + 1} of all seasons)")
print("   5y ranks:", {n.split()[-1]: res[5][1].get(n) for n in ("Kevin Garnett", "LeBron James", "Stephen Curry", "Michael Jordan", "Kobe Bryant", "Tim Duncan")})
