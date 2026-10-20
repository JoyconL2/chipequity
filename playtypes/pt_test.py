"""Do play types predict a player's NEXT-season impact beyond what the model already knows?
Target: next season's single-season regression (total, and offense). Baseline inputs: this season's single-season and
3-year regression and box-score prior. Test adds the play-type features. Leave-one-season-out, weighted by next-season
possessions."""
import numpy as np, pandas as pd
from sklearn.linear_model import RidgeCV
F = pd.read_csv("pt_features.csv")
d1 = pd.read_csv("../cepm/disp1.csv"); d3 = pd.read_csv("../cepm/disp3.csv"); pr = pd.read_csv("../cepm/prior_w1.csv")
S = sorted(set(d1.window_end)); nxt = {S[i]: S[i + 1] for i in range(len(S) - 1)}
A = d1.rename(columns={"player": "p", "window_end": "season", "rapm": "r1", "o_rapm": "o1", "d_rapm": "dd1", "poss": "poss1"})[["p", "season", "r1", "o1", "dd1", "poss1"]]
B = d3.rename(columns={"player": "p", "window_end": "season", "rapm": "r3", "o_rapm": "o3"})[["p", "season", "r3", "o3"]]
Pr = pr.rename(columns={"player": "p", "window_end": "season"}); Pr["prior"] = Pr.prior_o + Pr.prior_d; Pr = Pr[["p", "season", "prior", "prior_o"]]
X = F.merge(A, on=["p", "season"]).merge(B, on=["p", "season"], how="left").merge(Pr, on=["p", "season"], how="left")
X["r3"] = X.r3.fillna(X.r1); X["o3"] = X.o3.fillna(X.o1); X = X.fillna({"prior": 0, "prior_o": 0})
T = A.copy(); T["season"] = T.season.map({v: k for k, v in nxt.items()}); T = T.dropna(subset=["season"]).rename(columns={"r1": "y", "o1": "yo", "poss1": "wn"})[["p", "season", "y", "yo", "wn"]]
X = X.merge(T, on=["p", "season"]); X = X[(X.wn >= 1500) & (X.poss1 >= 1000)].reset_index(drop=True)
base = ["r1", "r3", "prior"]; baseo = ["o1", "o3", "prior_o"]
pt = [c for c in F.columns if c.endswith("75") or c.endswith("_pps") or c == "self_share"]
def loso(cols, yname):
    pred = np.zeros(len(X))
    for s in X.season.unique():
        tr, te = X.season != s, X.season == s
        mu, sd = X.loc[tr, cols].mean(), X.loc[tr, cols].std().replace(0, 1)
        m = RidgeCV(alphas=np.logspace(-2, 3, 12)).fit((X.loc[tr, cols] - mu) / sd, X.loc[tr, yname], sample_weight=X.loc[tr, "wn"])
        pred[te.values] = m.predict((X.loc[te, cols] - mu) / sd)
    w = X.wn; e = X[yname] - pred; return float(np.sqrt((w * e * e).sum() / w.sum())), float(np.corrcoef(pred, X[yname])[0, 1])
print(len(X), "player-seasons")
for lab, cols, y in (("total, baseline", base, "y"), ("total, + play types", base + pt, "y"), ("offense, baseline", baseo, "yo"), ("offense, + play types", baseo + pt, "yo")):
    r, c = loso(cols, y); print(f"{lab:24s} RMSE {r:.3f}  r {c:.3f}")
# which features matter (full fit, standardized)
mu, sd = X[base + pt].mean(), X[base + pt].std()
m = RidgeCV(alphas=np.logspace(-2, 3, 12)).fit((X[base + pt] - mu) / sd, X.y, sample_weight=X.wn)
print(pd.Series(m.coef_, index=base + pt).round(3).sort_values().to_string())
