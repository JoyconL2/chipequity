import sys; sys.argv=[sys.argv[0]]
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
# minutes allocation with concentration gamma: raw^gamma, then scaled to 240 with a cap
def allocate_g(m, gamma, cap):
    m = np.power(np.maximum(np.array(m, float), 0.1), gamma); m = m / m.sum() * 240
    for _ in range(25):
        if (m <= cap + 1e-9).all(): break
        over = m > cap; extra = (m[over] - cap).sum(); m[over] = cap; free = ~over & (m < cap)
        m[free] += extra * m[free] / m[free].sum()
    return m
def feats(gamma, cap, cep="c2"):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        known = (g[cep].notna() & (g.gp1 >= 5)).values
        raw = np.where(known, g.mpg1.fillna(0).values, UMPG_ALL[s])
        m = allocate_g(raw, gamma, cap); sh = m / 48; c = np.nan_to_num(g[cep].values)
        rows.append({"season": s, "tid": t, "X": (sh * c)[known].sum(), "U": sh[~known].sum(), "top": np.sort(m)[-1]})
    F = add_targets(pd.DataFrame(rows)); return F[F.prev.notna()].reset_index(drop=True)
grid = {}
for gamma in (1.0, 1.5, 2.0, 2.5, 3.0):
    for cap in (36, 38, 40):
        F = feats(gamma, cap); grid[(gamma, cap)] = F
# nested choice: for each held-out season, pick (gamma, cap) using only the other seasons' held-out errors
errs = {}
for key, F in grid.items():
    p = loso(F, ["X", "U", "prev"]); errs[key] = pd.Series((F.net - p).values ** 2, index=F.season.values)
seasons = sorted(set(grid[(1.0, 40)].season))
chosen_pred = []; chosen = {}
for s in seasons:
    best = min(errs, key=lambda k: errs[k][errs[k].index != s].mean()); chosen[s] = best
    F = grid[best]; p = loso(F, ["X", "U", "prev"]); chosen_pred.append((F.season == s, p, F))
for key in sorted(errs): print(key, "rmse", round(float(np.sqrt(errs[key].mean())), 3), "| star minutes (avg team's top player)", round(float(grid[key].top.mean()), 1))
# nested result
F0 = grid[(1.0, 40)].copy(); P0 = pd.Series(np.nan, index=F0.index)
for s in seasons:
    F = grid[chosen[s]]; p = loso(F, ["X", "U", "prev"]); m = F.season == s
    P0[F0.season == s] = p[m].values
print("chosen settings:", sorted(set(chosen.values())))
score(F0, P0, "R3 minutes concentration chosen without seeing the season (nested)")
