exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
C1 = load(f"{SP}/cepm/disp1.csv")
oo = pd.read_csv("../load/onoff.csv"); oo = oo[oo.on_net.notna()]
g = oo.groupby(["p", "season"]).apply(lambda x: pd.Series({"on": np.average(x.on_net, weights=x.op), "n": x.op.sum()}), include_groups=False).reset_index()
ON = {(int(p), s): v * n / (n + 3000) for p, s, v, n in zip(g.p, g.season, g.on, g.n)}
for wgt in (0.0, 0.25, 0.5):
    rows = []
    for (s, t), gg in R.groupby(["season", "tid"]):
        sp_ = S[SI[s] - 1]
        c = np.array([((1 - wgt) * C1[(p, sp_)][0] + wgt * ON.get((p, sp_), 0.0)) if (p, sp_) in C1 else np.nan for p in gg.p]); k = ~np.isnan(c) & (gg.gp1.values >= 5)
        raw = np.where(k, np.nan_to_num(gg.mpg1.values), UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(c))[k].sum(), "U": sh[~k].sum()})
    F = add_targets(pd.DataFrame(rows)); F = F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
    p = loso(F, ["X", "U"]); p = p - p.groupby(F.season).transform("mean"); score(F, p, f"1-yr CEPM with {int(wgt*100)}% on-court margin")
