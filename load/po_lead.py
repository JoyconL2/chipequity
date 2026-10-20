"""Playoff lead margin with opponent adjustment. For each postseason and player:
  lead stints  = playoff stints (garbage time out) where he has the highest 1-year Chip Equity regression on his side
  raw          = team margin per 100 in those stints; off / def split vs the league's regular-season points per 100
  team-adjusted   (_t) = + opponent team's regular-season strength (non-garbage ORtg / DRtg vs league)
  lineup-adjusted (_l) = + the five opponents on the floor: sum of their 1-year regression o (credited to our defense)
                         and d (credited to our offense)
  po comp share = his non-garbage playoff seconds / his team's, in playoff games he played."""
import sys, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
df = pd.read_pickle(__import__("os").environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); gt = garbage_time(df); df = df.assign(isgt=gt.values)
rs = df[(df.season_type == "rs") & ~df.isgt]; po = df[df.season_type == "po"]
C1 = pd.read_csv("../cepm/disp1.csv"); R1 = {(int(p), s): (r, o, d) for p, s, r, o, d in zip(C1.player, C1.window_end, C1.rapm, C1.o_rapm, C1.d_rapm)}

import os
_TAG = os.environ.get("LEADBY", "u2")   # lead = highest 3-year regression + 2 x (usage vs league - 1) on the floor (lead_map.py)
from lead_map import lead_map as _lm
LEADV = _lm(_TAG)

# team regular-season strength per 100 vs league (non-garbage)
TS = {}; LG = {}
for season, d in rs.groupby("season"):
    lg = 100 * (d.home_pts.sum() + d.away_pts.sum()) / (d.home_poss.sum() + d.away_poss.sum()); LG[season] = lg
    for side, opp in (("home", "away"), ("away", "home")):
        g = d.groupby(f"{side}_team")[[f"{side}_pts", f"{opp}_pts", f"{side}_poss", f"{opp}_poss"]].sum()
        for t, r in g.iterrows():
            a = TS.setdefault((season, t), [0, 0, 0, 0]); a[0] += r[f"{side}_pts"]; a[1] += r[f"{opp}_pts"]; a[2] += r[f"{side}_poss"]; a[3] += r[f"{opp}_poss"]
TSR = {k: (100 * a[0] / a[2] - LG[k[0]], LG[k[0]] - 100 * a[1] / a[3]) for k, a in TS.items()}   # (offense, defense) vs league, + = good
out = []
for season, d in po.groupby("season"):
    lg = LG[season]; acc = {}; secs = {}
    for side, opp in (("home", "away"), ("away", "home")):
        P = d[f"{side}_players"].str.split("-").values; O = d[f"{opp}_players"].str.split("-").values
        poss = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values; pf = d[f"{side}_pts"].values; pa = d[f"{opp}_pts"].values
        ot = d[f"{opp}_team"].values; g_ = d.isgt.values; sc = d.secs.values; gid = d.game_id.values; tm = d[f"{side}_team"].values
        for pl, op, w, f, a, oteam, isg, s_, gi, t in zip(P, O, poss, pf, pa, ot, g_, sc, gid, tm):
            ids_ = [int(x) for x in pl]
            if not isg:
                for p in ids_: secs.setdefault(p, {}).setdefault((t, gi), 0); secs[p][(t, gi)] += s_
                secs.setdefault(("T", t), {}).setdefault(gi, 0); secs[("T", t)][gi] += s_
            if isg or w <= 0: continue
            v = [LEADV.get((p, season), -1) for p in ids_]; best = ids_[int(np.argmax(v))]
            oo = [R1.get((int(x), season), (0, 0, 0)) for x in op]; lo = sum(x[1] for x in oo); ld = sum(x[2] for x in oo)
            to, td = TSR.get((season, oteam), (0, 0))
            x = acc.setdefault(best, np.zeros(7))
            x += [w, f, a, w * td, w * to, w * ld, w * lo]   # poss, pts for, pts against, opp team D, opp team O, opp lineup d, opp lineup o
    for p in [q for q in secs if not (isinstance(q, tuple) and q[0] == "T")]:
        x = acc.get(p, np.zeros(7)); n = x[0]
        if n <= 0:
            mine = secs[p]; tot = sum(secs[("T", t)][gi] for (t, gi) in mine)
            out.append(dict(p=p, season=season, n=0.0, off=0.0, de=0.0, lead=0.0, off_t=0.0, de_t=0.0, off_l=0.0, de_l=0.0, po_share=sum(mine.values()) / tot if tot else np.nan, po_sec=sum(mine.values()), po_tsec=tot)); continue
        off = 100 * x[1] / n - lg; de = lg - 100 * x[2] / n
        mine = secs.get(p, {}); tot = sum(secs[("T", t)][gi] for (t, gi) in mine); share = sum(mine.values()) / tot if tot else np.nan
        out.append(dict(p=p, season=season, n=n, off=off, de=de, lead=off + de,
                        off_t=off + x[3] / n, de_t=de + x[4] / n, off_l=off + x[5] / n, de_l=de + x[6] / n, po_share=share, po_sec=sum(mine.values()), po_tsec=tot))
    print(season, len(acc), flush=True)
R = pd.DataFrame(out, columns=["p", "season", "n", "off", "de", "lead", "off_t", "de_t", "off_l", "de_l", "po_share", "po_sec", "po_tsec"]); R["lead_t"] = R.off_t + R.de_t; R["lead_l"] = R.off_l + R.de_l
R.to_csv("po_lead.csv" if _TAG == "u2" else f"po_lead_{_TAG}.csv", index=False); print(len(R)); print(R.describe().round(2).to_string())
