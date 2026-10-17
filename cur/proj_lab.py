"""Projected net rating + record: an iterative lab.
Every season 1998-99..2025-26 is predicted using ONLY what was known before it started, and every model's
coefficients are fit leave-one-season-out (the season being predicted is never in the fit).

Opening roster of season s = players who appeared in the team's first 10 regular-season games
(close to an opening-night roster, without hindsight about later trades or call-ups)."""
import json, math, sys
import numpy as np, pandas as pd

SP = ".."
D = json.load(open(f"{SP}/site/data.json"))
S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}
T = D["T"]; tid = D["teamIds"]

# ---------- targets: regular-season net rating, wins, games ----------
team = []
for a, s, t, pts, opp, op, dp, w, l in zip(T["a"], T["s"], T["t"], T["pts"], T["opp"], T["op"], T["dp"], T["w"], T["l"]):
    if t != 0 or w is None: continue
    team.append((S[s], tid[a], 100 * pts / op - 100 * opp / dp, w, l))
TM = pd.DataFrame(team, columns=["season", "tid", "net", "w", "l"])
TM["gp"] = TM.w + TM.l; TM["wpct"] = TM.w / TM.gp

# ---------- per-game minutes ----------
G = pd.read_csv(f"{SP}/pomodel/player_game.csv", dtype={"game_id": str})
G = G[G.stype == "rs"].copy()
G["min"] = G.secs / 60
# team ids in the minutes file vs the team table (Hornets/Pelicans ids swap by era)
def fix_tid(season, t, have):
    if (season, t) in have: return t
    alt = {1610612766: 1610612740, 1610612740: 1610612766}.get(t)
    return alt if (season, alt) in have else t
have = set(zip(TM.season, TM.tid))
G["tid"] = [fix_tid(s, t, have) for s, t in zip(G.season, G.team)]
tg = G.groupby(["season", "tid", "game_id", "date"]).size().reset_index()[["season", "tid", "game_id", "date"]]
tg["n"] = tg.sort_values("date").groupby(["season", "tid"]).cumcount()
G = G.merge(tg[["season", "tid", "game_id", "n"]], on=["season", "tid", "game_id"])
opening = G[G.n < 10].groupby(["season", "tid"]).p.apply(lambda x: sorted(set(x))).to_dict()

# player-season usage (all teams combined)
ps = G.groupby(["p", "season"]).agg(gp=("game_id", "nunique"), mins=("min", "sum")).reset_index()
ps["mpg"] = ps.mins / ps.gp
PS = {(r.p, r.season): (r.mpg, r.gp, r.mins) for r in ps.itertuples()}
first_season = ps.groupby("p").season.min().to_dict()

# ---------- player priors (all from windows ENDING the season before) ----------
def load(f, col="rapm"):
    t = pd.read_csv(f); return {(int(p), w): (r, o, d) for p, w, r, o, d in zip(t.player, t.window_end, t[col], t.o_rapm, t.d_rapm)}
C3RS = load(f"{SP}/cepm/cepm3_rs.csv"); C3 = load(f"{SP}/cepm/disp3.csv"); C2 = load(f"{SP}/cepm/disp2.csv")

def prior_rows(s):
    """one row per (team, player) on the opening roster of season s, with everything known before s"""
    sp = S[SI[s] - 1]; spp = S[SI[s] - 2] if SI[s] >= 2 else None
    out = []
    for (season, t), plist in opening.items():
        if season != s: continue
        for p in plist:
            m1 = PS.get((p, sp)); m2 = PS.get((p, spp)) if spp else None
            exp = SI[sp] - SI[first_season[p]] + 1 if first_season.get(p) and SI[first_season[p]] <= SI[sp] else 0
            c3rs = C3RS.get((p, sp)); c3 = C3.get((p, sp)); c2 = C2.get((p, sp))
            out.append(dict(season=s, tid=t, p=p, mpg1=m1[0] if m1 else np.nan, gp1=m1[1] if m1 else 0, mpg2=m2[0] if m2 else np.nan, gp2=m2[1] if m2 else 0,
                            exp=exp, c3rs=c3rs[0] if c3rs else np.nan, c3=c3[0] if c3 else np.nan, c2=c2[0] if c2 else np.nan,
                            o3=c3[1] if c3 else np.nan, d3=c3[2] if c3 else np.nan))
    return out

SEASONS = [s for s in S[2:] if (s, ) and any(k[0] == s for k in opening)]
R = pd.DataFrame([r for s in SEASONS for r in prior_rows(s)])

def allocate(m, cap=40.0, total=240.0):
    m = np.array(m, float)
    for _ in range(25):
        free = m < cap - 1e-9
        if m[free].sum() <= 0: break
        m[free] *= (total - m[~free].sum()) / m[free].sum()
        if (m <= cap + 1e-9).all(): break
        m = np.minimum(m, cap)
    return m

def team_features(R, cep_col="c3rs", minutes="mpg", umpg=None, exp_split=False, min_gp=5):
    """roster -> team features. minutes: 'mpg' (per game played), 'avail' (mpg x share of games played), 'blend2' (two seasons)"""
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        known = g[cep_col].notna() & (g.gp1 >= min_gp)
        if minutes == "mpg": raw = g.mpg1.where(known)
        elif minutes == "avail": raw = (g.mpg1 * np.minimum(1, g.gp1 / 70)).where(known)
        elif minutes == "blend2":
            raw = np.where(g.mpg2.notna(), 0.7 * g.mpg1 + 0.3 * g.mpg2, g.mpg1); raw = pd.Series(raw, index=g.index).where(known)
        raw = raw.fillna(umpg[s]).values
        m = allocate(raw); share = m / 48
        c = g[cep_col].where(known).values
        f = {"season": s, "tid": t, "X": np.nansum(share * np.nan_to_num(c)), "U": share[~known.values].sum()}
        if exp_split:
            e = g.exp.values
            for name, lo, hi in (("Xy", 0, 3), ("Xp", 4, 9), ("Xv", 10, 99)):
                sel = known.values & (e >= lo) & (e <= hi)
                f[name] = np.nansum(share[sel] * c[sel])
        rows.append(f)
    return pd.DataFrame(rows)

# league-average minutes of players with no usable prior (rookies etc.), from OTHER seasons only
nop = R[(R.c3rs.isna()) | (R.gp1 < 5)]
UMPG_ALL = {}
for s in SEASONS:
    v = [PS[(p, s)][0] for p, ss in zip(nop.p, nop.season) if ss != s and (p, s) in PS]
    UMPG_ALL[s] = float(np.mean(v)) if v else 12.0

prev_net = {(r.season, r.tid): r.net for r in TM.itertuples()}
def add_targets(F):
    F = F.merge(TM, on=["season", "tid"])
    F["prev"] = [prev_net.get((S[SI[s] - 1], t), np.nan) for s, t in zip(F.season, F.tid)]
    return F

def loso(F, cols, target="net"):
    """leave-one-season-out OLS; returns held-out predictions"""
    pred = pd.Series(np.nan, index=F.index)
    for s in F.season.unique():
        tr, te = F.season != s, F.season == s
        A = np.c_[np.ones(tr.sum()), F.loc[tr, cols].values]
        b = np.linalg.lstsq(A, F.loc[tr, target].values, rcond=None)[0]
        pred[te] = np.c_[np.ones(te.sum()), F.loc[te, cols].values] @ b
    return pred

def score(F, pred, label):
    e = F.net - pred
    # wins from net: fit wins% ~ net on the other seasons, then x games
    wp = pd.Series(np.nan, index=F.index)
    for s in F.season.unique():
        tr, te = F.season != s, F.season == s
        k = np.polyfit(F.loc[tr, "net"], F.loc[tr, "wpct"], 1)
        wp[te] = np.clip(np.polyval(k, pred[te]), 0.05, 0.95)
    we = (wp * F.gp) - F.w; we82 = we / F.gp * 82
    r = {"model": label, "net_rmse": round(float(np.sqrt(np.mean(e ** 2))), 3), "net_mae": round(float(np.mean(np.abs(e))), 3),
         "r": round(float(np.corrcoef(F.net, pred)[0, 1]), 3), "wins_mae_82": round(float(np.mean(np.abs(we82))), 2),
         "within5w": round(float(np.mean(np.abs(we82) <= 5)), 3)}
    print(json.dumps(r)); return r

if __name__ == "__main__":
    results = []
    base = add_targets(team_features(R, umpg=UMPG_ALL))
    ev = base.prev.notna()
    B = base[ev].reset_index(drop=True)
    results.append(score(B, pd.Series(0.0, index=B.index), "M0a  predict 0 (every team average)"))
    results.append(score(B, loso(B, ["prev"]), "M0b  last season's net, regressed"))
    results.append(score(B, loso(B, ["X", "U"]), "M1   roster CEPM x minutes (opening roster)"))
    results.append(score(B, loso(B, ["X", "U", "prev"]), "M2   M1 + last season's net"))
    for mins in ("avail", "blend2"):
        F = add_targets(team_features(R, minutes=mins, umpg=UMPG_ALL)); F = F[F.prev.notna()].reset_index(drop=True)
        results.append(score(F, loso(F, ["X", "U", "prev"]), f"M3   minutes = {mins}"))
    for col in ("c3", "c2"):
        F = add_targets(team_features(R, cep_col=col, umpg=UMPG_ALL)); F = F[F.prev.notna()].reset_index(drop=True)
        results.append(score(F, loso(F, ["X", "U", "prev"]), f"M4   CEPM source = {col}"))
    F = add_targets(team_features(R, exp_split=True, umpg=UMPG_ALL)); F = F[F.prev.notna()].reset_index(drop=True)
    results.append(score(F, loso(F, ["Xy", "Xp", "Xv", "U", "prev"]), "M5   CEPM split by experience (young / prime / veteran)"))
    json.dump(results, open("proj_lab_round1.json", "w"), indent=1)
