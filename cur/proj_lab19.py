"""How well does each player rating predict NEXT season's team net rating? Same opening-roster minutes for all;
only the rating changes. Leave-one-season-out fits (X + new-player minutes), 1998-99..2025-26."""
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
oo = pd.read_csv("../load/onoff.csv"); oo = oo[oo.onoff.notna()]
oo["w"] = oo.op
g = oo.groupby(["p", "season"]).apply(lambda x: pd.Series({"onoff": np.average(x.onoff, weights=x.w), "poss": x.op.sum()}), include_groups=False).reset_index()
OO = {(int(p), s): (v, n) for p, s, v, n in zip(g.p, g.season, g.onoff, g.poss)}
C1 = load(f"{SP}/cepm/disp1.csv")
def val(kind, p, s):
    sp = S[SI[s] - 1]
    if kind == "onoff": v = OO.get((p, sp)); return v[0] if v else np.nan
    if kind == "onoff_shrunk": v = OO.get((p, sp)); return v[0] * v[1] / (v[1] + 3000) if v else np.nan
    if kind == "cepm1": v = C1.get((p, sp)); return v[0] if v else np.nan
    if kind == "cepm3": v = C3.get((p, sp)); return v[0] if v else np.nan
def feats(kind):
    rows = []
    for (s, t), gg in R.groupby(["season", "tid"]):
        c = np.array([val(kind, p, s) for p in gg.p]); k = ~np.isnan(c) & (gg.gp1.values >= 5)
        raw = np.where(k, np.nan_to_num(gg.mpg1.values), UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        rows.append({"season": s, "tid": t, "X": (sh * np.nan_to_num(c))[k].sum(), "U": sh[~k].sum()})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
for kind, lab in (("onoff", "raw on/off (last season)"), ("onoff_shrunk", "raw on/off, shrunk by sample size"), ("cepm1", "1-year CEPM (last season)"), ("cepm3", "3-year CEPM")):
    F = feats(kind); p = loso(F, ["X", "U"]); p = p - p.groupby(F.season).transform("mean")
    score(F, p, f"{lab}: roster only")
    p2 = loso(F, ["X", "U", "prev"]); p2 = p2 - p2.groupby(F.season).transform("mean"); score(F, p2, f"{lab}: + last season's net")
