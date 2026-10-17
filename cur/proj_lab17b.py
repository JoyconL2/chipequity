"""User's priors on purpose + market blend.
Priors: (1) last season's net counts only as much as last season's core (top-8 minute players) is back;
(2) a lead star with quality support pieces gets a bonus on top of what CEPM x minutes already counts."""
import json, numpy as np, pandas as pd
import sys; F = pd.read_pickle(sys.argv[1]); OUT = sys.argv[2]; D = json.load(open("../site/data.json")); tid = D["teamIds"]
F["pc"] = F.prev * F.core8
for c in ("top1", "auxq"): F[c + "_c"] = F[c] - F.groupby("season")[c].transform("mean")
def loso(cols, offset=None):
    y = F.net - (offset if offset is not None else 0); p = pd.Series(np.nan, index=F.index)
    for s in F.season.unique():
        tr, te = F.season != s, F.season == s
        b = np.linalg.lstsq(np.c_[np.ones(tr.sum()), F.loc[tr, cols].values], y[tr].values, rcond=None)[0]
        p[te] = np.c_[np.ones(te.sum()), F.loc[te, cols].values] @ b
    if offset is not None: p = p + offset
    return p - p.groupby(F.season).transform("mean")
slope = float(np.polyfit(F.net, F.wpct - 0.5, 1)[0])
def wins(p, k=1.3): return 82 * np.clip(0.5 + slope * k * p, 0.03, 0.97)
L = pd.read_csv("market/win_totals.csv"); fix = {1610612766: 1610612740, 1610612740: 1610612766}
have = set(zip(F.season, F.tid))
L["tid"] = [tid[D["abbrs"].index(ab)] for ab in L.abbr]; L["tid"] = [t if (s, t) in have else fix.get(t, t) for s, t in zip(L.season, L.tid)]
L["k_pct"] = L.line / L.games; L["k_pct"] = L.k_pct - L.groupby("season").k_pct.transform("mean") + 0.5
F = F.merge(L[["season", "tid", "k_pct"]], on=["season", "tid"], how="left")
W = 82 * F.wpct; mk = F.k_pct.notna()
def report(label, p):
    w = wins(p); e = (w - W).abs(); sd = w.groupby(F.season).std().mean()
    out = {"model": label, "net_rmse": round(float(np.sqrt(((F.net - p) ** 2).mean())), 3), "wins_mae": round(float(e.mean()), 2), "wins_mae_market_seasons": round(float(e[mk].mean()), 2), "spread_sd_wins": round(float(sd), 1)}
    print(json.dumps(out)); return w
w_cur = report("current: standings-first", loso(["prev", "dX", "U", "X"]))
w_pc = report("prior 1: standings x core continuity", loso(["pc", "dX", "U", "X"]))
res = {}
for b1, b2 in ((0.3, 0.15), (0.5, 0.25), (0.8, 0.4)):
    off = b1 * F.top1_c + b2 * F.auxq_c
    res[(b1, b2)] = report(f"priors 1+2: star bonus {b1}/CEPM pt, support {b2}", loso(["pc", "dX", "U", "X"], off))
# market blend: wins = w x model + (1 - w) x market, on seasons with lines
mkw = 82 * F.k_pct
print("market alone, market seasons: wins MAE", round(float((mkw - W)[mk].abs().mean()), 2))
for key, wm in (("current", w_cur), ("priors 0.5/0.25", res[(0.5, 0.25)])):
    for w in (0.3, 0.5, 0.7):
        bl = w * wm + (1 - w) * mkw; print(f"blend {key} x{w} + market: wins MAE {float((bl - W)[mk].abs().mean()):.2f}")

print("--- priors 0.3/0.15 blended")
for w in (0.3, 0.4, 0.5):
    bl = w * res[(0.3, 0.15)] + (1 - w) * mkw; print(f"x{w}: wins MAE {float((bl - W)[mk].abs().mean()):.2f}  spread {float(bl[mk].groupby(F.season[mk]).std().mean()):.1f}")
print("actual spread", float(W.groupby(F.season).std().mean()))
off = 0.3 * F.top1_c + 0.15 * F.auxq_c; cols = ["pc", "dX", "U", "X"]
b = np.linalg.lstsq(np.c_[np.ones(len(F)), F[cols].values], (F.net - off).values, rcond=None)[0]
json.dump({"a": float(b[0]), **{c: float(v) for c, v in zip(cols, b[1:])}, "b_top1": 0.3, "b_auxq": 0.15, "slope": slope}, open(OUT, "w"), indent=1); print(open(OUT).read())
