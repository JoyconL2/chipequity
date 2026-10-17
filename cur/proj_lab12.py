"""Standings-first projection: last season's team result is the base, roster changes adjust it.
   net_s = a + b * net_{s-1} + c * (roster value now - roster value last season) [+ d * net_{s-2}]
Roster value = sum over players of (minutes share x 5) x CEPM, using the SAME CEPM ratings for both rosters,
so the difference is purely who came and went (and how minutes shifted)."""
exec(open("proj_lab11.py").read().split('def run3(')[0])
# last season's actual roster value for each team: minutes on THAT team last season x the same CEPM ratings
cep_now = {(p, s): v for p, s, v in zip(R.p, R.season, R.c3f)}
def player_val(p, s):        # rating used for season s (window ending s-1, healthy form etc. as in the opening-roster model)
    return cep_now.get((p, s))
G_team_min = G.groupby(["season", "tid", "p"])["min"].sum().reset_index()
tot_min = G_team_min.groupby(["season", "tid"])["min"].sum().to_dict()
cache_c3f = {}
def c3f_for(p, s):
    sp = S[SI[s] - 1]
    v = C3.get((p, sp)); v2 = C2.get((p, sp))
    return v[0] if v else (v2[0] if v2 else np.nan)
prev_val = {}
for (s, t), g in G_team_min.groupby(["season", "tid"]):
    i = SI[s] + 1
    if i >= len(S): continue
    nxt = S[i]                                     # this roster is "last season" for season nxt
    share = g["min"].values / tot_min[(s, t)] * 5
    vals = np.array([c3f_for(p, nxt) for p in g.p])
    known = ~np.isnan(vals)
    prev_val[(nxt, t)] = float((share[known] * vals[known]).sum()) * 1.0
F = feats_d("depth", 10.0)
F["Xprev"] = [prev_val.get((s, t), np.nan) for s, t in zip(F.season, F.tid)]
F["dX"] = F.X - F.Xprev
F["prev2"] = [prev_net.get((S[SI[s] - 2], t), np.nan) if SI[s] >= 2 else np.nan for s, t in zip(F.season, F.tid)]
F = F[F.Xprev.notna() & F.prev2.notna()].reset_index(drop=True)
def run4(cols, label):
    p = loso(F, cols); p = p - p.groupby(F.season).transform("mean")
    A = np.c_[np.ones(len(F)), F[cols].values]; b = np.linalg.lstsq(A, F.net.values, rcond=None)[0]
    score(F, p, label); print("     weights:", {c: round(float(v), 3) for c, v in zip(cols, b[1:])})
run4(["X", "U", "prev"], "current roster model (last season ~15%)")
run4(["prev", "dX", "U"], "standings-first: last season's net + roster change")
run4(["prev", "prev2", "dX", "U"], "standings-first + two seasons ago")
run4(["prev", "dX", "U", "X"], "standings-first + roster level")
