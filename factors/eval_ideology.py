import json, numpy as np, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}
ids = [int(x) for x in D["ids"]]; kOf = {p: k for k, p in enumerate(ids)}; nm = D["names"]
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "gp", "sec")}); P = P[P.t == 0]
G = P.groupby(["p", "s"])[["sec", "gp"]].sum(); MPG = {(k, s): r.sec / 60 / r.gp for (k, s), r in G.iterrows() if r.gp}
def mpgw(k, s, w):
    sec = gp = 0
    for x in range(s - w + 1, s + 1):
        if (k, x) in G.index: r = G.loc[(k, x)]; sec += r.sec; gp += r.gp
    return sec / 60 / gp if gp else np.nan
F = pd.read_csv("factor_cepm.csv")
C = {1: pd.read_csv("../cepm/disp1.csv"), 3: pd.read_csv("../cepm/disp3.csv")}
GREATS = ["LeBron James", "Chris Paul", "Stephen Curry", "Shai Gilgeous-Alexander", "Kevin Garnett", "Tim Duncan", "Kevin Durant", "Dwyane Wade", "Shaquille O'Neal", "Kawhi Leonard", "Nikola Jokić", "Giannis Antetokounmpo"]
HOGS = ["James Harden", "Luka Dončić", "Russell Westbrook"]
for w, minp in ((1, 1500), (3, 4500)):
    f = F[(F.w == w) & (F.poss >= minp)].copy(); c = C[w]; c = c[(c.window_end >= "2000-01") & (c.window_end <= "2024-25") & (c.poss >= minp)]
    m = f.merge(c[["player", "window_end", "rapm"]], on=["player", "window_end"])
    print(f"== {w}-year windows: correlation factor CEPM vs CEPM {np.corrcoef(m.fcepm, m.rapm)[0,1]:.2f} (n={len(m)})")
    for lab, col in (("CEPM", "rapm"), ("Factor CEPM", "fcepm"), ("Average of both", "avg")):
        m["avg"] = (m.rapm + m.fcepm) / 2
        m["k"] = [kOf.get(int(p)) for p in m.player]; m = m[m.k.notna()]
        m["ce"] = [v * mpgw(int(k), SI[s], w) / 48 for v, k, s in zip(m[col], m.k, m.window_end)]
        best = m.sort_values("ce", ascending=False).drop_duplicates("k")
        rk = {nm[int(k)]: i + 1 for i, k in enumerate(best.k)}
        top = [f"{nm[int(k)]} {s} {v:+.1f}" for k, s, v in zip(best.k[:10], best.window_end[:10], best.ce[:10])]
        g = [rk.get(n, 999) for n in GREATS]; h = [rk.get(n, 999) for n in HOGS]
        print(f"  {lab:16s} Chip Equity best-{'season' if w==1 else 'window'} top 10: {', '.join(top)}")
        print(f"  {'':16s} greats' ranks {dict(zip([n.split()[-1] for n in GREATS], g))} avg {np.mean(g):.1f} | Harden/Luka/Russ {h}")
