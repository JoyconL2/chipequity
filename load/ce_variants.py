import json, numpy as np, pandas as pd
src = open("ce_build.py").read(); exec(src[src.index("D = json.load"):src.index("rows, n = [], {}")])
def agg(k, seasons):
    a = np.zeros(10); got = False
    for s in seasons:
        r = GI.get((k, s))
        if r is not None: a += np.array(r[2:], float); got = True
    return a if got else None
def make(mode):
    def f(k, seasons):
        a = agg(k, seasons)
        if a is None: return None
        sec, gp, pos, upos, ob, stsec, ssec, lu, lob, lst = a
        if gp == 0 or pos == 0: return None
        m = sec / 60 / gp / 48; ur, obr = cl(upos / lu), cl(ob / lob); sr = cl((stsec / ssec) / (lst / ssec)) if ssec > 0 else 1.0
        if mode == "full": return m * (ur + obr + sr) / 3
        if mode == "half": return m * (1 + 0.5 * ((ur + obr + sr) / 3 - 1))
        if mode == "min_stint": return m * (1 + 0.5 * (sr - 1))
        if mode == "min": return m
    return f
NAMES = ["James Harden", "Luka Dončić", "Russell Westbrook", "Chris Paul", "Michael Jordan", "LeBron James", "Stephen Curry", "Shai Gilgeous-Alexander", "Kevin Garnett", "Tim Duncan", "Kevin Durant", "Dwyane Wade", "Shaquille O'Neal", "Kawhi Leonard", "Nikola Jokić", "Giannis Antetokounmpo", "Trae Young"]
d = pd.read_csv("../cepm/disp3.csv"); d = d[d.poss >= 4500]
for mode in ("full", "half", "min_stint", "min"):
    L = make(mode); best = {}
    for p, r, we in zip(d.player, d.rapm, d.window_end):
        k = kOf.get(int(p)); s = SI.get(we)
        if k is None or s is None: continue
        ld = L(k, range(s - 2, s + 1))
        if ld is None: continue
        if k not in best or r * ld > best[k][0]: best[k] = (r * ld, r, ld)
    rk = sorted(best.items(), key=lambda x: -x[1][0]); pos = {k: i + 1 for i, (k, _) in enumerate(rk)}
    nm = D["names"]
    print(f"== {mode}: top 12", [f"{nm[k]} {v[0]:.1f}" for k, v in rk[:12]])
    print("   ", ", ".join(f"{n} #{pos[nm.index(n)]} ({best[nm.index(n)][0]:.1f})" for n in NAMES if nm.index(n) in pos))
