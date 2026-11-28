"""Playoff defensive credit (1.1): half of each playoff stint's defense goes to the best defender on the floor, the other
half stays with the stint's lead (po_lead.py); chip_build.py mixes the two.
  best defender = the highest 3-year defensive regression rating among the five (window ending that season; 1-year if
                  he has no 3-year window; -1 if unrated)
Per player-season: dposs = playoff possessions as the best defender on the floor (garbage time out), dlead = defensive margin
per 100 in them (league regular-season points per 100 minus points allowed, plus the opponent's regular-season offense vs
league, as in po_lead.py), dtm = the other four players' 3-year defense in them (for the teammate adjustment).
Writes po_def.csv."""
import os, sys, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
df = pd.read_pickle(os.environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); gt = garbage_time(df); df = df.assign(isgt=gt.values)
rs = df[(df.season_type == "rs") & ~df.isgt]; po = df[(df.season_type == "po") & ~df.isgt]
d1 = pd.read_csv("../cepm/disp1.csv"); d3 = pd.read_csv("../cepm/disp3.csv")
D3 = {(int(p), s): d for p, s, d in zip(d3.player, d3.window_end, d3.d_rapm)}
PICK = {(int(p), s): D3.get((int(p), s), d) for p, s, d in zip(d1.player, d1.window_end, d1.d_rapm)}   # 3-year, else 1-year
# team regular-season offense per 100 vs league (non-garbage), as in po_lead.py
LG, TO = {}, {}
for season, d in rs.groupby("season"):
    lg = 100 * (d.home_pts.sum() + d.away_pts.sum()) / (d.home_poss.sum() + d.away_poss.sum()); LG[season] = lg
    acc = {}
    for side in ("home", "away"):
        g = d.groupby(f"{side}_team")[[f"{side}_pts", f"{side}_poss"]].sum()
        for t, r in g.iterrows():
            a = acc.setdefault(t, [0.0, 0.0]); a[0] += r[f"{side}_pts"]; a[1] += r[f"{side}_poss"]
    for t, a in acc.items(): TO[(season, t)] = 100 * a[0] / a[1] - lg
rows = []
for season, d in po.groupby("season"):
    lg = LG[season]; parts = []
    for side, opp in (("home", "away"), ("away", "home")):
        w = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values; keep = w > 0
        P5 = np.array([[int(x) for x in s_.split("-")] for s_ in d[f"{side}_players"].values[keep]], dtype=np.int64)
        w = w[keep]; pa = d[f"{opp}_pts"].values[keep].astype(float); to = np.array([TO.get((season, t), 0.0) for t in d[f"{opp}_team"].values[keep]])
        u, inv = np.unique(P5, return_inverse=True); inv = inv.reshape(P5.shape)
        sc = np.array([PICK.get((int(p), season), -1.0) for p in u])[inv]
        td = np.array([D3.get((int(p), season), 0.0) for p in u])[inv]
        W = np.zeros(sc.shape); W[np.arange(len(sc)), sc.argmax(1)] = 1.0      # the best defender on the floor
        defw = w * lg - 100 * pa + w * to                                    # possessions x opponent-adjusted defensive margin per 100
        wd = w[:, None] * W; tm = td.sum(1, keepdims=True) - td
        parts.append(pd.DataFrame({"p": P5.ravel(), "a": wd.ravel(), "b": (defw[:, None] * W).ravel(), "c": (wd * tm).ravel()}))
    acc = pd.concat(parts).groupby("p")[["a", "b", "c"]].sum()
    for p, r in acc[acc.a > 0].iterrows(): rows.append(dict(p=int(p), season=season, dposs=r.a, dlead=r.b / r.a, dtm=r.c / r.a))
    print(season, len(acc), flush=True)
pd.DataFrame(rows, columns=["p", "season", "dposs", "dlead", "dtm"]).to_csv("po_def.csv", index=False); print(len(rows))
