import json, numpy as np, pandas as pd
src = open("ce_build.py").read(); exec(src[src.index("D = json.load"):src.index("rows, n = [], {}")])
d = pd.read_csv("../cepm/disp1.csv"); d = d[d.poss >= 1500]
nm = D["names"]; out = {m: [] for m in ("min", "usg_half", "usg_full")}
for p, r, we in zip(d.player, d.rapm, d.window_end):
    k = kOf.get(int(p)); s = SI.get(we)
    if k is None or s is None: continue
    g = GI.get((k, s))
    if g is None: continue
    sec, gp, pos, upos, ob, stsec, ssec, lu, lob, lst = np.array(g[2:], float)
    if gp == 0: continue
    m = sec / 60 / gp / 48; ur = cl(upos / lu)
    out["min"].append((r * m, nm[k], we, r, m, upos / pos))
    out["usg_half"].append((r * m * (1 + 0.5 * (ur - 1)), nm[k], we, r, m, upos / pos))
    out["usg_full"].append((r * m * ur, nm[k], we, r, m, upos / pos))
for mode, L in out.items():
    L.sort(reverse=True)
    print(f"== {mode}")
    for i, (ce, n, s, r, m, u) in enumerate(L[:12], 1): print(f"  {i:2d}. {n} {s}: {ce:+.1f}  (CEPM {r:+.1f}, {m*48:.1f} mpg, usage {u:.1f}%)")
    for who in ("James Harden", "Russell Westbrook", "Luka Dončić"):
        b = [(i, x) for i, x in enumerate(L, 1) if x[1] == who][:1]
        if b: i, x = b[0]; print(f"     best {who}: #{i} {x[2]} {x[0]:+.1f}")
