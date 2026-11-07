"""Chip Equity v1 for every season on one box-score basis: 1983-84..1995-96 from the game logs (career totals for
1979-83 once available), 1996-97..2025-26 out-of-season (each season estimated by a model trained without it)."""
import json, sys, numpy as np, pandas as pd
sys.argv = ["x"]; import v1_model as V
from sklearn.model_selection import GroupKFold
P, rw, D = V.modern_box(); ids = [int(x) for x in D["ids"]]; S = D["seasons"]
M = V.features(P[P.t == 0]); M["pid"] = [ids[k] for k in M.p]; M["name"] = [D["names"][k] for k in M.p]
F = M.merge(rw[["p", "season", "o", "d", "r"]], on=["p", "season"], suffixes=("", "_real")); F = F[F.season != "1996-97"].reset_index(drop=True)
mk = V.models()["gbm"]
for tgt in ("o", "d"): M[tgt + "_v1"] = np.nan
for tr_i, te_i in GroupKFold(10).split(F, groups=F.season):              # each season predicted by a model without it
    seasons = set(F.season.iloc[te_i])
    for tgt in ("o", "d"):
        m = mk(); m.fit(F.iloc[tr_i][V.X_COLS], F.iloc[tr_i][tgt]); sel = M.season.isin(seasons); M.loc[sel, tgt + "_v1"] = m.predict(M.loc[sel, V.X_COLS])
for tgt in ("o", "d"):                                                    # 1996-97 (not in training): full model
    m = mk(); m.fit(F[V.X_COLS], F[tgt]); sel = M.season == "1996-97"; M.loc[sel, tgt + "_v1"] = m.predict(M.loc[sel, V.X_COLS])
M["r_v1"] = M.o_v1 + M.d_v1
X = pd.read_csv("v1_80.csv"); X = X[X.season < "1996-97"]
A = pd.concat([X.assign(pid=X.p, era="box")[["pid", "name", "season", "on", "mpg", "r", "o", "d", "era"]],
               M.assign(r=M.r_v1, o=M.o_v1, d=M.d_v1, era="pbp")[["pid", "name", "season", "on", "mpg", "r", "o", "d", "era"]]], ignore_index=True)
A = A[A.on >= 1500]; A.to_csv("v1_all.csv", index=False)
print("seasons", A.season.min(), "..", A.season.max(), "| player-seasons", len(A))
print("\nALL-TIME best single seasons, Chip Equity v1 (box-score basis for everyone):")
print(A.sort_values("r", ascending=False).head(25)[["name", "season", "r", "o", "d"]].round(2).to_string(index=False))
# best 5-year stretch (average of single seasons, 3+ qualifying seasons in the window)
A["y"] = A.season.str[:4].astype(int); best = []
for (pid, nm), g in A.groupby(["pid", "name"]):
    g = g.set_index("y").r
    for y0 in g.index:
        w = g[(g.index >= y0) & (g.index < y0 + 5)]
        if len(w) >= 4: best.append((nm, f"{y0}-{str(y0+5)[-2:]}", w.mean()))
B = pd.DataFrame(best, columns=["name", "stretch", "r"]).sort_values("r", ascending=False).drop_duplicates("name")
print("\nALL-TIME best 5-year stretch (4+ qualifying seasons), v1:"); print(B.head(20).round(2).to_string(index=False))
