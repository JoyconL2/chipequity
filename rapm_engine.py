"""
RAPM - STEPS 3 & 4: ridge regression on stints, with your doctrine built in.

Input: stint files from the parser (one row per stretch where the same 10 players are on the floor):
  game_id, season, game_date, period, start_sec, end_sec   (seconds left in the period, start > end)
  home_team, away_team, home_players, away_players          (players as "id-id-id-id-id")
  home_poss, away_poss, home_pts, away_pts                  (offensive possessions and points by side)
  start_margin                                              (home score minus away score when the stint began)

What it does
  Step 3  Ridge regression. Each stint is a row: +1 for the 5 home players, -1 for the 5 away players,
          0 for everyone else. Target = home margin per 100 possessions, weighted by possessions.
          Also an offense/defense split version (two rows per stint, one per side).
  Step 4  Cleaning and controls:
          - Garbage time removed (Cleaning-the-Glass style: big 4th-quarter leads + mostly bench on the floor).
          - Fatigue markers: how long each five has been on the floor without rest, minutes already played
            in the game, and back-to-back nights.
          - Situational controls: home court, score state (teams ahead ease off), clutch time.
          - Multicollinearity: ridge penalty picked by cross-validation on held-out games, multi-season
            windows with time decay, and very-low-minute players pooled into one "replacement" column.
  Doctrine
          - Era: results are standardized to each season's scoring level, not just pace (points per 100
            are rescaled by league efficiency, so +5 in a 100-ORtg league counts more than +5 in 117).
          - No hand-tuned "subjective" model: every weight is fit from data with cross-validation.
          - Box prior (optional, --prior): a stats model trained on THIS RAPM, using assisted-FG share,
            assist credit by assist points and shot zone, and offensive vs defensive rebounds as separate
            inputs. RAPM is then shrunk toward that prior instead of toward zero.

Usage
  python rapm_engine.py stints/*.csv --window 3 --out rapm_results.csv [--prior features_rs.csv]
"""
import argparse, glob, sys
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

# ---------------- loading + step 4 cleaning ----------------
def load(paths):
    df = pd.concat([pd.read_csv(p, dtype={"game_id": str}) for p in paths], ignore_index=True)
    df = df[(df.home_poss + df.away_poss) > 0].copy()
    df["poss"] = (df.home_poss + df.away_poss) / 2
    df["secs"] = (df.start_sec - df.end_sec).clip(lower=0)
    return df

def mark_starters_and_fatigue(df):
    """Per game: who started, each player's continuous time on court and game minutes at each stint."""
    df = df.sort_values(["game_id", "period", "start_sec"], ascending=[True, True, False]).reset_index(drop=True)
    n = len(df)
    cont_h = np.zeros(n); cont_a = np.zeros(n); load_h = np.zeros(n); load_a = np.zeros(n); starters_on = np.zeros(n)
    for gid, g in df.groupby("game_id", sort=False):
        first = g.iloc[0]
        starters = set(first.home_players.split("-")) | set(first.away_players.split("-"))
        on_since, played = {}, {}
        t_elapsed = 0.0
        prev_period = None
        for idx, r in g.iterrows():
            if r.period != prev_period:
                # period start: elapsed game seconds before this period
                t_elapsed = (r.period - 1) * 720 if r.period <= 4 else 2880 + (r.period - 5) * 300
                prev_period = r.period
                on_since = {}                      # quarter breaks count as rest
            plen = 720 if r.period <= 4 else 300
            now = t_elapsed + (plen - r.start_sec)
            hp, ap = r.home_players.split("-"), r.away_players.split("-")
            for pl in hp + ap:
                on_since.setdefault(pl, now)
            for pl in list(on_since):
                if pl not in hp and pl not in ap: on_since.pop(pl)
            cont_h[idx] = np.mean([(now - on_since[p]) / 60 for p in hp]); cont_a[idx] = np.mean([(now - on_since[p]) / 60 for p in ap])
            load_h[idx] = np.mean([played.get(p, 0) / 60 for p in hp]); load_a[idx] = np.mean([played.get(p, 0) / 60 for p in ap])
            starters_on[idx] = sum(p in starters for p in hp + ap)
            for p in hp + ap: played[p] = played.get(p, 0) + r.secs
    df["fat_cont"] = cont_h - cont_a          # minutes since last rest: home five minus away five
    df["fat_load"] = load_h - load_a          # minutes already played this game
    df["starters_on"] = starters_on
    return df

def back_to_back(df):
    g = df.drop_duplicates("game_id")[["game_id", "game_date", "home_team", "away_team"]].copy()
    g["game_date"] = pd.to_datetime(g.game_date, errors="coerce")
    long = pd.concat([g[["game_id", "game_date"]].assign(team=g.home_team), g[["game_id", "game_date"]].assign(team=g.away_team)])
    long = long.sort_values(["team", "game_date"])
    long["b2b"] = (long.groupby("team").game_date.diff().dt.days == 1).astype(int)
    b = long.set_index(["game_id", "team"]).b2b
    df["b2b"] = [b.get((gid, h), 0) - b.get((gid, a), 0) for gid, h, a in zip(df.game_id, df.home_team, df.away_team)]
    return df

def garbage_time(df):
    """Cleaning-the-Glass style: 4th quarter, big lead for the time left, and 2 or fewer starters on the floor."""
    m = df.start_margin.abs(); t = df.start_sec
    big = ((t <= 720) & (t > 540) & (m >= 25)) | ((t <= 540) & (t > 360) & (m >= 20)) | ((t <= 360) & (m >= 10))
    return (df.period == 4) & big & (df.starters_on <= 2)

def era_scale(df):
    """Doctrine: standardize to each season's scoring level (not just pace)."""
    lg = df.groupby("season").apply(lambda x: (x.home_pts.sum() + x.away_pts.sum()) / (x.home_poss.sum() + x.away_poss.sum()) * 100, include_groups=False)
    ref = lg.mean()
    return df.season.map(ref / lg), lg

# ---------------- step 3: design matrices ----------------
def player_index(df, min_poss):
    on = {}
    for col in ["home_players", "away_players"]:
        for pls, ps in zip(df[col], df.poss):
            for p in pls.split("-"): on[p] = on.get(p, 0) + ps
    keep = sorted(p for p, v in on.items() if v >= min_poss)
    idx = {p: i for i, p in enumerate(keep)}
    return idx, on

COVS = ["home", "fat_cont", "fat_load", "b2b", "margin_state", "clutch"]
COV_PEN = {"home": 1.0, "fat_cont": 300.0, "fat_load": 300.0, "b2b": 300.0, "margin_state": 300.0, "clutch": 300.0}

def covariates(df):
    C = pd.DataFrame({"home": 1.0, "fat_cont": df.fat_cont, "fat_load": df.fat_load / 10, "b2b": df.b2b,
                      "margin_state": df.start_margin.clip(-20, 20) / 10,
                      "clutch": ((df.period >= 4) & (df.start_sec <= 300) & (df.start_margin.abs() <= 5)).astype(float)})
    return C[COVS].values

def design_net(df, idx):
    """User's spec: +1 home on court, -1 away on court, 0 bench. Replacement column pools low-minute players."""
    rows, cols, vals = [], [], []
    R = len(idx)                                           # replacement column index
    for r, (hp, ap) in enumerate(zip(df.home_players, df.away_players)):
        for p in hp.split("-"): rows.append(r); cols.append(idx.get(p, R)); vals.append(1.0)
        for p in ap.split("-"): rows.append(r); cols.append(idx.get(p, R)); vals.append(-1.0)
    X = sp.csr_matrix((vals, (rows, cols)), shape=(len(df), R + 1))
    return sp.hstack([X, sp.csr_matrix(covariates(df))]).tocsr()

def design_od(df, idx):
    """Offense/defense split: one row per side. Columns [offense(N+1) | defense(N+1) | covariates]."""
    N = len(idx) + 1; R = N - 1
    rows, cols, vals, y, w = [], [], [], [], []
    C = covariates(df); covs = []
    lg_mean = (df.home_pts.sum() + df.away_pts.sum()) / (df.home_poss.sum() + df.away_poss.sum()) * 100
    r = 0
    for k, s in enumerate(df.itertuples()):
        for off, dfn, pts, ps, sign in [(s.home_players, s.away_players, s.home_pts, s.home_poss, 1), (s.away_players, s.home_players, s.away_pts, s.away_poss, -1)]:
            if ps <= 0: continue
            for p in off.split("-"): rows.append(r); cols.append(idx.get(p, R)); vals.append(1.0)
            for p in dfn.split("-"): rows.append(r); cols.append(N + idx.get(p, R)); vals.append(-1.0)   # good defense lowers opponent points
            y.append(pts / ps * 100 * s.era - lg_mean); w.append(ps * s.decay); covs.append(np.r_[C[k] * sign, 1.0]); r += 1
    X = sp.csr_matrix((vals, (rows, cols)), shape=(r, 2 * N))
    X = sp.hstack([X, sp.csr_matrix(np.array(covs))]).tocsr()      # last column = intercept
    return X, np.array(y), np.array(w)

def ridge(X, y, w, lam, n_players, lam_cov=1.0, prior=None):
    """Weighted ridge with optional prior: minimize sum w (y - Xb)^2 + lam |b - b0|^2 (players), lam_cov |c|^2 (covariates)."""
    p = X.shape[1]
    pen = np.full(p, lam_cov); pen[:n_players] = lam
    for j, c in enumerate(COVS):
        if n_players + j < p: pen[n_players + j] = COV_PEN[c]
    if p > n_players + len(COVS): pen[n_players + len(COVS):] = 1e-6       # intercept: unpenalized
    b0 = np.zeros(p) if prior is None else prior
    W = sp.diags(w / w.mean())
    A = (X.T @ W @ X) + sp.diags(pen)
    rhs = X.T @ (W @ (y - X @ b0))
    sol = spla.spsolve(A.tocsc(), rhs)
    return b0 + sol

def cv_lambda(df, build, grid, n_players_fn, folds=5, seed=0, prior=None):
    """Pick the ridge penalty by predicting held-out GAMES (not random rows)."""
    games = np.array(df.game_id.unique(), dtype=object); rng = np.random.default_rng(seed); rng.shuffle(games)
    fold = {g: i % folds for i, g in enumerate(games)}
    f = df.game_id.map(fold).values
    scores = {}
    for lam in grid:
        err = 0.0; tot = 0.0
        for k in range(folds):
            tr, te = df[f != k], df[f == k]
            Xtr, ytr, wtr, ntr, Xte, yte, wte = build(tr, te)
            b = ridge(Xtr, ytr, wtr, lam, ntr, prior=prior)
            pred = Xte @ b
            err += np.sum(wte * (yte - pred) ** 2); tot += wte.sum()
        scores[lam] = err / tot
    best = min(scores, key=scores.get)
    return best, scores

# ---------------- run ----------------
def run(df, window_end, window, decay, min_poss, lam_grid, od=True, prior_df=None, fixed_lam=None):
    seasons = sorted(df.season.unique())
    if window_end not in seasons: return None
    i = seasons.index(window_end); use = seasons[max(0, i - window + 1): i + 1]
    d = df[df.season.isin(use)].copy()
    d["decay"] = d.season.map({s: decay ** (len(use) - 1 - j) for j, s in enumerate(use)})
    idx, onposs = player_index(d, min_poss)
    if len(idx) == 0: return None          # early in a season nobody has min_poss yet
    N = len(idx) + 1
    # ---- net model (user's spec) for lambda selection ----
    def build_net(tr, te):
        Xtr = design_net(tr, idx); Xte = design_net(te, idx)
        y = lambda x: (x.home_pts - x.away_pts) / x.poss * 100 * x.era
        return Xtr, y(tr).values, (tr.poss * tr.decay).values, N, Xte, y(te).values, (te.poss * te.decay).values
    prior_net = None; prior_od = None
    if prior_df is not None:
        pdf = prior_df[prior_df.window_end == window_end] if "window_end" in prior_df else prior_df
        pv = pdf.set_index("player").reindex([int(p) for p in idx]).fillna(0)
        prior_net = np.r_[pv.prior_o.values + pv.prior_d.values, -2.0, np.zeros(len(COVS))]
        prior_od = np.r_[pv.prior_o.values, -1.0, pv.prior_d.values, -1.0, np.zeros(len(COVS) + 1)]
    lam, scores = (fixed_lam, {}) if fixed_lam else cv_lambda(d, build_net, lam_grid, None, prior=prior_net)
    Xn = design_net(d, idx); yn = ((d.home_pts - d.away_pts) / d.poss * 100 * d.era).values; wn = (d.poss * d.decay).values
    bn = ridge(Xn, yn, wn, lam, N, prior=prior_net)
    out = pd.DataFrame({"player": list(idx), "rapm": bn[:N - 1]})
    if od:
        Xo, yo, wo = design_od(d, idx)
        bo = ridge(Xo, yo, wo, lam, 2 * N, prior=prior_od)
        out["o_rapm"] = bo[:N - 1]; out["d_rapm"] = bo[N:2 * N - 1]
    out["poss"] = out.player.map(onposs)
    out["window_end"] = window_end; out["seasons"] = f"{use[0]}..{use[-1]}"; out["lambda"] = lam
    covs = dict(zip(COVS, bn[N:]))
    return out.sort_values("rapm", ascending=False), covs, scores

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+"); ap.add_argument("--window", type=int, default=3); ap.add_argument("--decay", type=float, default=0.5)
    ap.add_argument("--min-poss", type=int, default=1000); ap.add_argument("--out", default="rapm_results.csv")
    ap.add_argument("--keep-garbage", action="store_true"); ap.add_argument("--only-end", default=None); ap.add_argument("--cache", default=None); ap.add_argument("--seasons", default=None); ap.add_argument("--prior", default=None); ap.add_argument("--lambda-from", default=None); ap.add_argument("--lam", type=float, default=None)
    a = ap.parse_args()
    files = [f for pat in a.files for f in glob.glob(pat)]
    import os
    if a.cache and os.path.exists(a.cache):
        df = pd.read_pickle(a.cache)
    else:
        df = load(files); df = mark_starters_and_fatigue(df); df = back_to_back(df)
        if a.cache: df.to_pickle(a.cache)
    if a.seasons: lo, hi = a.seasons.split(".."); df = df[(df.season >= lo) & (df.season <= hi)].copy()
    gt = garbage_time(df); print(f"stints {len(df):,}; garbage time removed: {gt.mean():.1%} of stints, {df.poss[gt].sum()/df.poss.sum():.1%} of possessions")
    if not a.keep_garbage: df = df[~gt].copy()
    df["era"], lg = era_scale(df); print("league ORtg by season:", lg.round(1).to_dict())
    prior = pd.read_csv(a.prior) if a.prior else None
    res = []
    for s in sorted(df.season.unique()):
        if a.only_end and s != a.only_end: continue
        if s < sorted(df.season.unique())[min(a.window, df.season.nunique()) - 1] and not a.only_end: continue   # skip partial windows at the start
        fl = a.lam
        if a.lambda_from:
            lf = pd.read_csv(a.lambda_from).drop_duplicates("window_end").set_index("window_end")["lambda"]
            fl = float(lf.get(s, lf.median()))
        r = run(df, s, a.window, a.decay, a.min_poss, [250, 500, 1000, 2000, 4000, 8000, 16000], prior_df=prior, fixed_lam=fl)
        if r is None: continue
        out, covs, scores = r; res.append(out)
        print(f"{s}: lambda {out['lambda'].iloc[0]}, controls {({k: round(v, 2) for k, v in covs.items()})}")
    (pd.concat(res) if res else pd.DataFrame(columns=["player", "rapm", "o_rapm", "d_rapm", "poss", "window_end", "seasons", "lambda"])).to_csv(a.out, index=False); print("saved", a.out)

if __name__ == "__main__":
    main()
