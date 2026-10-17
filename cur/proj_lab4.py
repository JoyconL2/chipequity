import sys; sys.argv=[sys.argv[0]]
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
def feats(returning=False, two=False, exp=False):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        c2 = g.c2.values; c3 = g.c3rs.values; gp1 = g.gp1.values; gp2 = g.gp2.values; m1 = g.mpg1.values; m2 = g.mpg2.values; e = g.exp.values
        k1 = ~np.isnan(c2) & (gp1 >= 5)
        k = k1 | (~np.isnan(c2) & (gp2 >= 20)) if returning else k1
        mins = np.where(gp1 >= 5, np.nan_to_num(m1), np.nan_to_num(m2))
        raw = np.where(k, mins, UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        f = {"season": s, "tid": t, "X": (sh * np.nan_to_num(c2))[k].sum(), "U": sh[~k].sum(), "Xret": (sh * np.nan_to_num(c2))[k & ~k1].sum()}
        if two: f["X3"] = (sh * np.nan_to_num(c3))[k & ~np.isnan(c3)].sum()
        if exp:
            for nm, lo, hi in (("Xy", 0, 3), ("Xp", 4, 9), ("Xv", 10, 99)): sel = k & (e >= lo) & (e <= hi); f[nm] = (sh * np.nan_to_num(c2))[sel].sum()
        rows.append(f)
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna()].reset_index(drop=True)
F = feats(); score(F, loso(F, ["X", "U", "prev"]), "R4-0 best so far (c2 + prev)")
F = feats(returning=True); score(F, loso(F, ["X", "U", "prev"]), "R4-1 returning players use their last healthy season")
score(F, loso(F, ["X", "Xret", "U", "prev"]), "R4-2 ... with their own weight")
F = feats(returning=True, two=True); score(F, loso(F, ["X", "X3", "U", "prev"]), "R4-3 + 3-year CEPM as a second input")
F = feats(returning=True, exp=True); score(F, loso(F, ["Xy", "Xp", "Xv", "U", "prev"]), "R4-4 returning + experience split")
