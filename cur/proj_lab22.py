"""Lighter shrinkage for high-minute players in single-season CEPM: does it predict next season better?"""
import sys
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
VARS = [("lw_0_2000", "current 1-year CEPM"), ("lw_0.5_2000", "lighter: lambda x (2000/poss)^0.5"), ("lw_1_2000", "lighter: lambda x (2000/poss)"), ("lw_1_3000", "lighter: lambda x (3000/poss)")]
for f, lab in VARS:
    C = load(f"{SP}/cepm/{f}.csv")
    rows = []
    for (s, t), gg in R.groupby(["season", "tid"]):
        sp_ = S[SI[s] - 1]; c = np.array([C[(p, sp_)][0] if (p, sp_) in C else np.nan for p in gg.p]); k = ~np.isnan(c) & (gg.gp1.values >= 5)
        raw = np.where(k, np.nan_to_num(gg.mpg1.values), UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(c))[k].sum(), "U": sh[~k].sum()})
    F = add_targets(pd.DataFrame(rows)); F = F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
    p = loso(F, ["X", "U"]); p = p - p.groupby(F.season).transform("mean"); score(F, p, lab)
    p = loso(F, ["X", "U", "prev"]); p = p - p.groupby(F.season).transform("mean"); score(F, p, lab + " + last season's net")
