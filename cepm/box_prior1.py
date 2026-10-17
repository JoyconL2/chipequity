"""CEPM step A: the box component.

Learns how per-100 box stats map to pure RAPM, then predicts a starting value (the prior) for every player in
every window. The RAPM solve then shrinks toward this prior instead of toward zero.

Doctrine inputs (all per 100 possessions, relative to that season's league average, so eras compare):
  scoring above league efficiency, shot diet (rim / mid / three / FTs), UNASSISTED points (self-creation),
  assists split by the shot they create (rim, three, other), live- vs dead-ball turnovers,
  offensive and defensive rebounds as SEPARATE inputs, fouls drawn, steals, blocks, fouls, charges.
Weights are fit from data (ridge, cross-validated), never set by hand.

Leakage guard: the prior for a window is predicted by a model trained only on RAPM windows that share no
season with it, so the box component never sees the on-court results it is about to be combined with.

usage: python box_prior.py   -> priors.csv (window_end, w, player, prior_o, prior_d) + box_coefs.json
"""
import json
import numpy as np, pandas as pd

F = pd.read_csv("../mymodel/features_rs.csv")
FEATS = [c for c in F.columns if c.startswith(("o_", "d_"))] + ["mpg"]
SEAS = sorted(set(F.Season))
ALL = [f"{y}-{str(y + 1)[-2:]}" for y in range(1996, 2026)]
pos = {s: i for i, s in enumerate(ALL)}

# one row per player-season (traded players: possession-weighted across teams)
F["w"] = F.poss.fillna(0).clip(lower=1e-3)
agg = F.groupby(["EntityId", "Season"]).apply(
    lambda g: pd.Series({**{c: np.average(g[c].fillna(0), weights=g.w) for c in FEATS}, "poss": g.poss.sum()}),
    include_groups=False).reset_index()
ps = {(int(r.EntityId), r.Season): r for r in agg.itertuples()}


def window_feats(players, end, w):
    """possession-weighted average of the box features over the seasons in the window"""
    seas = ALL[max(0, pos[end] - w + 1): pos[end] + 1]
    out = {}
    for p in players:
        rows = [ps.get((int(p), s)) for s in seas]; rows = [r for r in rows if r is not None]
        if not rows or sum(r.poss for r in rows) <= 0: continue
        wt = np.array([r.poss for r in rows])
        out[int(p)] = (np.average([[getattr(r, c) for c in FEATS] for r in rows], axis=0, weights=wt), wt.sum())
    return out


def ridge_fit(X, y, w, lam):
    mu = np.average(X, axis=0, weights=w); sd = np.sqrt(np.average((X - mu) ** 2, axis=0, weights=w)) + 1e-9
    Z = (X - mu) / sd; ym = np.average(y, weights=w); W = w / w.mean()
    b = np.linalg.solve(Z.T @ (Z * W[:, None]) + lam * np.eye(Z.shape[1]), Z.T @ ((y - ym) * W))
    return b / sd, ym - mu @ (b / sd)


# training table: 3-year pure RAPM windows (target) vs window-averaged box stats
R3 = pd.read_csv("../rapm_out/rw3.csv")
rows = []
for end, g in R3.groupby("window_end"):
    if end not in pos: continue
    wf = window_feats(g.player, end, 3)
    for r in g.itertuples():
        if int(r.player) in wf:
            x, bp = wf[int(r.player)]
            if bp >= 0.5 * r.poss:          # box coverage for most of the window (seasons before 2000-01 have no box data)
                rows.append((end, int(r.player), r.o_rapm, r.d_rapm, r.poss, *x))
T = pd.DataFrame(rows, columns=["end", "player", "o", "d", "poss", *FEATS])
T["e"] = T.end.map(pos)
X = T[FEATS].values; W = np.sqrt(T.poss.values)       # sqrt: big-minute players count more, but not overwhelmingly


def fit(mask, lam):
    co, io = ridge_fit(X[mask], T.o.values[mask], W[mask], lam)
    cd, idf = ridge_fit(X[mask], T.d.values[mask], W[mask], lam)
    return co, io, cd, idf


def no_overlap(lo, hi):
    """training windows (each covers e-2..e) that share no season with [lo, hi]"""
    return ((T.e.values < lo) | (T.e.values - 2 > hi))


# choose ridge strength: predict each window from a model that never saw its seasons
best = None
for lam in [30, 100, 300, 1000]:
    err = 0; tot = 0
    for e in sorted(T.e.unique()):
        m = no_overlap(e - 2, e); te = T.e.values == e
        co, io, cd, idf = fit(m, lam)
        po, pd_ = X[te] @ co + io, X[te] @ cd + idf
        err += np.sum(T.poss.values[te] * ((T.o.values[te] - po) ** 2 + (T.d.values[te] - pd_) ** 2)); tot += T.poss.values[te].sum()
    print(f"lambda {lam}: out-of-sample error {err / tot:.3f}")
    if best is None or err / tot < best[1]: best = (lam, err / tot)
LAM = best[0]
var0 = np.average(T.o ** 2 + T.d ** 2, weights=T.poss)
print(f"chosen lambda {LAM}; box component explains {1 - best[1] / var0:.0%} of 3-year RAPM (out of sample)")

# priors for every window the site uses: 2-5 year windows ending each season, plus decades
specs = [(ALL[e], 1, e, e) for e in range(len(ALL))]      # single seasons (1-year CEPM)
players = sorted(set(agg.EntityId.astype(int)))
out = []
for end, w, lo, hi in specs:
    co, io, cd, idf = fit(no_overlap(lo, hi), LAM)
    wf = window_feats(players, end, w)
    for p, (x, bp) in wf.items():
        out.append((end, w, p, round(float(x @ co + io), 3), round(float(x @ cd + idf), 3)))
P = pd.DataFrame(out, columns=["window_end", "w", "player", "prior_o", "prior_d"])
P.to_csv("prior_w1.csv", index=False)
co, io, cd, idf = fit(np.ones(len(T), bool), LAM)
_skip = ({"feats": FEATS, "off": co.tolist(), "def": cd.tolist(), "io": float(io), "id": float(idf), "lambda": LAM})
print("coefficients (per 100 poss, off / def):")
for f, a, b in zip(FEATS, co, cd): print(f"  {f:16s} {a:+.3f} {b:+.3f}")
print("priors:", len(P))
