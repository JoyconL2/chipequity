"""Current-season model, fit separately from the historical playoff model.

A team's strength before any games = its roster's prior CEPM (regular-season 3-year window ending LAST season),
weighted by each player's projected minutes (last season's minutes per game, scaled to 240 team minutes).
Players with no prior CEPM (rookies, players back from abroad) get a learned team-level term instead.
As games are played, the projection is blended with the team's actual margin: (n*MOV_n + k*proj) / (n + k), k learned.
Game odds: margin ~ Normal(hca + R_home - R_away, sigma), with hca and sigma learned per stage of the season.

Every coefficient is fit leave-one-season-out, and every reported accuracy is on held-out seasons.
Output: cur_params.json (coefficients + backtest), and prints the backtest."""
import json, math
import numpy as np, pandas as pd

D = json.load(open("../site/data.json"))
S = D["seasons"]; P = D["P"]; tid = D["teamIds"]
games = pd.read_csv("games.csv").sort_values(["season", "gid"])
cep = pd.read_csv("../cepm/cepm3_rs.csv")
cep = {(r.window_end, int(r.player)): r.rapm for r in cep.itertuples()}
pid = D["ids"]

# ---- player-season minutes (regular season), and each player's main team that season ----
rows = pd.DataFrame({"k": P["p"], "s": P["s"], "t": P["t"], "tm": P["tm"], "gp": P["gp"], "sec": P["sec"]})
rows = rows[rows.t == 0]
tot = rows.groupby(["k", "s"]).agg(gp=("gp", "sum"), sec=("sec", "sum")).reset_index()
tot["mpg"] = tot.sec / 60 / tot.gp.clip(lower=1)
mpg_prev = {(r.k, r.s): (r.mpg, r.gp) for r in tot.itertuples()}
main = rows.sort_values("sec").groupby(["k", "s"]).tail(1)

# team id per season for an abbreviation index (Hornets ids differ by era in the game files)
season_teams = {s: set(g.home) | set(g.away) for s, g in games.groupby("season")}
def team_id(a, s):
    t = tid[a]
    if t in season_teams[s]: return t
    alt = {1610612766: 1610612740, 1610612740: 1610612766}.get(t)
    return alt if alt in season_teams[s] else t

MAXM, TEAM_MIN = 40.0, 240.0
def allocate(m):
    """scale projected minutes to 240 a game, capping anyone at 40"""
    m = np.array(m, float)
    for _ in range(20):
        free = m < MAXM - 1e-9
        rest = TEAM_MIN - m[~free].sum()
        if m[free].sum() <= 0: break
        m[free] *= rest / m[free].sum()
        if (m <= MAXM + 1e-9).all(): break
        m = np.minimum(m, MAXM)
    return m

def team_features(players, s_prev, unknown_mpg):
    """players: list of NBA ids. Returns X (sum of minutes/48 * CEPM over known players), U (minutes/48 of unknown players)."""
    mp, cv = [], []
    for p in players:
        c = cep.get((s_prev, p)); m = mpg_prev.get((kof.get(p), S.index(s_prev))) if s_prev in S else None
        if c is not None and m is not None and m[1] >= 5: mp.append(m[0]); cv.append(c)
        else: mp.append(unknown_mpg); cv.append(None)
    m = allocate(mp)
    X = sum(mi / 48 * c for mi, c in zip(m, cv) if c is not None)
    U = sum(mi / 48 for mi, c in zip(m, cv) if c is None)
    return X, U

kof = {int(p): k for k, p in enumerate(pid)}
# roster of each team-season = players whose main team it was (players who appeared at least once)
roster = {}
for r in main.itertuples():
    s = S[r.s]; roster.setdefault((s, team_id(r.tm, s)), []).append(int(pid[r.k]))

seasons = [s for s in S[1:] if s in season_teams]                    # need a previous season for priors
mov = {}
for s, g in games.groupby("season"):
    for t in season_teams[s]:
        h = g[g.home == t]; a = g[g.away == t]
        mov[(s, t)] = (np.r_[h.hp - h.ap, a.ap - a.hp]).mean()

# unknown players' projected minutes: average MPG of players with no prior, from OTHER seasons only
def unknown_mpg_excl(s_out):
    v = [tot_mpg for (k, si), (tot_mpg, gp) in mpg_prev.items()
         if S[si] != s_out and si > 0 and (S[si - 1], int(pid[k])) not in cep]
    return float(np.mean(v))
UMPG = {s: unknown_mpg_excl(s) for s in seasons}

feat = []
for s in seasons:
    sp = S[S.index(s) - 1]
    for t in season_teams[s]:
        X, U = team_features(roster.get((s, t), []), sp, UMPG[s])
        prev = mov.get((sp, t), np.nan)
        feat.append((s, t, X, U, mov[(s, t)], prev))
F = pd.DataFrame(feat, columns=["season", "team", "X", "U", "mov", "prev"])

def fit_lin(df):
    A = np.c_[np.ones(len(df)), df.X, df.U]
    return np.linalg.lstsq(A, df.mov, rcond=None)[0]
coef_out = {}; F["proj"] = np.nan; F["base"] = np.nan
for s in seasons:
    tr = F[F.season != s]; c = fit_lin(tr); coef_out[s] = c
    m = F.season == s
    F.loc[m, "proj"] = c[0] + c[1] * F.loc[m, "X"] + c[2] * F.loc[m, "U"]
    trb = tr.dropna(subset=["prev"]); b = np.polyfit(trb.prev, trb.mov, 1)
    F.loc[m, "base"] = np.polyval(b, F.loc[m, "prev"].fillna(0))
ev = F.dropna(subset=["prev"])
rmse = lambda e: float(np.sqrt(np.mean(e ** 2)))
pre = {"rmse_roster": rmse(ev.mov - ev.proj), "rmse_last_season": rmse(ev.mov - ev.base), "rmse_zero": rmse(ev.mov),
       "r_roster": float(np.corrcoef(ev.mov, ev.proj)[0, 1]), "r_last_season": float(np.corrcoef(ev.mov, ev.base)[0, 1]), "n_team_seasons": int(len(ev))}
print("preseason projection of season MOV (held-out seasons):", json.dumps({k: round(v, 3) for k, v in pre.items()}))

# ---- in-season: blend projection with actual margin; walk every game in order ----
projd = {(r.season, r.team): r.proj for r in F.itertuples()}
def walk(s, k):
    g = games[games.season == s]; acc = {}
    out = []
    for r in g.itertuples():
        th, ta = acc.setdefault(r.home, [0, 0.0]), acc.setdefault(r.away, [0, 0.0])
        Rh = (th[1] + k * projd[(s, r.home)]) / (th[0] + k); Ra = (ta[1] + k * projd[(s, r.away)]) / (ta[0] + k)
        out.append((min(th[0], ta[0]), Rh - Ra, r.hp - r.ap))
        th[0] += 1; th[1] += r.hp - r.ap; ta[0] += 1; ta[1] += r.ap - r.hp
    return out
KS = [2, 4, 6, 8, 10, 12, 15, 20, 25, 30, 40]
def game_loss(rows, hca):
    return np.mean([(m - (hca + d)) ** 2 for _, d, m in rows])
walks = {(s, k): walk(s, k) for s in seasons for k in KS}
LOSS = {(s2, k): game_loss(walks[(s2, k)], 3.0) for s2 in seasons for k in KS}
best_k = {}
for s in seasons:
    errs = {k: np.mean([LOSS[(s2, k)] for s2 in seasons if s2 != s]) for k in KS}
    best_k[s] = min(errs, key=errs.get)
K_ALL = min(KS, key=lambda k: np.mean([LOSS[(s2, k)] for s2 in seasons]))
print("blend k (games of prior weight), all seasons:", K_ALL, "| held-out choices:", sorted(set(best_k.values())))

STAGES = [(0, 0), (1, 10), (11, 25), (26, 50), (51, 82)]
def stage_rows(s, k): return walks[(s, k)]
held = []                                             # (stage, pred diff incl hca, margin) on held-out seasons
stage_par = {}
for s in seasons:
    k = best_k[s]
    tr = [x for s2 in seasons if s2 != s for x in walks[(s2, best_k[s])]]
    te = walks[(s, k)]
    for j, (lo, hi) in enumerate(STAGES):
        a = [(d, m) for n, d, m in tr if lo <= n <= hi]
        d, m = np.array(a).T
        hca = float(np.mean(m - d)); sig = float(np.std(m - d - hca))
        for n, dd, mm in te:
            if lo <= n <= hi: held.append((j, dd + hca, mm, sig))
H = pd.DataFrame(held, columns=["stage", "pred", "margin", "sig"])
H["p"] = 0.5 * (1 + np.vectorize(math.erf)(H.pred / (H.sig * math.sqrt(2))))
H["win"] = (H.margin > 0).astype(int)
bt_games = []
for j, (lo, hi) in enumerate(STAGES):
    h = H[H.stage == j]
    acc = float(((h.p > 0.5) == (h.win == 1)).mean()); ll = float(-np.mean(h.win * np.log(h.p) + (1 - h.win) * np.log(1 - h.p)))
    bt_games.append({"stage": f"{lo}-{hi}" if hi else "opening", "games": int(len(h)), "acc": round(acc, 4), "logloss": round(ll, 4)})
print("game picks by games already played (held-out):", bt_games)

# final parameters from ALL seasons
c = fit_lin(F); K = K_ALL
allrows = [x for s2 in seasons for x in walks[(s2, K)]]
stages = []
for lo, hi in STAGES:
    a = np.array([(d, m) for n, d, m in allrows if lo <= n <= hi]); hca = float(np.mean(a[:, 1] - a[:, 0])); sig = float(np.std(a[:, 1] - a[:, 0] - hca))
    stages.append({"lo": lo, "hi": hi, "hca": round(hca, 3), "sigma": round(sig, 3)})

# ---- playoff series picked with the end-of-season blended rating (held out) ----
ab = D["abbrs"]
endR = {}
for s in seasons:
    k = best_k[s]; g = games[games.season == s]; acc = {}
    for r in g.itertuples():
        for t, m in ((r.home, r.hp - r.ap), (r.away, r.ap - r.hp)):
            e = acc.setdefault(t, [0, 0.0]); e[0] += 1; e[1] += m
    for t, (n, sm) in acc.items(): endR[(s, t)] = (sm + k * projd[(s, t)]) / (n + k)
Wins = {(S[s], team_id(a, S[s])): w for a, s, t, w in zip(D["T"]["a"], D["T"]["s"], D["T"]["t"], D["T"]["w"]) if t == 0 and S[s] in season_teams}
def series_p(dr, hca, sig, need):
    ph = 0.5 * (1 + math.erf((dr + hca) / (sig * math.sqrt(2)))); pa = 0.5 * (1 + math.erf((dr - hca) / (sig * math.sqrt(2))))
    order = [1, 1, 0, 0, 1, 0, 1] if need == 4 else [1, 1, 0, 0, 1]
    from functools import lru_cache
    @lru_cache(None)
    def f(i, a, b):
        if a == need: return 1.0
        if b == need: return 0.0
        p = ph if order[i] else pa
        return p * f(i + 1, a + 1, b) + (1 - p) * f(i + 1, a, b + 1)
    return f(0, 0, 0)
last = stages[-1]; ok = n = 0
for x in D["series"]:
    s = S[x[0]]
    if s not in season_teams: continue
    w, l = team_id(x[2], s), team_id(x[3], s)
    if (s, w) not in endR or (s, l) not in endR: continue
    need = 3 if (x[1] == 1 and int(s[:4]) <= 2001) else 4
    hw = Wins.get((s, w), 0) >= Wins.get((s, l), 0)            # better record has home court
    dr = (endR[(s, w)] - endR[(s, l)]) * (1 if hw else -1)
    p_home = series_p(dr, last["hca"], last["sigma"], need)
    pw = p_home if hw else 1 - p_home
    ok += pw > 0.5; n += 1
print(f"playoff series picked with the end-of-season rating (held-out k): {ok}/{n} = {ok / n:.3f}")

json.dump({"a": round(float(c[0]), 4), "b": round(float(c[1]), 4), "c": round(float(c[2]), 4), "k": K, "unknown_mpg": round(float(np.mean(list(UMPG.values()))), 2),
           "max_min": MAXM, "stages": stages, "prior_window": "regular-season 3-year CEPM ending last season",
           "backtest": {"preseason": pre, "games": bt_games, "series": {"n": n, "acc": round(ok / n, 4)}, "seasons": f"{seasons[0]} to {seasons[-1]}"}},
          open("cur_params.json", "w"), indent=1)
print(json.dumps({"a": c[0], "b": c[1], "c": c[2], "k": K, "stages": stages}, default=float))
