"""Playoff-only CEPM: one fit per postseason, using ONLY that postseason's possessions.
The box component is the same learned model as regular-season CEPM, applied to each player's PLAYOFF box stats
(per 100, relative to that postseason's average), shrunk by sample size. The ridge solve then pulls each player
toward that playoff box estimate instead of toward zero.
Output: po_cepm.csv (season, player, cepm, o, d, poss, lambda)"""
import os, subprocess, sys
import numpy as np, pandas as pd

sys.argv = [sys.argv[0]]
import box_prior as BP          # refits the box model (same data, same choices as regular-season CEPM)

co, io, cd, idf = BP.fit(np.ones(len(BP.T), bool), BP.LAM)
F = pd.read_csv("../mymodel/features_po.csv")
F["w"] = F.poss.fillna(0).clip(lower=1e-3)
agg = F.groupby(["EntityId", "Season"]).apply(
    lambda g: pd.Series({**{c: np.average(g[c].fillna(0), weights=g.w) for c in BP.FEATS}, "poss": g.poss.sum()}), include_groups=False).reset_index()
X = agg[BP.FEATS].values
shrink = agg.poss / (agg.poss + 600)                 # a few hundred playoff possessions is a small box-score sample
agg["prior_o"] = (X @ co + io) * shrink; agg["prior_d"] = (X @ cd + idf) * shrink
P = agg.rename(columns={"EntityId": "player", "Season": "window_end"})[["window_end", "player", "prior_o", "prior_d"]]
P.to_csv("prior_po.csv", index=False)

out = []
for season in sorted(P.window_end.unique()):
    f = f"../stints/stints_{season}_po.csv"
    if not os.path.exists(f): continue
    r = subprocess.run([sys.executable, "../rapm_engine.py", f, "--window", "1", "--decay", "1", "--min-poss", "150",
                        "--only-end", season, "--prior", "prior_po.csv", "--out", f"po_{season}.csv"], capture_output=True, text=True)
    if r.returncode != 0: print(season, "FAILED", r.stderr[-300:]); continue
    d = pd.read_csv(f"po_{season}.csv"); d["season"] = season; out.append(d)
    print(season, "lambda", d["lambda"].iloc[0], "| top:", ", ".join(f"{p} {v:+.1f}" for p, v in zip(d.player[:3], d.rapm[:3])))
R = pd.concat(out).rename(columns={"rapm": "cepm", "o_rapm": "o", "d_rapm": "d"})
R[["season", "player", "cepm", "o", "d", "poss", "lambda"]].to_csv("po_cepm.csv", index=False)
print("saved po_cepm.csv", len(R))
