"""Next-season team test for Chip Equity with opponent-adjusted playoff lead margin folded in (per-100 rate; the
projection supplies minutes). Only seasons up to the one before the predicted season are used."""
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
import json, sys
g = {}; src = open("../load/po_test.py").read().split('if __name__ == "__main__":')[0]
import os; os.chdir("../load"); exec(src, g); os.chdir("../cur")
comps = g["comps"]; SS = g["S"]; SIl = {s: i for i, s in enumerate(SS)}
d1 = pd.read_csv(f"{SP}/cepm/disp1.csv"); C1v = {(int(p), s): r for p, s, r in zip(d1.player, d1.window_end, d1.rapm)}
d3 = pd.read_csv(f"{SP}/cepm/disp3.csv"); C3v = {(int(p), s): r for p, s, r in zip(d3.player, d3.window_end, d3.rapm)}
cache = {}
def rate(p, s, m, adj, sh, B=0.4, WL=0.35):
    key = (p, s, m, adj, sh)
    if key in cache: return cache[key]
    r = C1v.get((p, s)); c = comps(p, [s], 3000, m, adj, sh) if r is not None else None
    if c is None: cache[key] = np.nan; return np.nan
    si = SIl[s]; j = max(si, 2); r = (1 - B) * r + B * C3v.get((p, SS[j]), r)
    x = comps(p, [SS[t] for t in range(j - 2, j + 1)], 9000, m, adj, sh); lm = (1 - B) * c[0] + B * (x[0] if x else c[0])
    v = (1 - WL) * r + WL * lm; cache[key] = v; return v
CASES = {"playoffs x2, opp-adjusted, lead by " + os.environ.get("LEADBY", "r1"): (2, "t", "rs")}
for tag, (m, adj, sh) in CASES.items():
    rows = []
    for (s, t), gg in R.groupby(["season", "tid"]):
        sp_ = S[SI[s] - 1]; c = np.array([rate(int(p), sp_, m, adj, sh) for p in gg.p]); k = ~np.isnan(c) & (gg.gp1.values >= 5)
        raw = np.where(k, np.nan_to_num(gg.mpg1.values), UMPG_ALL[s]); mm = allocate(raw); shr = mm / 48
        rows.append({"season": s, "tid": t, "X": (shr * np.nan_to_num(c))[k].sum(), "U": shr[~k].sum()})
    F = add_targets(pd.DataFrame(rows)); F = F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
    p = loso(F, ["X", "U"]); p = p - p.groupby(F.season).transform("mean"); score(F, p, tag)
