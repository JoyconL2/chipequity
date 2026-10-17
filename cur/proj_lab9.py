src = open("proj_lab7.py").read()
exec(src.split('base = feats_ret("base")')[0]); exec(src.split('print("--- returning STARS only ---")')[0].split('run(F2, "returning stars: CEPM from the window before the lost season")')[1])
# "healthy form": for players whose last season was cut short, use the better of the window ending last season
# and the window ending the season before (their last mostly-healthy 3-year stretch)
R["c3_s2"] = [C3b.get((p, S[SI[s]-2])) if SI[s] >= 2 else np.nan for p, s in zip(R.p, R.season)]
R["c3_s2"] = R.c3_s2.astype(float)
def feats_h(gp_cut, mode):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        c = g.c3f.values.astype(float); gp1 = g.gp1.values; gp2 = g.gp2.values; m1 = np.nan_to_num(g.mpg1.values); m2 = np.nan_to_num(g.mpg2.values)
        k = ~np.isnan(c) & (gp1 >= 5)
        hurt = k & (gp1 < gp_cut) & ~np.isnan(g.c3_s2.values)
        if mode == "max": c = np.where(hurt, np.fmax(c, g.c3_s2.values), c)
        if mode == "s2":  c = np.where(hurt, g.c3_s2.values, c)
        star = (gp1 < 5) & (gp2 >= 20) & (m2 >= 28) & (np.nan_to_num(c) >= 2); c = np.where(star, c * 0.5, c); k = k | star
        mins = np.where(gp1 >= 5, m1, m2); raw = np.where(k, mins, UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(c))[k].sum(), "U": sh[~k].sum(), "nh": int(hurt.sum())})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
def run2(F, label):
    p = loso(F, ["X", "U", "prev"]); p = p - p.groupby(F.season).transform("mean"); score(F, p, label)
run2(feats_h(0, "none"), "current model")
for cut in (40, 50, 60):
    run2(feats_h(cut, "max"), f"healthy form: best of last two 3-yr windows if under {cut} games last season")
run2(feats_h(50, "s2"), "healthy form: window before the short season (under 50 games)")
