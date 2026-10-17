exec(open("proj_lab5.py").read().split('print("--- CEPM window')[0])
lastteam = G.groupby(["season", "tid"]).p.apply(set).to_dict()
def feats2(cep):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        k = (g[cep].notna() & (g.gp1 >= 5)).values
        raw = np.where(k, g.mpg1.fillna(0).values, UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        c = np.nan_to_num(g[cep].values); w = g.win3.values; ok = ~np.isnan(w)
        ret = np.array([p in lastteam.get((S[SI[s]-1], t), set()) for p in g.p])
        rows.append({"season": s, "tid": t, "X": (sh * c)[k].sum(), "U": sh[~k].sum(),
                     "WIN_new": (sh * np.nan_to_num(w))[ok & ~ret].sum(), "WIN_ret": (sh * np.nan_to_num(w))[ok & ret].sum(), "cont": sh[ret].sum() / 5})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
F = feats2("c3f")
def coefs(F, cols):
    A = np.c_[np.ones(len(F)), F[cols].values]; return dict(zip(["a"] + cols, np.round(np.linalg.lstsq(A, F.net.values, rcond=None)[0], 3)))
for cols in (["X","U","prev"], ["X","U","prev","WIN_new"], ["X","U","prev","WIN_new","WIN_ret"]):
    p = loso(F, cols); p = p - p.groupby(F.season).transform("mean"); score(F, p, " + ".join(cols)); print("   coefficients:", coefs(F, cols))
