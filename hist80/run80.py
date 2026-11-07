"""Fit Chip Equity v1 on 1997-98..2025-26 (calibrated on out-of-fold predictions), check it on 1996-97 built from the
1980s-style game logs, and estimate 1979-80..1995-96. Writes hist80/v1_80.csv."""
import json, sys, numpy as np, pandas as pd
sys.argv = ["x"]; import v1_model as V
from sklearn.model_selection import GroupKFold, cross_val_predict
P, rw, D = V.modern_box()
F = V.features(P[P.t == 0]).merge(rw[["p", "season", "o", "d", "r"]], on=["p", "season"]); F = F[F.season != "1996-97"].reset_index(drop=True)
B = pd.read_csv("box80.csv"); B = B[B.complete]; X = V.features(B[B.t == 0])
ids = [int(x) for x in D["ids"]]; F["pid"] = [ids[k] for k in F.p]; rw = rw.assign(pid=[ids[k] for k in rw.p])
mk = V.models()["gbm"]; cal = {}
for tgt in ("o", "d"):
    cv = cross_val_predict(mk(), F[V.X_COLS], F[tgt], cv=GroupKFold(5), groups=F.season)      # out-of-fold, by season
    b, a = np.polyfit(cv, F[tgt], 1); cal[tgt] = (a, b)
    m = mk(); m.fit(F[V.X_COLS], F[tgt]); X[tgt] = a + b * m.predict(X[V.X_COLS])
    print(f"calibration {tgt}: real = {a:+.3f} + {b:.3f} x estimate")
X["r"] = X.o + X.d
nm80 = {int(k): v for k, v in json.load(open("names80.json")).items()}
X["name"] = [nm80.get(int(p), str(p)) for p in X.p]
X["poss"] = X.on
# check: 1996-97 from game logs vs the real (play-by-play) Chip Equity
# check: 1996-97 inputs built from the game logs vs from the site's own data, same model -> same estimates?
M97 = V.features(P[(P.t == 0) & (P.season == "1996-97")]); M97["pid"] = [ids[k] for k in M97.p]
for tgt in ("o", "d"):
    m = mk(); m.fit(F[V.X_COLS], F[tgt]); a, b = cal[tgt]; M97[tgt] = a + b * m.predict(M97[V.X_COLS])
M97["r"] = M97.o + M97.d
chk = X[X.season == "1996-97"].merge(M97[["pid", "r", "on"]], left_on="p", right_on="pid", suffixes=("", "_site"))
chk = chk[chk.on_site >= 1500]
print(f"1996-97 consistency (game-log inputs vs site inputs): n={len(chk)} r={np.corrcoef(chk.r, chk.r_site)[0,1]:.3f} mean diff {np.mean(chk.r - chk.r_site):+.2f}")
X.to_csv("v1_80.csv", index=False)
q = X[(X.season < "1996-97") & (X.poss >= 1500)]
print("\nbest estimated single seasons 1979-80..1995-96 (1,500+ possessions):")
print(q.sort_values("r", ascending=False).head(25)[["name", "season", "mpg", "r", "o", "d"]].round(2).to_string(index=False))
