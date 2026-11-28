"""Defensive credit (1.1): the defensive half of each regular-season stint's margin goes to the best defender on the floor
instead of the stint's lead.
  best defender = the highest 3-year defensive regression rating among the five (window ending that season; 1-year if he
                  has no 3-year window; -1 if unrated)
Per player-season: dposs = possessions as the best defender on the floor, dlead = defensive margin per 100 in them (league
points per 100 minus points allowed, garbage time out), dtm = the other four players' 3-year defense in them (for the
teammate adjustment in chip_build.py). Playoff defense is split half to the lead (po_lead.py), half to the best defender (po_def.py).
Writes def_share.csv. Tested 1997-2026 with the rest of 1.1 on next-season team prediction."""
import os, sys, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
df = pd.read_pickle(os.environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); df = df[df.season_type == "rs"].copy(); df = df[~garbage_time(df)]
d1 = pd.read_csv("../cepm/disp1.csv"); d3 = pd.read_csv("../cepm/disp3.csv")
D3 = {(int(p), s): d for p, s, d in zip(d3.player, d3.window_end, d3.d_rapm)}
PICK = {(int(p), s): D3.get((int(p), s), d) for p, s, d in zip(d1.player, d1.window_end, d1.d_rapm)}   # 3-year, else 1-year
rows = []
for season, d in df.groupby("season"):
    lg = 100 * (d.home_pts.sum() + d.away_pts.sum()) / (d.home_poss.sum() + d.away_poss.sum())    # league points per 100, non-garbage
    parts = []
    for side, opp in (("home", "away"), ("away", "home")):
        w = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values; keep = w > 0
        P5 = np.array([[int(x) for x in s_.split("-")] for s_ in d[f"{side}_players"].values[keep]], dtype=np.int64)
        w = w[keep]; pa = d[f"{opp}_pts"].values[keep].astype(float)
        u, inv = np.unique(P5, return_inverse=True); inv = inv.reshape(P5.shape)
        sc = np.array([PICK.get((int(p), season), -1.0) for p in u])[inv]
        td = np.array([D3.get((int(p), season), 0.0) for p in u])[inv]
        W = np.zeros(sc.shape); W[np.arange(len(sc)), sc.argmax(1)] = 1.0      # the best defender on the floor takes it all
        defw = w * lg - 100 * pa                                   # possessions x defensive margin per 100
        wd = w[:, None] * W; tm = td.sum(1, keepdims=True) - td
        parts.append(pd.DataFrame({"p": P5.ravel(), "a": wd.ravel(), "b": (defw[:, None] * W).ravel(), "c": (wd * tm).ravel()}))
    acc = pd.concat(parts).groupby("p")[["a", "b", "c"]].sum()
    for p, r in acc[acc.a > 0].iterrows(): rows.append(dict(p=int(p), season=season, dposs=r.a, dlead=r.b / r.a, dtm=r.c / r.a))
    print(season, len(acc), flush=True)
pd.DataFrame(rows).to_csv("def_share.csv", index=False); print(len(rows))
