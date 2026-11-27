"""Shared defensive credit (1.1): the defensive half of each regular-season stint's margin is shared among the five
players on the floor instead of going to the stint's lead.
  score  = 3-year defensive regression (window ending that season; 1-year if none; -1 if unrated)
           + (defensive activity / league - 1), activity = (steals + blocks + 0.3 x defensive rebounds) per possession,
           capped at 0.3 to 2.5 x league (data.json, regular season)
  share  = max(score + 1, 0) / sum over the five (equal fifths if all are zero)
Per player-season: dposs = sum of possessions x share, dlead = his share-weighted defensive margin per 100 (league points
per 100 minus points allowed, garbage time out), dtm = share-weighted sum of the other four players' 3-year defense
(for the teammate adjustment in chip_build.py). Playoffs keep one lead for both ends (po_lead.py).
Writes def_share.csv. Tested 1997-2026 with the rest of 1.1: better next-season team prediction than one lead for both ends."""
import os, sys, json, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
df = pd.read_pickle(os.environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); df = df[df.season_type == "rs"].copy(); df = df[~garbage_time(df)]
d1 = pd.read_csv("../cepm/disp1.csv"); d3 = pd.read_csv("../cepm/disp3.csv")
D3 = {(int(p), s): d for p, s, d in zip(d3.player, d3.window_end, d3.d_rapm)}
PICK = {(int(p), s): D3.get((int(p), s), d) for p, s, d in zip(d1.player, d1.window_end, d1.d_rapm)}   # 3-year, else 1-year
D = json.load(open("../site/data.json")); S = D["seasons"]; ids = [int(x) for x in D["ids"]]
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "pos", "stl", "blk", "dreb")}); P = P[P.t == 0]
g = P.groupby(["p", "s"])[["pos", "stl", "blk", "dreb"]].sum(); g = g[g.pos > 0]; L = P.groupby("s")[["pos", "stl", "blk", "dreb"]].sum()
lga = ((L.stl + L.blk + 0.3 * L.dreb) / L.pos).to_dict()
ACT = {(ids[k], S[s]): min(2.5, max(0.3, ((r.stl + r.blk + 0.3 * r.dreb) / r.pos) / lga[s])) for (k, s), r in g.iterrows()}
rows = []
for season, d in df.groupby("season"):
    lg = 100 * (d.home_pts.sum() + d.away_pts.sum()) / (d.home_poss.sum() + d.away_poss.sum())    # league points per 100, non-garbage
    parts = []
    for side, opp in (("home", "away"), ("away", "home")):
        w = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values; keep = w > 0
        P5 = np.array([[int(x) for x in s_.split("-")] for s_ in d[f"{side}_players"].values[keep]], dtype=np.int64)
        w = w[keep]; pa = d[f"{opp}_pts"].values[keep].astype(float)
        u, inv = np.unique(P5, return_inverse=True); inv = inv.reshape(P5.shape)
        sc = np.array([PICK.get((int(p), season), -1.0) + (ACT.get((int(p), season), 1.0) - 1.0) for p in u])[inv]
        td = np.array([D3.get((int(p), season), 0.0) for p in u])[inv]
        x = np.maximum(sc + 1.0, 0.0); t = x.sum(1, keepdims=True); W = np.where(t > 0, x / np.where(t > 0, t, 1.0), 0.2)
        defw = w * lg - 100 * pa                                   # possessions x defensive margin per 100
        wd = w[:, None] * W; tm = td.sum(1, keepdims=True) - td
        parts.append(pd.DataFrame({"p": P5.ravel(), "a": wd.ravel(), "b": (defw[:, None] * W).ravel(), "c": (wd * tm).ravel()}))
    acc = pd.concat(parts).groupby("p")[["a", "b", "c"]].sum()
    for p, r in acc[acc.a > 0].iterrows(): rows.append(dict(p=int(p), season=season, dposs=r.a, dlead=r.b / r.a, dtm=r.c / r.a))
    print(season, len(acc), flush=True)
pd.DataFrame(rows).to_csv("def_share.csv", index=False); print(len(rows))
