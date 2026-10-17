"""Factor CEPM: each player's effect on the four factors at both ends, adjusted for teammates and opponents
(ridge regression on every stint, like CEPM), then turned into points per 100 possessions.
  offense: eFG% (shooting), TOV% (turnovers), OREB% (offensive rebounds), FT rate (trips per shot)
  defense: the same four for the opponent (opponent eFG = defensive shooting, forced turnovers, defensive
           rebounding = opponent OREB%, fouls = opponent FT rate)
Points per factor come from a regression of team offensive rating on the four factors (season fixed effects)."""
import sys, json, numpy as np, pandas as pd, scipy.sparse as sp
from scipy.sparse.linalg import spsolve
SEASONS = [f"{y}-{str(y + 1)[-2:]}" for y in range(2000, 2025)]
FS = {s: pd.read_csv(f"fstints_{s}.csv") for s in SEASONS}
# stint points (from the stints files) for the points regression
for s in SEASONS:
    st = pd.read_csv(f"../stints/stints_{s}_rs.csv", dtype={"game_id": str}); st["sid"] = np.arange(len(st))
    f = FS[s].merge(st[["sid", "home_pts", "away_pts", "home_team", "away_team"]].rename(columns={"home_team": "hteam", "away_team": "ateam"}), on="sid")
    f["team"] = np.where(f.side == "home", f.hteam, f.ateam); f["pts"] = np.where(f.side == "home", f.home_pts, f.away_pts)
    FS[s] = f
FACT = {"efg": (lambda f: (f.FGM + 0.5 * f.FG3M) / f.FGA.clip(lower=1), lambda f: f.FGA),
        "tov": (lambda f: f.TOV / f.P.clip(lower=1), lambda f: f.P),
        "orb": (lambda f: f.OREB / f.MISS.clip(lower=1), lambda f: f.MISS),
        "ftr": (lambda f: f.FTT / f.FGA.clip(lower=1), lambda f: f.FGA)}
# ---- points per unit of each factor: team-season offense, season fixed effects ----
rows = []
for s in SEASONS:
    g = FS[s].groupby("team")[["P", "FGA", "FGM", "FG3M", "MISS", "OREB", "TOV", "FTT", "pts"]].sum()
    g["efg"] = (g.FGM + 0.5 * g.FG3M) / g.FGA; g["tov"] = g.TOV / g.P; g["orb"] = g.OREB / g.MISS; g["ftr"] = g.FTT / g.FGA; g["ortg"] = 100 * g.pts / g.P; g["s"] = s
    rows.append(g)
TT = pd.concat(rows); X = TT[["efg", "tov", "orb", "ftr"]]; X = X - X.groupby(TT.s).transform("mean"); y = TT.ortg - TT.groupby("s").ortg.transform("mean")
B = np.linalg.lstsq(X.values, y.values, rcond=None)[0]; BW = dict(zip(["efg", "tov", "orb", "ftr"], B))
r2 = 1 - ((y - X.values @ B) ** 2).sum() / (y ** 2).sum()
print("points per 100 per unit factor:", {k: round(v, 1) for k, v in BW.items()}, "| R^2", round(r2, 3), flush=True)
def design(f):
    off = np.where(f.side == "home", f.home_players, f.away_players); de = np.where(f.side == "home", f.away_players, f.home_players)
    return [list(map(int, str(o).split("-"))) for o in off], [list(map(int, str(d).split("-"))) for d in de]
def fit(seasons, lam):
    f = pd.concat([FS[s] for s in seasons], ignore_index=True); f = f[f.P > 0]
    O, Dd = design(f); players = sorted({p for l in O for p in l} | {p for l in Dd for p in l}); ix = {p: i for i, p in enumerate(players)}; n = len(players)
    r, c = [], []
    for i, (o, d) in enumerate(zip(O, Dd)):
        for p in o: r.append(i); c.append(ix[p])
        for p in d: r.append(i); c.append(n + ix[p])
    Xs = sp.csr_matrix((np.ones(len(r)), (r, c)), shape=(len(f), 2 * n))
    out = {"player": players}
    for k, (yf, wf) in FACT.items():
        yv = yf(f).values; w = wf(f).values.astype(float); mu = np.average(yv, weights=np.maximum(w, 1e-9))
        W = sp.diags(w); A = (Xs.T @ W @ Xs) + lam[k] * sp.identity(2 * n); b = Xs.T @ (w * (yv - mu))
        beta = spsolve(A.tocsc(), b); out[f"o_{k}"] = beta[:n]; out[f"d_{k}"] = beta[n:]
    # exposure (offensive possessions on the floor) per player
    poss = np.zeros(n)
    for o, pp in zip(O, f.P.values):
        for p in o: poss[ix[p]] += pp
    out["poss"] = poss
    R = pd.DataFrame(out)
    R["f_off"] = sum(BW[k] * R[f"o_{k}"] for k in FACT); R["f_def"] = -sum(BW[k] * R[f"d_{k}"] for k in FACT)
    R["fcepm"] = R.f_off + R.f_def
    return R
if __name__ == "__main__":
    # choose ridge strength per factor: hold out every 5th game of 2015-16 to 2017-18, pick lambda with best weighted error
    lam_grid = [500, 1000, 2000, 4000, 8000, 16000, 32000]
    f = pd.concat([FS[s] for s in ("2015-16", "2016-17", "2017-18")], ignore_index=True); f = f[f.P > 0]
    gid = f.game_id.astype(str).str[-4:].astype(int); te = (gid % 5 == 0).values
    O, Dd = design(f); players = sorted({p for l in O for p in l} | {p for l in Dd for p in l}); ix = {p: i for i, p in enumerate(players)}; n = len(players)
    r, c = [], []
    for i, (o, d) in enumerate(zip(O, Dd)):
        for p in o: r.append(i); c.append(ix[p])
        for p in d: r.append(i); c.append(n + ix[p])
    Xs = sp.csr_matrix((np.ones(len(r)), (r, c)), shape=(len(f), 2 * n)); LAM = {}
    for k, (yf, wf) in FACT.items():
        yv = yf(f).values; w = wf(f).values.astype(float); mu = np.average(yv[~te], weights=np.maximum(w[~te], 1e-9)); errs = []
        Xt = Xs[~te]; W = sp.diags(w[~te]); XtWX = Xt.T @ W @ Xt; b = Xt.T @ (w[~te] * (yv[~te] - mu))
        for lam in lam_grid:
            beta = spsolve((XtWX + lam * sp.identity(2 * n)).tocsc(), b); pr = mu + Xs[te] @ beta
            errs.append(np.average((yv[te] - pr) ** 2, weights=np.maximum(w[te], 1e-9)))
        LAM[k] = lam_grid[int(np.argmin(errs))]; print("lambda", k, LAM[k], [round(e, 5) for e in errs], flush=True)
    json.dump({"lambda": LAM, "points": BW, "r2": r2}, open("factor_params.json", "w"), indent=1)
    allr = []
    for w in (1, 3):
        for i, s in enumerate(SEASONS):
            if i + 1 < w: continue
            R = fit(SEASONS[i - w + 1:i + 1], LAM); R["window_end"] = s; R["w"] = w; allr.append(R)
            print(w, s, len(R), flush=True)
    pd.concat(allr).to_csv("factor_cepm.csv", index=False)
