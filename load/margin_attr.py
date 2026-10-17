"""Ways to credit the margin a lineup builds to the players in it (regular season, garbage time out):
  on      : plain on-court margin (everyone on the floor gets the full margin)
  share   : each stint's margin split by the players' positive 1-year CEPM (stars get most of it), x5 to keep the scale
  lead    : margin only in stints where he is the best player on the floor (by 1-year CEPM)
  rel     : on-court margin minus his teammates' average on-court margin (minutes together weighted)"""
import sys, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
df = pd.read_pickle("../rapm_out/stints_all.pkl"); df = df[(df.season_type == "rs")].copy(); df = df[~garbage_time(df)]
C1 = pd.read_csv("../cepm/disp1.csv"); cep = {(int(p), s): r for p, s, r in zip(C1.player, C1.window_end, C1.rapm)}
out = {}
for season, d in df.groupby("season"):
    acc = {}
    for side, opp in (("home", "away"), ("away", "home")):
        pl = d[f"{side}_players"].str.split("-").values; poss = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values
        mg = np.where(poss > 0, 100 * (d[f"{side}_pts"] - d[f"{opp}_pts"]).values / np.maximum(poss, 1e-9), 0.0)
        for players, w, m in zip(pl, poss, mg):
            if w <= 0: continue
            ids_ = [int(x) for x in players]; v = [cep.get((p, season), -1.0) for p in ids_]; pos = [max(x, 0.0) for x in v]; tot = sum(pos)
            best = int(np.argmax(v))
            for j, p in enumerate(ids_):
                a = acc.setdefault(p, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])   # poss, on*poss, share*poss, lead_poss, lead*poss, teammates-on sum
                a[0] += w; a[1] += w * m; a[2] += w * m * (5 * pos[j] / tot if tot > 0 else 1.0)
                if j == best: a[3] += w; a[4] += w * m
    for p, a in acc.items(): out[(p, season)] = a
    print(season, len(acc), flush=True)
rows = [dict(p=p, season=s, poss=a[0], on=a[1] / a[0], share=a[2] / a[0], lead_poss=a[3], lead=(a[4] / a[3] if a[3] > 0 else 0.0)) for (p, s), a in out.items()]
R = pd.DataFrame(rows)
# rel: on-court margin minus teammates' on-court margin, weighted by their minutes together (approx: team-season average of teammates' on)
R.to_csv("margin_attr.csv", index=False); print(len(R))
