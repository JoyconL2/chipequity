"""Play-type rows for the site: data.json pt = {cols, rows, lg}. Run after build_playtypes.py and pt_features.py."""
import json, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}; kOf = {int(p): k for k, p in enumerate(D["ids"])}
F = pd.read_csv("playtypes.csv").fillna(0); X = pd.read_csv("pt_features.csv")
F = F.merge(X[["p", "season", "pos", "rim_self75", "mid_self75", "three_self75"]], on=["p", "season"])
lg = F.groupby("season").sum(numeric_only=True); cats = ["transition", "putback", "rim", "mid", "three"]; rows = []
for r in F.itertuples(index=False):
    k = kOf.get(int(r.p)); si = SI.get(r.season)
    if k is None or si is None: continue
    rows.append([k, si, int(r.pos)] + [int(getattr(r, f"{c}_fga")) for c in cats] + [int(getattr(r, f"{c}_pts")) for c in cats]
                + [round(x, 2) for x in (r.rim_self75, r.mid_self75, r.three_self75)] + [int(getattr(r, c)) for c in ("ast_rim", "ast_mid", "ast_three", "ast_transition")])
D["pt"] = {"cols": ["k", "s", "pos"] + [c + "_fga" for c in cats] + [c + "_pts" for c in cats] + ["rim_self75", "mid_self75", "three_self75", "ast_rim", "ast_mid", "ast_three", "ast_transition"],
           "rows": rows, "lg": {str(SI[s]): [int(lg.loc[s, f"{c}_fga"]) for c in cats] + [int(lg.loc[s, f"{c}_pts"]) for c in cats] for s in lg.index if s in SI}}
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False); print(len(rows), "rows")
