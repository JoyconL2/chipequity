src = open("proj_lab7.py").read()
exec(src.split('base = feats_ret("base")')[0]); exec(src.split('print("--- returning STARS only ---")')[0].split('run(F2, "returning stars: CEPM from the window before the lost season")')[1])
F = feats_star(0.5); p = loso(F, ["X", "U", "prev"]); F["proj"] = p - p.groupby(F.season).transform("mean")
slope = float(np.polyfit(F.net, F.wpct - 0.5, 1)[0]); F["m_pct"] = np.clip(0.5 + slope * F.proj, 0.05, 0.95)
L = pd.read_csv("market/win_totals.csv")
L["tid"] = [tid[D["abbrs"].index(ab)] for ab in L.abbr]; L["tid"] = [fix_tid(s, t, have) for s, t in zip(L.season, L.tid)]
L["k_pct"] = L.line / L.games; L["k_pct"] = L.k_pct - L.groupby("season").k_pct.transform("mean") + 0.5     # remove the books' margin
X = F.merge(L[["season", "tid", "k_pct"]], on=["season", "tid"])
print("team-seasons with a market line:", len(X), "| seasons:", sorted(X.season.unique()))
mae = lambda pct: float(np.mean(np.abs(pct - X.wpct)) * 82)
print(f"model alone:  wins MAE {mae(X.m_pct):.2f}")
print(f"market alone: wins MAE {mae(X.k_pct):.2f}")
# blend weight on the model, chosen leave-one-season-out
bl = pd.Series(np.nan, index=X.index); ws = {}
for s in X.season.unique():
    tr = X.season != s
    grid = np.linspace(0, 1, 101); err = [np.mean(np.abs(w * X.m_pct[tr] + (1 - w) * X.k_pct[tr] - X.wpct[tr])) for w in grid]
    w = grid[int(np.argmin(err))]; ws[s] = w; bl[X.season == s] = w * X.m_pct[X.season == s] + (1 - w) * X.k_pct[X.season == s]
print("model weight chosen on the other seasons:", ws)
print(f"blend:        wins MAE {mae(bl):.2f}")
for s in sorted(X.season.unique()):
    x = X.season == s; print(f"  {s}: model {np.mean(np.abs(X.m_pct[x]-X.wpct[x]))*82:.1f} | market {np.mean(np.abs(X.k_pct[x]-X.wpct[x]))*82:.1f} | blend {np.mean(np.abs(bl[x]-X.wpct[x]))*82:.1f}")
grid = np.linspace(0, 1, 101); w_all = grid[int(np.argmin([np.mean(np.abs(w * X.m_pct + (1 - w) * X.k_pct - X.wpct)) for w in grid]))]
print("weight on all seasons:", w_all)
json.dump({"w_model": float(w_all), "fold_weights": ws, "mae_model": mae(X.m_pct), "mae_market": mae(X.k_pct), "mae_blend": mae(bl), "n": int(len(X)), "seasons": sorted(X.season.unique())}, open("market/blend.json", "w"), indent=1)
