"""Add 1-year CEPM (each single season, cepm/disp1.csv: same engine and box prior as the 2-5 year windows, shrinkage
cross-validated per season) to data.json's rw rows as w = 1, ranked within each season like the other windows."""
import json, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]; sidx = {s: i for i, s in enumerate(S)}
kidx = {int(p): k for k, p in enumerate(D["ids"])}
rw = D["rw"]; rw["rows"] = [r for r in rw["rows"] if r[2] != 1]
t = pd.read_csv("../cepm/disp1.csv")
for s, g in t.groupby("window_end"):
    if s not in sidx: continue
    g = g.sort_values("rapm", ascending=False).reset_index(drop=True); rw["n"][f"{sidx[s]}_1"] = len(g)
    for rk, r in enumerate(g.itertuples(), 1):
        k = kidx.get(int(r.player))
        if k is not None: rw["rows"].append([k, sidx[s], 1, round(r.o_rapm, 2), round(r.d_rapm, 2), round(r.rapm, 2), rk, int(round(r.poss))])
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
print("1-year rows:", sum(r[2] == 1 for r in rw["rows"]))
nm = D["names"]
for s in ("2025-26", "2015-16"):
    top = sorted([r for r in rw["rows"] if r[2] == 1 and r[1] == sidx[s]], key=lambda r: r[6])[:6]
    print(s, [(nm[r[0]], r[5]) for r in top])
