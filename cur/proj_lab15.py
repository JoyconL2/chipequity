"""Minutes allocation: proportional scaling (current) shrinks stars and bench equally when a roster's minutes
add up past 240. Real rotations keep stars' minutes and squeeze the bench. Test concentrated allocations."""
exec(open("proj_lab14.py").read().split('# core continuity')[0])
def alloc_pow(raw, gam, cap=40.0):
    w = np.power(np.maximum(raw, 0.01), gam); m = raw.copy()
    for _ in range(30):   # minutes ~ raw * (raw/mean)^(gam-1), scaled to 240, capped at min(cap, raw*1.15) so nobody outgrows his role much
        lim = np.minimum(cap, raw * 1.15 + 2)
        m = w / w.sum() * 240; 
        for _ in range(30):
            over = m > lim
            if not over.any(): break
            fixed = np.where(over, lim, 0); free = ~over & (m < lim)
            m = np.where(over, lim, m); rest = 240 - m[~free].sum(); m[free] = w[free] / w[free].sum() * rest
        break
    return m
def alloc_greedy(raw, cap=40.0):
    order = np.argsort(-raw); m = np.zeros_like(raw); left = 240.0
    for j in order:
        m[j] = min(raw[j], cap, left); left -= m[j]
    if left > 0: m = allocate(np.where(m > 0, m, 0.5) + 0)   # short roster: scale up
    return m
def feats15(mode, gam=1.0):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        c = g.c3f.values.astype(float); gp1 = g.gp1.values; gp2 = g.gp2.values; m1 = np.nan_to_num(g.mpg1.values); m2 = np.nan_to_num(g.mpg2.values)
        k = ~np.isnan(c) & (gp1 >= 5)
        hurt = k & (gp1 < 50) & ~np.isnan(g.c3_s2.values); c = np.where(hurt, g.c3_s2.values, c)
        star = (gp1 < 5) & (gp2 >= 20) & (m2 >= 28) & (np.nan_to_num(c) >= 2); c = np.where(star, c * 0.5, c); k = k | star
        mins = np.where(gp1 >= 5, m1, m2); nU = (~k).sum(); left = max(0.0, 240 - mins[k].sum()); u = min(UMPG_ALL[s], max(10.0, left / max(nU, 1)))
        raw = np.where(k, mins, u).astype(float)
        m = allocate(raw) if mode == "prop" else alloc_greedy(raw) if mode == "greedy" else alloc_pow(raw, gam)
        sh = m / 48; cc = np.where(k, np.nan_to_num(c), 0.0)
        rows.append({"season": s, "tid": t, "X": (sh * cc).sum(), "U": sh[~k].sum()})
    return pd.DataFrame(rows)
for mode, gam in (("prop", 1), ("pow", 1.5), ("pow", 2.0), ("pow", 3.0), ("greedy", 1)):
    f = feats15(mode, gam); F = F13.drop(columns=["X", "U"]).merge(f, on=["season", "tid"]); F["dX"] = F.X - F.Xprev
    F["pc"] = F.prev * F.cont
    print(f"--- allocation {mode} {gam}")
    run5(["prev", "dX", "U", "X"], "standings-first", F)
    run5(["pc", "dX", "U", "X"], "standings x continuity", F)
