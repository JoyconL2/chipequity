exec(open("proj_lab9.py").read().split('def run2(')[0])
def feats_d(mode, floor=0.0):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        c = g.c3f.values.astype(float); gp1 = g.gp1.values; gp2 = g.gp2.values; m1 = np.nan_to_num(g.mpg1.values); m2 = np.nan_to_num(g.mpg2.values)
        k = ~np.isnan(c) & (gp1 >= 5)
        hurt = k & (gp1 < 50) & ~np.isnan(g.c3_s2.values); c = np.where(hurt, g.c3_s2.values, c)
        star = (gp1 < 5) & (gp2 >= 20) & (m2 >= 28) & (np.nan_to_num(c) >= 2); c = np.where(star, c * 0.5, c); k = k | star
        mins = np.where(gp1 >= 5, m1, m2); nU = (~k).sum()
        if mode == "flat": u = UMPG_ALL[s]
        else:                                  # depth-aware: unknowns share what's left after the known players' minutes
            left = max(0.0, 240 - mins[k].sum()); u = min(UMPG_ALL[s], max(floor, left / max(nU, 1)))
        raw = np.where(k, mins, u); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(c))[k].sum(), "U": sh[~k].sum()})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
def run3(F, label):
    p = loso(F, ["X", "U", "prev"]); p = p - p.groupby(F.season).transform("mean"); score(F, p, label)
run3(feats_d("flat"), "current: every new player gets ~20 raw minutes")
for fl in (0.0, 4.0, 8.0):
    run3(feats_d("depth", fl), f"depth-aware: new players share the minutes left over (floor {fl:.0f})")
for fl in (10.0, 12.0):
    run3(feats_d("depth", fl), f"depth-aware: new players share the minutes left over (floor {fl:.0f})")
