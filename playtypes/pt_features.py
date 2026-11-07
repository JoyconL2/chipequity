"""Play-type features per player-season: per-75-possession rates and points per shot, relative to that season's league."""
import json, numpy as np, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]; ids = [int(x) for x in D["ids"]]
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "pos")}); P = P[P.t == 0]
POS = {(ids[k], S[s]): v for k, s, v in zip(P.p, P.s, P.pos)}
d = pd.read_csv("playtypes.csv").fillna(0); d["pos"] = [POS.get((int(p), s), np.nan) for p, s in zip(d.p, d.season)]
# 300+ possessions; the season being played can set its own early-season minimum: PT_CUR="2026-27:120"
import os
cur, cmin = (os.environ.get("PT_CUR", "") + ":").split(":")[:2]
d = d[(d.pos > 300) | ((d.season == cur) & (d.pos > float(cmin or 300)))].copy()
lg = d.groupby("season").sum(numeric_only=True)
for z in ("rim", "mid", "three"):
    lgua = (lg[f"{z}_ua"] / lg[f"{z}_fgm"]).to_dict()
    ua = (d[f"{z}_ua"] + 8 * d.season.map(lgua)) / (d[f"{z}_fgm"] + 8)          # unassisted share, shrunk to league
    d[f"{z}_self"] = d[f"{z}_fga"] * ua; d[f"{z}_setup"] = d[f"{z}_fga"] * (1 - ua)
cats = ["transition", "putback", "rim", "mid", "three"]
F = pd.DataFrame({"p": d.p.astype(int), "season": d.season, "pos": d.pos})
for c in ["transition_fga", "putback_fga", "rim_self", "rim_setup", "mid_self", "mid_setup", "three_self", "three_setup", "ast_rim", "ast_mid", "ast_three", "ast_transition"]:
    F[c + "75"] = 75 * d[c] / d.pos
for c in cats:   # points per shot vs league, shrunk (100 shots)
    lpps = (lg[f"{c}_pts"] / lg[f"{c}_fga"]).to_dict(); m = d.season.map(lpps)
    F[c + "_pps"] = (d[f"{c}_pts"] + 100 * m) / (d[f"{c}_fga"] + 100) - m
F["self_share"] = (d.rim_self + d.mid_self + d.three_self) / (d.rim_fga + d.mid_fga + d.three_fga).clip(lower=1)
F.to_csv("pt_features.csv", index=False); print(F.shape); print(F.describe().T[["mean", "std"]].round(2).to_string())
