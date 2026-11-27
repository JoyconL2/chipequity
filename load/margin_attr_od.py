"""Ways to credit the margin a lineup builds to the players in it (regular season, garbage time out):
  on      : plain on-court margin (everyone on the floor gets the full margin)
  share   : each stint's margin split by the players' positive 1-year CEPM (stars get most of it), x5 to keep the scale
  lead    : margin only in stints where he is the best player on the floor (by 1-year CEPM)
  rel     : on-court margin minus his teammates' average on-court margin (minutes together weighted)"""
import sys, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
df = pd.read_pickle(__import__("os").environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); df = df[(df.season_type == "rs")].copy(); df = df[~garbage_time(df)]

import os
_TAG = os.environ.get("LEADBY", "b1")   # lead = highest 3-year regression + (shot creation vs league - 1) + (usage vs league - 1) on the floor (lead_map.py)
from lead_map import lead_map as _lm
LEADV = _lm(_TAG)
cep = LEADV
out = {}
for season, d in df.groupby("season"):
    acc = {}
    for side, opp in (("home", "away"), ("away", "home")):
        pl = d[f"{side}_players"].str.split("-").values; poss = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values
        mg = np.where(poss > 0, 100 * (d[f"{side}_pts"] - d[f"{opp}_pts"]).values / np.maximum(poss, 1e-9), 0.0)
        pf_ = d[f"{side}_pts"].values; pa_ = d[f"{opp}_pts"].values
        for players, w, m, pf1, pa1 in zip(pl, poss, mg, pf_, pa_):
            if w <= 0: continue
            ids_ = [int(x) for x in players]; v = [cep.get((p, season), -1.0) for p in ids_]; pos = [max(x, 0.0) for x in v]; tot = sum(pos)
            best = int(np.argmax(v))
            for j, p in enumerate(ids_):
                a = acc.setdefault(p, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])   # poss, on*poss, share*poss, lead_poss, lead*poss, teammates-on sum
                a[0] += w; a[1] += w * m; a[2] += w * m * (5 * pos[j] / tot if tot > 0 else 1.0)
                if j == best: a[3] += w; a[4] += w * m; a[6] += pf1; a[7] += pa1
    lg = 100 * (d.home_pts.sum() + d.away_pts.sum()) / (d.home_poss.sum() + d.away_poss.sum())    # league points per 100, non-garbage
    for p, a in acc.items(): out[(p, season)] = a + [lg]
    print(season, len(acc), flush=True)
rows = [dict(p=p, season=s, poss=a[0], on=a[1] / a[0], share=a[2] / a[0], lead_poss=a[3], lead=(a[4] / a[3] if a[3] > 0 else 0.0), lead_off=(100 * a[6] / a[3] - a[8] if a[3] > 0 else 0.0), lead_def=(a[8] - 100 * a[7] / a[3] if a[3] > 0 else 0.0)) for (p, s), a in out.items()]
R = pd.DataFrame(rows)
# rel: on-court margin minus teammates' on-court margin, weighted by their minutes together (approx: team-season average of teammates' on)
R.to_csv("margin_attr_od.csv" if _TAG == "b1" else f"margin_attr_od_{_TAG}.csv", index=False); print(len(R))
