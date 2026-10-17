"""Factor CEPM vs CEPM for predicting next season (same opening-roster minutes; seasons 2001-02..2025-26, since
factor data covers 2000-01..2024-25)."""
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
FC = pd.read_csv("../factors/factor_cepm.csv")
FV = {(int(p), s, w): v for p, s, w, v in zip(FC.player, FC.window_end, FC.w, FC.fcepm)}
C1 = load(f"{SP}/cepm/disp1.csv")
def val(kind, p, s):
    sp = S[SI[s] - 1]
    c1 = C1.get((p, sp)); c3 = C3.get((p, sp)); f1 = FV.get((p, sp, 1)); f3 = FV.get((p, sp, 3))
    if kind == "cepm1": return c1[0] if c1 else np.nan
    if kind == "cepm3": return c3[0] if c3 else np.nan
    if kind == "fac1": return f1 if f1 is not None else np.nan
    if kind == "fac3": return f3 if f3 is not None else np.nan
    if kind == "avg1": return (c1[0] + f1) / 2 if c1 and f1 is not None else (c1[0] if c1 else np.nan)
    if kind == "avg3": return (c3[0] + f3) / 2 if c3 and f3 is not None else (c3[0] if c3 else np.nan)
def feats(kind):
    rows = []
    for (s, t), gg in R.groupby(["season", "tid"]):
        if not ("2001-02" <= s <= "2025-26"): continue
        c = np.array([val(kind, p, s) for p in gg.p]); k = ~np.isnan(c) & (gg.gp1.values >= 5)
        raw = np.where(k, np.nan_to_num(gg.mpg1.values), UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(c))[k].sum(), "U": sh[~k].sum()})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna()].reset_index(drop=True)
for kind, lab in (("cepm1", "1-year CEPM"), ("fac1", "1-year factor CEPM"), ("avg1", "1-year average of both"), ("cepm3", "3-year CEPM"), ("fac3", "3-year factor CEPM"), ("avg3", "3-year average of both")):
    F = feats(kind); p = loso(F, ["X", "U"]); p = p - p.groupby(F.season).transform("mean"); score(F, p, lab)
