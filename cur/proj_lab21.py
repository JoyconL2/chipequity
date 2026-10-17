"""Star-controlled on/off (load/ctx_onoff.py) as a predictor of next season, alone and on top of CEPM.
Value = context-matched on/off x W/(W+K): K is how many (harmonic) possessions it takes to trust it halfway."""
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
X0 = pd.read_csv("../load/ctx_onoff.csv"); X0 = X0[X0.weight > 0]
agg = X0.groupby(["player", "season"]).apply(lambda g: pd.Series({"v": np.average(g.ctx_onoff, weights=g.weight), "W": g.weight.sum()}), include_groups=False).reset_index()
CTX = {(int(p), s): (v, W) for p, s, v, W in zip(agg.player, agg.season, agg.v, agg.W)}
C1 = load(f"{SP}/cepm/disp1.csv")
OO = pd.read_csv("../load/onoff.csv"); OO = OO[OO.onoff.notna()].groupby(["p", "season"]).apply(lambda g: np.average(g.onoff, weights=g.op), include_groups=False).to_dict()
def val(kind, p, s, K=2000):
    sp = S[SI[s] - 1]
    if kind == "ctx": v = CTX.get((p, sp)); return v[0] * v[1] / (v[1] + K) if v else np.nan
    if kind == "raw": return OO.get((p, sp), np.nan)
    if kind == "c1": v = C1.get((p, sp)); return v[0] if v else np.nan
    if kind == "c3": v = C3.get((p, sp)); return v[0] if v else np.nan
def feats(kinds, K=2000):
    rows = []
    for (s, t), gg in R.groupby(["season", "tid"]):
        base = np.array([val(kinds[0], p, s, K) for p in gg.p]); k = ~np.isnan(base) & (gg.gp1.values >= 5)
        raw = np.where(k, np.nan_to_num(gg.mpg1.values), UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        r = {"season": s, "tid": t, "U": sh[~k].sum()}
        for kind in kinds:
            c = np.array([val(kind, p, s, K) for p in gg.p]); r["X_" + kind] = (sh * np.nan_to_num(c))[k].sum()
        rows.append(r)
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
def run(kinds, label, K=2000):
    F = feats(kinds, K); cols = ["X_" + k for k in kinds] + ["U"]; p = loso(F, cols); p = p - p.groupby(F.season).transform("mean")
    r = score(F, p, label); b = np.linalg.lstsq(np.c_[np.ones(len(F)), F[cols].values], F.net.values, rcond=None)[0]
    print("     weights", dict(zip(cols, np.round(b[1:], 3))))
run(["raw"], "raw on/off")
for K in (0, 1000, 2000, 4000, 8000):
    run(["ctx"], f"star-controlled on/off, K={K}", K)
run(["c1"], "1-year CEPM")
for K in (1000, 2000, 4000):
    run(["c1", "ctx"], f"1-year CEPM + star-controlled on/off (K={K})", K)
run(["c3"], "3-year CEPM")
run(["c3", "ctx"], "3-year CEPM + star-controlled on/off (K=2000)", 2000)
