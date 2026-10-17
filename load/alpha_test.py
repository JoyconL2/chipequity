"""Lighter minutes weight: Chip Equity with CompShare ** ALPHA (ALPHA = 1 is the shipped version)."""
import sys, json, numpy as np, pandas as pd
from scipy.stats import spearmanr
ALPHA = float(sys.argv[1])
src = open("ce_build2.py").read(); src = src[src.index("import json"):src.index('D["ce"] = ')]
src = src.replace("def ce(cepm, lead, share, obr): return ((1 - W_M) * cepm + W_M * lead) * share * (1 + UO * (obr - 1))",
                  "def ce(cepm, lead, share, obr): return ((1 - W_M) * cepm + W_M * lead) * share ** ALPHA * (1 + UO * (obr - 1))")
exec(src)
json.dump(cerm, open(f"cerm_{ALPHA}.json", "w"))
import json as _j, os as _o; _EV = next((_j.load(open(_f)) for _f in ("eval_list.json", "../load/eval_list.json") if _o.path.exists(_f)), {}); T = _EV.get("T", [])   # private evaluation list, kept out of the repo
def ranks(j):
    items = sorted(((v[0], k) for (k, ww), v in best.items() if ww == j), reverse=True); return {nm[k]: i + 1 for i, (v, k) in enumerate(items)}, items
for w, lab in ((1, "single season"), (5, "best 5-year")):
    rk, items = ranks(w); rho = spearmanr(range(len(T)), [rk.get(n, 9999) for n in T]).correlation
    print(f"alpha {ALPHA} {lab:13s}: match {rho:.2f} | Curry #{rk['Stephen Curry']} Wemby #{rk.get('Victor Wembanyama')} Harden #{rk['James Harden']} Kobe #{rk['Kobe Bryant']} Embiid #{rk['Joel Embiid']} Nash #{rk['Steve Nash']} Tatum #{rk['Jayson Tatum']}")
    if w == 1: print("   top 12:", ", ".join(f"{nm[k].split()[-1]} {v:+.1f}" for v, k in items[:12]))
# 2025-26 board
si = SI["2025-26"]; cur = sorted([(r[3], r[0]) for r in rows if r[1] == si and r[2] == 1], reverse=True)
G = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "gp")}); G = G[(G.t == 0) & (G.s == si)].groupby("p").gp.sum()
cur = [(v, k) for v, k in cur if G.get(k, 0) >= 40]
print("   2025-26:", ", ".join(f"{nm[k].split()[-1]} {v:+.1f}" for v, k in cur[:6]))
