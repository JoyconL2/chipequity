"""Test folding opponent-adjusted playoff lead margin (and playoff minutes share) into Chip Equity.
 m     weight of a playoff possession vs a regular-season one (0 = current stat)
 adj   raw / t (opponent team strength) / l (opponent lineup)
 sh    rs = regular-season competitive share only; mix = playoff minutes count too (same weight m)
Scores: rank match with a private evaluation list (best 1/3/5-year boards)."""
import json, numpy as np, pandas as pd, itertools, sys
from scipy.stats import spearmanr
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}; ids = [int(x) for x in D["ids"]]
nm = {p: D["names"][k] for k, p in enumerate(ids)}
import os; _SUF = "" if os.environ.get("LEADBY", "r3") == "r3" else "_" + os.environ["LEADBY"]
M = pd.read_csv(f"margin_attr_od{_SUF}.csv"); LEAD = {(int(p), s): (n, v) for p, s, n, v in zip(M.p, M.season, M.lead_poss, M.lead)}
C = pd.read_csv("comp_share.csv"); COMP = {(int(p), s): (a, b) for p, s, a, b in zip(C.p, C.season, C.comp, C.t_comp)}
PO = pd.read_csv(f"po_lead{_SUF}.csv"); POL = {(int(p), s): r for p, s, r in zip(PO.p, PO.season, PO.to_dict("records"))}
import json as _j, os as _o; _EV = next((_j.load(open(_f)) for _f in ("eval_list.json", "../load/eval_list.json") if _o.path.exists(_f)), {}); T = _EV.get("T", [])   # private evaluation list, kept out of the repo
def comps(p, seas, K, m, adj, sh, po_seas=None):
    n = net = ca = cb = 0.0
    for s in seas:
        v = LEAD.get((p, s)); c = COMP.get((p, s))
        if v and v[0] > 0: n += v[0]; net += v[0] * v[1]
        if c: ca += c[0]; cb += c[1]
    if cb <= 0: return None
    for s in (seas if po_seas is None else po_seas):
        q = POL.get((p, s))
        if m and q:
            lv = q["lead"] if adj == "raw" else q["lead_" + adj]
            n += m * q["n"]; net += m * q["n"] * lv
            if sh == "mix": ca += m * q["po_sec"]; cb += m * q["po_tsec"]
    return (net / (n + K) if n else 0.0), ca / cb
disp = {w: pd.read_csv(f"../cepm/disp{w}.csv") for w in (1, 3, 5)}
C3 = {(int(p), s): r for p, s, r in zip(disp[3].player, disp[3].window_end, disp[3].rapm)}
MINP = {1: 1500, 3: 4500, 5: 7500}
def board(w, m, adj, sh, WL=0.35, B=0.4):
    d = disp[w]; d = d[d.poss >= MINP[w]]; rows = []
    for p, r, we in zip(d.player, d.rapm, d.window_end):
        p = int(p); si = SI[we]
        if w == 1 and si == 0: continue
        seas = [S[x] for x in range(max(0, si - w + 1), si + 1)]; c = comps(p, seas, 3000, m, adj, sh)
        if c is None: continue
        ln, share = c
        if w == 1:
            j = max(si, 2); r = (1 - B) * r + B * C3.get((p, S[j]), r); x = comps(p, [S[t] for t in range(j - 2, j + 1)], 9000, m, adj, sh)
            if x: ln = (1 - B) * ln + B * x[0]
        rows.append((p, we, ((1 - WL) * r + WL * ln) * share))
    return pd.DataFrame(rows, columns=["p", "s", "v"])
def match(R):
    b = R.sort_values("v", ascending=False).drop_duplicates("p"); rk = {nm[p]: i + 1 for i, p in enumerate(b.p)}
    return spearmanr(range(len(T)), [rk.get(n, 9999) for n in T]).correlation, rk
if __name__ == "__main__":
    out = []
    for m, adj, sh in [(0, "t", "rs")] + list(itertools.product((0.5, 1, 2, 3), ("raw", "t", "l"), ("rs", "mix"))):
        res = {}; 
        for w in (1, 3, 5): res[w] = match(board(w, m, adj, sh))
        rk1, rk5 = res[1][1], res[5][1]
        out.append(dict(m=m, adj=adj, sh=sh, m1=res[1][0], m3=res[3][0], m5=res[5][0], mean=np.mean([res[w][0] for w in (1, 3, 5)]),
                        **{f"5y_{n.split()[-1]}": rk5.get(n) for n in T}, ))
        print(out[-1]["m"], adj, sh, round(out[-1]["mean"], 3), flush=True)
    R = pd.DataFrame(out); R.to_csv("po_test.csv", index=False)
    pd.set_option("display.width", 300); print(R.sort_values("mean", ascending=False).round(3).to_string(index=False))
