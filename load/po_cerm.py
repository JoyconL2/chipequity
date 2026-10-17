"""Playoff-model inputs (regular-season-only 3-year regression) with earlier postseasons' opponent-adjusted lead margin."""
import json, sys, pandas as pd
g = {}; exec(open("po_test.py").read().split('if __name__ == "__main__":')[0], g)
comps, S, SI, D = g["comps"], g["S"], g["SI"], g["D"]; kOf = {int(p): k for k, p in enumerate(D["ids"])}
rs3 = pd.read_csv("../cepm/cepm3_rs.csv")
import os; TAG = os.environ.get("LEADBY", "r1")
for m, adj in ((2, "t"),):
    out = []
    for p, r, we in zip(rs3.player, rs3.rapm, rs3.window_end):
        k = kOf.get(int(p)); si = SI.get(we)
        if k is None or si is None: continue
        c = comps(int(p), [S[x] for x in range(max(0, si - 2), si + 1)], 3000, m, adj, "rs", po_seas=[S[x] for x in range(max(0, si - 2), si)])
        if c: out.append([k, si, round((0.65 * r + 0.35 * c[0]) * c[1], 3)])
    json.dump(out, open(f"../pomodel/cerm_po{m}{adj}_{TAG}.json", "w")); print(m, adj, len(out))
