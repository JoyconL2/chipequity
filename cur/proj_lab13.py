"""Ground-up rework (user brief): standings count only as far as the same core returns; roster shape matters
(a lead scorer, quality support pieces, shooting, defense). Every feature is tested leave-one-season-out."""
exec(open("proj_lab12.py").read().split('def run4(')[0])
# ---- last-season player box (all teams combined), per 75 possessions ----
P = pd.DataFrame(D["P"]); P = P[P.t == 0]; P["nid"] = [int(D["ids"][k]) for k in P.p]; P["season"] = [S[i] for i in P.s]
B = P.groupby(["nid", "season"])[["pts", "fg2a", "fg3a", "fg3m", "fta", "pos", "sec", "gp", "ast", "stl", "blk"]].sum()
B["pts75"] = B.pts * 75 / B.pos.clip(lower=1); B["ts"] = B.pts / (2 * (B.fg2a + B.fg3a + 0.44 * B.fta)).clip(lower=1)
B["tpa75"] = B.fg3a * 75 / B.pos.clip(lower=1); B["tpp"] = B.fg3m / B.fg3a.clip(lower=1)
lgts = (P.groupby("season").pts.sum() / (2 * (P.groupby("season").fg2a.sum() + P.groupby("season").fg3a.sum() + 0.44 * P.groupby("season").fta.sum()))).to_dict()
BX = B.to_dict("index")
# ---- each player's last-season team net, minute-weighted across his teams (does the core carry a winning history?) ----
net_of = {(r.season, r.tid): r.net for r in TM.itertuples()}
pnet = {}
for (s, p), g in G_team_min.groupby(["season", "p"]):
    w = g["min"].values; n = np.array([net_of.get((s, t), np.nan) for t in g.tid]); k = ~np.isnan(n)
    if k.any(): pnet[(p, s)] = float((w[k] * n[k]).sum() / w[k].sum())
# share of last season's team minutes that are back on the opening roster (continuity)
team_last = {}
for (s, t), g in G_team_min.groupby(["season", "tid"]): team_last[(s, t)] = dict(zip(g.p, g["min"]))
def feats13():
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        sp = S[SI[s] - 1]
        c = g.c3f.values.astype(float); gp1 = g.gp1.values; gp2 = g.gp2.values; m1 = np.nan_to_num(g.mpg1.values); m2 = np.nan_to_num(g.mpg2.values)
        k = ~np.isnan(c) & (gp1 >= 5)
        hurt = k & (gp1 < 50) & ~np.isnan(g.c3_s2.values); c = np.where(hurt, g.c3_s2.values, c)
        star = (gp1 < 5) & (gp2 >= 20) & (m2 >= 28) & (np.nan_to_num(c) >= 2); c = np.where(star, c * 0.5, c); k = k | star
        mins = np.where(gp1 >= 5, m1, m2); nU = (~k).sum(); left = max(0.0, 240 - mins[k].sum()); u = min(UMPG_ALL[s], max(10.0, left / max(nU, 1)))
        m = allocate(np.where(k, mins, u)); sh = m / 48; cc = np.where(k, np.nan_to_num(c), 0.0)
        o = np.nan_to_num(g.o3.values); d = np.nan_to_num(g.d3.values)
        f = {"season": s, "tid": t, "X": (sh * cc).sum(), "U": sh[~k].sum(), "Xo": (sh * o * k).sum(), "Xd": (sh * d * k).sum()}
        order = np.argsort(-cc); f["top1"] = cc[order[0]]; f["top2"] = cc[order[1]]; f["top3"] = cc[order[2]]
        rot = (m >= 15) & k; f["aux"] = int(((cc >= 1.0) & rot).sum()) - int(cc[order[0]] >= 1.0)    # support pieces besides the best player
        f["auxq"] = float(np.clip(cc[rot], 0, None).sum() - max(cc[order[0]], 0))
        # lead scorer: highest points per 75 among rotation players, his efficiency over league, and his CEPM
        best = None
        for j, p in enumerate(g.p.values):
            bx = BX.get((p, sp))
            if bx and m[j] >= 24 and bx["gp"] >= 20 and (best is None or bx["pts75"] > best[0]): best = (bx["pts75"], bx["ts"] - lgts[sp], cc[j])
        f["scorer"] = best[0] if best else 15.0; f["scorer_ts"] = best[1] if best else 0.0; f["scorer_c"] = best[2] if best else 0.0
        tpa = tpp = wsum = 0.0
        for j, p in enumerate(g.p.values):
            bx = BX.get((p, sp))
            if bx and bx["pos"] > 300: tpa += sh[j] * bx["tpa75"]; tpp += sh[j] * bx["fg3m"]; wsum += sh[j] * bx["fg3a"]
        f["tpa"] = tpa / 5; f["tpp"] = (tpp / wsum) if wsum else 0.35
        # continuity with last season's team, and the minute-weighted last-season team net the incoming roster carries
        last = team_last.get((sp, t), {}); tot = sum(last.values()) or 1
        f["cont"] = sum(v for p, v in last.items() if p in set(g.p)) / tot
        pn = np.array([pnet.get((p, sp), np.nan) for p in g.p]); kk = ~np.isnan(pn)
        f["carry"] = float((sh[kk] * pn[kk]).sum() / max(sh[kk].sum(), 1e-9)) if kk.any() else 0.0
        rows.append(f)
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
F13 = feats13()
F13["Xprev"] = [prev_val.get((s, t), np.nan) for s, t in zip(F13.season, F13.tid)]; F13["dX"] = F13.X - F13.Xprev
F13 = F13[F13.Xprev.notna()].reset_index(drop=True)
F13["prev_c"] = F13.prev * F13.cont; F13["prev2"] = [prev_net.get((S[SI[s] - 2], t), np.nan) if SI[s] >= 2 else np.nan for s, t in zip(F13.season, F13.tid)]
F13["prev2"] = F13.prev2.fillna(0); F13["prev2_c"] = F13.prev2 * F13.cont
F13["scorer_x"] = (F13.scorer - 20).clip(lower=0) * (F13.scorer_ts > 0)
F13["tp"] = F13.tpa * (F13.tpp - 0.355)
F13.to_pickle("F13.pkl")
def run5(cols, label, F=F13):
    p = loso(F, cols); p = p - p.groupby(F.season).transform("mean")
    A = np.c_[np.ones(len(F)), F[cols].values]; b = np.linalg.lstsq(A, F.net.values, rcond=None)[0]
    r = score(F, p, label); print("     weights:", {c: round(float(v), 3) for c, v in zip(cols, b[1:])}); return p
if __name__ == "__main__":
    print(F13[["cont", "carry", "top1", "aux", "scorer", "scorer_ts", "tpa", "tpp"]].describe().round(3).to_string())
    run5(["prev", "dX", "U", "X"], "current (standings-first)")
    run5(["prev_c", "U", "X"], "standings x continuity + roster")
    run5(["prev_c", "carry", "U", "X"], "+ net carried by incoming players")
    run5(["prev_c", "prev2_c", "carry", "U", "X"], "+ two seasons ago x continuity")
    run5(["prev_c", "carry", "U", "Xo", "Xd"], "o / d split")
    run5(["prev_c", "carry", "U", "X", "top1", "aux"], "+ best player + support pieces")
    run5(["prev_c", "carry", "U", "X", "top1", "auxq"], "+ best player + support quality")
    run5(["prev_c", "carry", "U", "X", "scorer_x", "scorer_ts"], "+ lead scorer")
    run5(["prev_c", "carry", "U", "X", "tp"], "+ shooting")
    run5(["prev_c", "carry", "U", "X", "top1", "auxq", "scorer_x", "scorer_ts", "tp", "Xd"], "everything")
