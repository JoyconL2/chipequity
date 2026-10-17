"""Chip Equity for every CEPM window (1-5 years), each player's best window, and each decade.
Chip Equity = CEPM x Load, Load = MPG/48 (minutes only; the usage / on-ball / stint version is kept in the code with ROLE_W = 0), each ratio = the player's
(possession- or minute-weighted) number over the window / the league's over the same seasons, kept between 0.5 and 2.
Same formula as the page (template.html loadOfRows). Writes data.json keys ce (windows) and cepeak (best + decades)."""
import json, numpy as np, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}
ids = [int(x) for x in D["ids"]]; kOf = {p: k for k, p in enumerate(ids)}
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "gp", "sec", "pos", "usg", "fg2a", "fg3a", "fta", "tov", "ast", "stint")})
P = P[P.t == 0].copy()
P["ob"] = P.fg2a + P.fg3a + 0.44 * P.fta + P.tov + P.ast; P["upos"] = P.usg * P.pos
P["hs"] = P.stint.notna(); P["stsec"] = np.where(P.hs, P.stint.fillna(0) * P.sec, 0.0); P["ssec"] = np.where(P.hs, P.sec, 0.0)
L = P.groupby("s").agg(u=("upos", "sum"), ob=("ob", "sum"), w=("pos", "sum"), st=("stsec", "sum"), sw=("ssec", "sum"))
L["usg"] = L.u / L.w; L["onb"] = L.ob / L.w; L["stint"] = L.st / L.sw
P = P.join(L[["usg", "onb", "stint"]].rename(columns=lambda c: "lg_" + c), on="s")
P["lu"] = P.lg_usg * P.pos; P["lob"] = P.lg_onb * P.pos; P["lst"] = np.where(P.hs, P.lg_stint * P.sec, 0.0)
G = P.groupby(["p", "s"])[["sec", "gp", "pos", "upos", "ob", "stsec", "ssec", "lu", "lob", "lst"]].sum()
G = G.reset_index(); GI = {(k, s): r for k, s, r in zip(G.p, G.s, G.itertuples(index=False))}
cl = lambda v: min(2.0, max(0.5, v))
ROLE_W = 0.0      # minutes only: usage / on-ball share / stint length rewarded high-volume players whose teams didn't win more with them
def load(k, seasons):
    a = np.zeros(10); got = False
    for s in seasons:
        r = GI.get((k, s))
        if r is not None: a += np.array(r[2:], float); got = True
    sec, gp, pos, upos, ob, stsec, ssec, lu, lob, lst = a
    if not got or gp == 0 or pos == 0: return None
    ur, obr = cl(upos / lu), cl(ob / lob); sr = cl((stsec / ssec) / (lst / ssec)) if ssec > 0 else 1.0
    return sec / 60 / gp / 48 * (1 + ROLE_W * ((ur + obr + sr) / 3 - 1))
rows, n = [], {}
MINP = {1: 1500, 2: 3000, 3: 4500, 4: 6000, 5: 7500}
best = {}
for w in (1, 2, 3, 4, 5):
    d = pd.read_csv(f"../cepm/disp{w}.csv")
    for p, r, o, dd, poss, we in zip(d.player, d.rapm, d.o_rapm, d.d_rapm, d.poss, d.window_end):
        k = kOf.get(int(p)); s = SI.get(we)
        if k is None or s is None: continue
        ld = load(k, range(s - w + 1, s + 1))
        if ld is None: continue
        rows.append([k, s, w, r * ld, o * ld, dd * ld, ld, poss])
        if poss >= MINP[w]:
            b = best.get((k, w))
            if b is None or r * ld > b[0]: best[(k, w)] = (r * ld, o * ld, dd * ld, ld, s)
R = pd.DataFrame(rows, columns=["k", "s", "w", "ce", "ceo", "ced", "load", "poss"])
R["rank"] = R.groupby(["s", "w"]).ce.rank(ascending=False, method="min").astype(int)
for (s, w), g in R.groupby(["s", "w"]): n[f"{s}_{w}"] = int(len(g))
r2 = lambda x: round(float(x), 2)
ce = {"rows": [[int(k), int(s), int(w), r2(c), r2(o), r2(d), round(float(l), 3), int(rk)] for k, s, w, c, o, d, l, rk in zip(R.k, R.s, R.w, R.ce, R.ceo, R.ced, R.load, R["rank"])], "n": n}
# best windows + decades, same shape as the CEPM peaks: [k, j, ce_o, ce_d, ce, rank, load, end season]
ds, pn, prow = [], [], []
for j, w in enumerate((1, 2, 3, 4, 5)):
    items = sorted(((v[0], k, v) for (k, ww), v in best.items() if ww == w), reverse=True)
    ds.append(f"Peak {w}Y Chip Equity"); pn.append(len(items))
    for rk, (c, k, v) in enumerate(items, 1): prow.append([k, j, r2(v[1]), r2(v[2]), r2(c), rk, round(v[3], 3), v[4]])
DEC = {"1990s": ("ddec1990.csv", "1996-97", "1999-00"), "2000s": ("ddec2000.csv", "2000-01", "2009-10"), "2010s": ("ddec2010.csv", "2010-11", "2019-20"), "2020s": ("ddec2020.csv", "2020-21", "2025-26")}
for name, (f, a, b) in DEC.items():
    d = pd.read_csv(f"../cepm/{f}"); d = d[d.poss >= 3000]; j = len(ds); items = []
    for p, r, o, dd in zip(d.player, d.rapm, d.o_rapm, d.d_rapm):
        k = kOf.get(int(p))
        if k is None: continue
        ld = load(k, range(SI[a], SI[b] + 1))
        if ld is not None: items.append((r * ld, k, o * ld, dd * ld, ld))
    items.sort(reverse=True); ds.append(f"{name} Chip Equity"); pn.append(len(items))
    for rk, (c, k, o, dd, ld) in enumerate(items, 1): prow.append([k, j, r2(o), r2(dd), r2(c), rk, round(ld, 3), SI[b]])
D["ce"] = ce; D["cepeak"] = {"ds": ds, "n": pn, "rows": prow}
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
print("windows", len(ce["rows"]), "| peaks/decades", dict(zip(ds, pn)))
nm = D["names"]
for j, name in enumerate(ds):
    top = [r for r in prow if r[1] == j][:5]; print(name, [(nm[r[0]], r[4], f"{round(r[6]*100)}%") for r in top])
