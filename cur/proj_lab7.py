exec(open("proj_lab5.py").read().split('print("--- CEPM window')[0])
# CEPM from the window ending TWO seasons back (the last window before a lost season)
C3b = {}
for (p, w), v in C3.items(): C3b[(p, w)] = v[0]
R["c3_prev2"] = [C3b.get((p, S[SI[s]-2])) if SI[s] >= 2 else np.nan for p, s in zip(R.p, R.season)]
R["c3_prev2"] = R.c3_prev2.astype(float)
def feats_ret(mode):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        c = g.c3f.values.astype(float); gp1 = g.gp1.values; gp2 = g.gp2.values; m1 = np.nan_to_num(g.mpg1.values); m2 = np.nan_to_num(g.mpg2.values)
        k = ~np.isnan(c) & (gp1 >= 5)
        if mode in ("ret", "ret_prev2"):
            ret = (gp1 < 5) & (gp2 >= 20)                     # missed (nearly) all of last season, healthy the season before
            if mode == "ret_prev2": c = np.where(ret & ~np.isnan(g.c3_prev2.values), g.c3_prev2.values, c)
            k = k | (ret & ~np.isnan(c))
        mins = np.where(gp1 >= 5, m1, m2)
        raw = np.where(k, mins, UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(c))[k].sum(), "U": sh[~k].sum(), "nret": int(((gp1 < 5) & (gp2 >= 20)).sum())})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
def run(F, label):
    p = loso(F, ["X", "U", "prev"]); p = p - p.groupby(F.season).transform("mean"); r = score(F, p, label)
    sel = F.nret > 0; e0 = (F.net - p)[sel]
    print(f"     teams with a returning player: {sel.sum()}, their net RMSE {np.sqrt((e0**2).mean()):.2f}"); return p
base = feats_ret("base"); p0 = run(base, "current (3-yr, returning stars treated as new)")
F1 = feats_ret("ret"); run(F1, "returning stars: 3-yr CEPM + minutes from their last healthy season")
F2 = feats_ret("ret_prev2"); run(F2, "returning stars: CEPM from the window before the lost season")
def feats_star(shrink):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        c = g.c3f.values.astype(float); gp1 = g.gp1.values; gp2 = g.gp2.values; m1 = np.nan_to_num(g.mpg1.values); m2 = np.nan_to_num(g.mpg2.values)
        k = ~np.isnan(c) & (gp1 >= 5)
        star = (gp1 < 5) & (gp2 >= 20) & (m2 >= 28) & (np.nan_to_num(c) >= 2)
        cc = np.where(star, c * shrink, c); k = k | star
        mins = np.where(gp1 >= 5, m1, m2); raw = np.where(k, mins, UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(cc))[k].sum(), "U": sh[~k].sum(), "nret": int(star.sum())})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
print("--- returning STARS only ---")
for sh in (1.0, 0.75, 0.5):
    run(feats_star(sh), f"returning stars at {int(sh*100)}% of their CEPM")
