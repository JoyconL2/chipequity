"""Add play-type features to the box-prior inputs (mymodel/features_rs.csv -> features_rs_pt.csv).
Same convention as the existing features: per 100 possessions on the floor, minus that season's league average."""
import json, numpy as np, pandas as pd
F = pd.read_csv("../mymodel/features_rs.csv")
D = json.load(open("../site/data.json")); S = D["seasons"]; ids = [int(x) for x in D["ids"]]
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "pos")}); P = P[P.t == 0]
POS = {(ids[k], S[s]): v for k, s, v in zip(P.p, P.s, P.pos)}
d = pd.read_csv("playtypes.csv").fillna(0); d["pos"] = [POS.get((int(p), s), np.nan) for p, s in zip(d.p, d.season)]
d = d[d.pos > 0].copy(); lg = d.groupby("season").sum(numeric_only=True)
for z in ("rim", "mid", "three"):
    lgua = (lg[f"{z}_ua"] / lg[f"{z}_fgm"]).to_dict(); ua = (d[f"{z}_ua"] + 8 * d.season.map(lgua)) / (d[f"{z}_fgm"] + 8)
    d[f"{z}_self"] = d[f"{z}_fga"] * ua; d[f"{z}_set"] = d[f"{z}_fga"] * (1 - ua)
G = pd.DataFrame({"EntityId": d.p.astype(int), "Season": d.season})
rates = {"o_pt_trans": "transition_fga", "o_pt_putback": "putback_fga", "o_pt_rim_self": "rim_self", "o_pt_rim_set": "rim_set",
         "o_pt_mid_self": "mid_self", "o_pt_mid_set": "mid_set", "o_pt_three_self": "three_self", "o_pt_three_set": "three_set",
         "o_pt_ast_mid": "ast_mid", "o_pt_ast_trans": "ast_transition"}
for name, col in rates.items():
    r = 100 * d[col] / d.pos; m = (d[col].groupby(d.season).sum() / d.pos.groupby(d.season).sum() * 100); G[name] = (r - d.season.map(m)).values
for c in ("transition", "rim", "mid", "three"):          # points added by play type: (pps - league pps) x shots, per 100
    lp = (lg[f"{c}_pts"] / lg[f"{c}_fga"]).to_dict(); G[f"o_pt_{c}_add"] = (100 * (d[f"{c}_pts"] - d[f"{c}_fga"] * d.season.map(lp)) / d.pos).values
out = F.merge(G, on=["EntityId", "Season"], how="left")
for c in G.columns[2:]: out[c] = out[c].fillna(0)
cols = [c for c in F.columns] ; extra = [c for c in G.columns[2:]]
out = out[cols[:cols.index("mpg")] + extra + cols[cols.index("mpg"):]]
out.to_csv("../mymodel/features_rs_pt.csv", index=False); print(out.shape, "matched", int((out.o_pt_trans != 0).sum()), "of", len(out))
