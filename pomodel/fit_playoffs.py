"""Fit + test the playoff series model. Every number is leave-one-season-out: a season's series are predicted
with weights fit only on the OTHER seasons.

Per-game margin for team A = sum_k  w_k * (feature_k(A) - feature_k(B)) * possessions/100  (+/- home court 2.5)
Game win chance = Phi(margin / 12); series chance from the 2-2-1-1-1 home pattern (best-of-5 first rounds before 2003).

Input: series2.json (node export_series.js). Prints accuracy / log loss and the weights to put in site/model.js PARAMS:
  net -> wNet, t3 -> wTop, avail -> wAv, luck -> wLuck."""
import json
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm

X = None   # loaded in __main__ (series2.json from export_series.js)


def series_pv(m, home, need, hca=2.5, sigma=12.0):
    m = np.asarray(m, float); n = len(m)
    sgn = np.where(home == "A", 1.0, np.where(home == "B", -1.0, 0.0))
    out = np.zeros(n)
    for nd in (3, 4):
        k = need == nd
        if not k.any(): continue
        pat = np.array([1, 1, 0, 0, 1, 0, 1] if nd == 4 else [1, 1, 0, 0, 1])
        p = norm.cdf((m[k][:, None] + np.where(pat[None, :] == 1, hca, -hca) * sgn[k][:, None]) / sigma)
        dp = {(0, 0): np.ones(k.sum())}
        for _ in range(2 * nd - 1):
            new = {}
            for (a, b), v in dp.items():
                if a == nd or b == nd: new[(a, b)] = new.get((a, b), 0) + v; continue
                new[(a + 1, b)] = new.get((a + 1, b), 0) + v * p[:, a + b]
                new[(a, b + 1)] = new.get((a, b + 1), 0) + v * (1 - p[:, a + b])
            dp = new
        out[k] = sum(v for (a, b), v in dp.items() if a == nd)
    return out


def design(Xs, cols):
    D = np.column_stack([Xs[f"{c}A"].values - Xs[f"{c}B"].values for c in cols])
    return np.nan_to_num(D) * ((Xs.paceA + Xs.paceB).values / 200)[:, None]


def evaluate(cols, label, Xs=None):
    Xs = X if Xs is None else Xs
    D = design(Xs, cols)
    nll = lambda b, idx: -np.sum(np.log(np.clip(series_pv(D[idx] @ b, Xs.home.values[idx], Xs.need.values[idx]), 1e-9, 1)))
    probs = np.zeros(len(Xs))
    for s in Xs.s.unique():                          # the series winner is always team A
        tr = np.where(Xs.s.values != s)[0]; te = np.where(Xs.s.values == s)[0]
        b = minimize(nll, np.full(len(cols), 0.5), args=(tr,), method="Nelder-Mead", options={"maxiter": 2000, "xatol": 1e-3}).x
        probs[te] = series_pv(D[te] @ b, Xs.home.values[te], Xs.need.values[te])
    full = minimize(nll, np.full(len(cols), 0.5), args=(np.arange(len(Xs)),), method="Nelder-Mead", options={"maxiter": 2000}).x
    print(f"{label:46s} acc {np.mean(probs > 0.5):.1%}  logloss {-np.mean(np.log(np.clip(probs, 1e-9, 1))):.4f}  weights {np.round(full, 2)}")


if __name__ == "__main__":
    X = pd.DataFrame(json.load(open("series2.json")))
    print(f"{len(X)} series, {X.s.min()} to {X.s.max()}")
    evaluate(["net"], "net rating only")
    evaluate(["net", "t3", "luck"], "net + top-3 CEPM + luck")
    evaluate(["net", "t3", "avail", "luck"], "net + top-3 + available roster + luck (site)")
    evaluate(["net", "t3", "avail", "luck", "exp"], "  + playoff experience")
    evaluate(["net", "t3", "late", "luck"], "net + top-3 + last-15 roster only + luck")
