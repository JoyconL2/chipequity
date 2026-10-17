"""Put our own RAPM (rapm_out/*.csv) into data.json in the shape the site already reads (rw + peak).
Base = data_pre_mymodel.json (the last consistent data file); nbarapm values are replaced entirely."""
import json, os
import pandas as pd

R = "../cepm"
d = json.load(open("data_1996.json"))
S = d["seasons"]; sidx = {s: i for i, s in enumerate(S)}
kidx = {int(pid): k for k, pid in enumerate(d["ids"])}

# ---- windows ending each season (2-year, 3-year) ----
rows, n = [], {}
wins = {}
for w in (2, 3, 4, 5):
    f = f"{R}/disp{w}.csv"
    if not os.path.exists(f): continue
    t = pd.read_csv(f); t["w"] = w; wins[w] = t
for w in (2, 3):
    if w not in wins: continue
    t = wins[w]
    for s, g in t.groupby("window_end"):
        g = g.sort_values("rapm", ascending=False).reset_index(drop=True)
        g["rank"] = g.index + 1
        if s in sidx: n[f"{sidx[s]}_{w}"] = len(g)
        for r in g.itertuples():
            k = kidx.get(int(r.player))
            if k is None or s not in sidx: continue
            rows.append([k, sidx[s], w, round(r.o_rapm, 2), round(r.d_rapm, 2), round(r.rapm, 2), int(r.rank), int(round(r.poss))])
d["rw"] = {"rows": rows, "n": n, "src": "CEPM (Chip Equity Plus-Minus): RAPM on every possession since 1996-97 (regular season + playoffs), shrunk toward a box-score estimate instead of zero"}

# ---- peaks (best window of n straight seasons) + decades ----
DS, NS, prow = [], [], []
MINP = {2: 3000, 3: 4500, 4: 6000, 5: 7500}
for w in (2, 3, 4, 5):
    if w not in wins: continue
    t = wins[w]; t = t[t.poss >= MINP[w]]
    best = t.sort_values("rapm", ascending=False).drop_duplicates("player").reset_index(drop=True)
    j = len(DS); DS.append(f"Peak {w}Y CEPM"); NS.append(len(best))
    for rank, r in enumerate(best.itertuples(), 1):
        k = kidx.get(int(r.player))
        if k is not None: prow.append([k, j, round(r.o_rapm, 2), round(r.d_rapm, 2), round(r.rapm, 2), rank])
for dec, f in (("1990s", "ddec1990"), ("2000s", "ddec2000"), ("2010s", "ddec2010"), ("2020s", "ddec2020")):
    p = f"{R}/{f}.csv"
    if not os.path.exists(p): continue
    t = pd.read_csv(p); t = t[t.poss >= 3000].sort_values("rapm", ascending=False).reset_index(drop=True)
    j = len(DS); DS.append(f"{dec} CEPM"); NS.append(len(t))
    for rank, r in enumerate(t.itertuples(), 1):
        k = kidx.get(int(r.player))
        if k is not None: prow.append([k, j, round(r.o_rapm, 2), round(r.d_rapm, 2), round(r.rapm, 2), rank])
d["peak"] = {"ds": DS, "n": NS, "rows": prow, "src": "CEPM (best 2- to 5-season windows since 1996-97; decade = one fit per decade)"}
# regular-season-only 3-year CEPM for the playoff model (never sees the playoffs it predicts)
M = pd.read_csv(f"{R}/cepm3_rs.csv")
d["rwm"] = [[kidx[int(r.player)], sidx[r.window_end], round(r.rapm, 2)] for r in M.itertuples() if int(r.player) in kidx and r.window_end in sidx]
json.dump(d, open("data.json", "w"), separators=(",", ":"), allow_nan=False)
print("rw rows", len(rows), "| peak sets", list(zip(DS, NS)))
