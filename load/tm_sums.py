"""For every player-season: in the stints where he is the lead (highest 3-year regression on his side, garbage time out),
the possession-weighted sum of his four teammates' 3-year offensive and defensive ratings. Regular season and playoffs.
Used to adjust lead margin for teammate quality: lead - beta x (teammates' o + d)."""
import sys, numpy as np, pandas as pd, os
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
os.environ.setdefault("LEADBY", "r3")
exec(open("margin_attr_od.py").read().split("import os")[1].split("LEADV = _lead_map()")[0].replace("\n_TAG", "\nimport os\n_TAG", 1) if False else "")
d1 = pd.read_csv("../cepm/disp1.csv"); d3 = pd.read_csv("../cepm/disp3.csv")
m1 = {(int(p), s): r for p, s, r in zip(d1.player, d1.window_end, d1.rapm)}
R3 = {(int(p), s): (r, o, d) for p, s, r, o, d in zip(d3.player, d3.window_end, d3.rapm, d3.o_rapm, d3.d_rapm)}
from lead_map import lead_map; LEADV = lead_map(os.environ.get("LEADBY", "u2"))
df = pd.read_pickle(__import__("os").environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); g = garbage_time(df).values
out = []
for stype in ("rs", "po"):
    d_all = df[(df.season_type == stype) & ~g]
    for season, d in d_all.groupby("season"):
        acc = {}
        for side, opp in (("home", "away"), ("away", "home")):
            P = d[f"{side}_players"].str.split("-").values; poss = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values
            for pl, w in zip(P, poss):
                if w <= 0: continue
                ids_ = [int(x) for x in pl]; v = [LEADV.get((p, season), -1) for p in ids_]; b = int(np.argmax(v))
                rr = [R3.get((p, season), (0.0, 0.0, 0.0)) for p in ids_]
                to = sum(x[1] for j, x in enumerate(rr) if j != b); td = sum(x[2] for j, x in enumerate(rr) if j != b)
                a = acc.setdefault(ids_[b], [0.0, 0.0, 0.0]); a[0] += w; a[1] += w * to; a[2] += w * td
        for p, a in acc.items(): out.append(dict(p=p, season=season, stype=stype, n=a[0], tmo=a[1] / a[0], tmd=a[2] / a[0]))
        print(stype, season, len(acc), flush=True)
R = pd.DataFrame(out); _t = os.environ.get("LEADBY", "b1"); R.to_csv("tm_sums.csv" if _t == "b1" else f"tm_sums_{_t}.csv", index=False); print(R.groupby("stype")[["tmo", "tmd"]].describe().round(2).T)
