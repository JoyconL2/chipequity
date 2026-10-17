exec(open("proj_lab9.py").read().split('def run2(')[0])
F = feats_h(50, "s2"); p = loso(F, ["X", "U", "prev"]); F["proj"] = p - p.groupby(F.season).transform("mean")
slope = float(np.polyfit(F.net, F.wpct - 0.5, 1)[0])
w82 = lambda net: 82 * np.clip(0.5 + slope * net, 0.03, 0.97)
F["actual_w"] = 82 * F.wpct
sd = lambda x: float(np.std(x))
print("--- how spread out (standard deviation of wins across the league, per season, averaged) ---")
g = F.groupby("season")
print(f"actual final records : {g.actual_w.apply(sd).mean():.1f} wins")
print(f"model projections    : {g.proj.apply(lambda x: sd(w82(x))).mean():.1f} wins")
L = pd.read_csv("market/win_totals.csv"); L["pct"] = L.line / L.games; L["pct"] -= L.groupby("season").pct.transform("mean") - 0.5
print(f"market lines         : {L.groupby('season').pct.apply(lambda x: sd(82 * x)).mean():.1f} wins  (6 seasons)")
print("--- stretch the projections apart by a factor and re-test on held-out seasons ---")
for k in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5):
    e = w82(k * F.proj) - F.actual_w
    print(f"x{k:.1f}: wins MAE {np.mean(np.abs(e)):.2f} | spread {F.assign(q=w82(k * F.proj)).groupby('season').q.apply(sd).mean():.1f} | top team avg {F.assign(q=w82(k*F.proj)).groupby('season').q.max().mean():.0f} wins, worst {F.assign(q=w82(k*F.proj)).groupby('season').q.min().mean():.0f}")
# nested: choose the factor on the other seasons
best = []
for s in F.season.unique():
    tr = F.season != s
    ks = np.arange(1.0, 1.81, 0.05); err = [np.mean(np.abs(w82(k * F.proj[tr]) - F.actual_w[tr])) for k in ks]; best.append(ks[int(np.argmin(err))])
print("factor chosen on other seasons:", sorted(set(np.round(best, 2))))
