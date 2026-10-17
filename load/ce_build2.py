"""Chip Equity v2 (shipped 2026-10-16).
For a window of seasons W (1-5 years, or a decade), regular-season inputs:
  CE = ((1 - 0.5) x CEPM_W + 0.5 x LeadMargin_W) x CompShare_W x (1 + 0.35 x (OnBall_W - 1))
  LeadMargin = team margin per 100 possessions in the stints where he is the best player on the floor (by 1-year CEPM),
               garbage time out, shrunk by n / (n + 3000) lead possessions
  CompShare  = his seconds outside garbage time / his team's seconds outside garbage time, in games he played
  OnBall     = (shots + 0.44 FT + turnovers + assists) per possession on the floor vs the league, kept in 0.5..2
Single seasons are steadied: 40% of both CEPM and lead margin comes from the 3-season window ending that season
(the first full window, 1996-99, for 1996-97 and 1997-98; lead margin pooled over it and shrunk by n / (n + 9000)).
Also writes the playoff model's top-3 values (regular-season-only 3-year CEPM in the same formula): data.json "cerm"."""
import json, numpy as np, pandas as pd
W_M, B, UO, K1 = 0.5, 0.4, 0.35, 3000
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}
ids = [int(x) for x in D["ids"]]; kOf = {p: k for k, p in enumerate(ids)}; nm = D["names"]
M = pd.read_csv("margin_attr.csv"); LEAD = {(int(p), s): (v, n) for p, s, v, n in zip(M.p, M.season, M.lead, M.lead_poss)}
C = pd.read_csv("comp_share.csv"); COMP = {(int(p), s): (a, b) for p, s, a, b in zip(C.p, C.season, C.comp, C.t_comp)}
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "pos", "fg2a", "fg3a", "fta", "tov", "ast")}); P = P[P.t == 0]
P["ob"] = P.fg2a + P.fg3a + 0.44 * P.fta + P.tov + P.ast
lgr = (P.groupby("s").ob.sum() / P.groupby("s").pos.sum()).to_dict()
g = P.groupby(["p", "s"])[["ob", "pos"]].sum(); OBC = {(ids[k], S[s]): (r.ob, r.pos, lgr[s]) for (k, s), r in g.iterrows()}
cl = lambda v: min(2.0, max(0.5, v))
def comps(p, seasons, K=K1):
    ln = lnn = ca = cb = ob = pos = lpos = 0.0
    for s in seasons:
        v = LEAD.get((p, s));  c = COMP.get((p, s)); o = OBC.get((p, s))
        if v: ln += v[0] * v[1]; lnn += v[1]
        if c: ca += c[0]; cb += c[1]
        if o: ob += o[0]; pos += o[1]; lpos += o[2] * o[1]
    if cb <= 0 or pos <= 0: return None
    lead = (ln / lnn) * lnn / (lnn + K) if lnn else 0.0
    return lead, ca / cb, cl((ob / pos) / (lpos / pos))
def ce(cepm, lead, share, obr): return ((1 - W_M) * cepm + W_M * lead) * share * (1 + UO * (obr - 1))
disp = {w: pd.read_csv(f"../cepm/disp{w}.csv") for w in (1, 2, 3, 4, 5)}
C3 = {(int(p), s): r for p, s, r in zip(disp[3].player, disp[3].window_end, disp[3].rapm)}
rows, n = [], {}; best = {}
MINP = {1: 1500, 2: 3000, 3: 4500, 4: 6000, 5: 7500}
for w, d in disp.items():
    out = []
    for p, r, we, poss in zip(d.player, d.rapm, d.window_end, d.poss):
        p = int(p); k = kOf.get(p); si = SI.get(we)
        if k is None or si is None: continue
        seas = [S[x] for x in range(max(0, si - w + 1), si + 1)]
        c = comps(p, seas)
        if c is None: continue
        lead, share, obr = c
        if w == 1:                                   # steady toward the 3-season level
            j = max(si, 2); wseas = [S[x] for x in range(j - 2, j + 1)]
            c3 = C3.get((p, S[j]), r); l3 = comps(p, wseas, K=9000)
            r = (1 - B) * r + B * c3; lead = (1 - B) * lead + B * (l3[0] if l3 else lead)
        v = ce(r, lead, share, obr); load = share * (1 + UO * (obr - 1))
        out.append((k, si, w, v, load, poss))
        if poss >= MINP[w] and not (w == 1 and si == 0):          # single-season board starts at 1997-98
            b = best.get((k, w))
            if b is None or v > b[0]: best[(k, w)] = (v, load, si)
    R = pd.DataFrame(out, columns=["k", "s", "w", "ce", "load", "poss"])
    R["rank"] = R.groupby("s").ce.rank(ascending=False, method="min").astype(int)
    for s_, gg in R.groupby("s"): n[f"{s_}_{w}"] = int(len(gg))
    rows += [[int(a), int(b_), int(c_), round(float(e), 2), None, None, round(float(l), 3), int(rk)] for a, b_, c_, e, l, rk in zip(R.k, R.s, R.w, R.ce, R.load, R["rank"])]
ds, pn, prow = [], [], []
for j, w in enumerate((1, 2, 3, 4, 5)):
    items = sorted(((v[0], k, v) for (k, ww), v in best.items() if ww == w), reverse=True)
    ds.append(f"Peak {w}Y Chip Equity"); pn.append(len(items))
    for rk, (v, k, x) in enumerate(items, 1): prow.append([k, j, None, None, round(v, 2), rk, round(x[1], 3), x[2]])
DEC = {"1990s": ("ddec1990.csv", "1996-97", "1999-00"), "2000s": ("ddec2000.csv", "2000-01", "2009-10"), "2010s": ("ddec2010.csv", "2010-11", "2019-20"), "2020s": ("ddec2020.csv", "2020-21", "2025-26")}
for name, (f, a, b) in DEC.items():
    d = pd.read_csv(f"../cepm/{f}"); d = d[d.poss >= 3000]; j = len(ds); items = []
    seas = [S[x] for x in range(SI[a], SI[b] + 1)]
    for p, r in zip(d.player, d.rapm):
        k = kOf.get(int(p)); c = comps(int(p), seas) if k is not None else None
        if c: items.append((ce(r, *c), k, c[1] * (1 + UO * (c[2] - 1))))
    items.sort(reverse=True); ds.append(f"{name} Chip Equity"); pn.append(len(items))
    for rk, (v, k, l) in enumerate(items, 1): prow.append([k, j, None, None, round(v, 2), rk, round(l, 3), SI[b]])
# playoff model: regular-season-only 3-year CEPM in the same formula
rs3 = pd.read_csv("../cepm/cepm3_rs.csv"); cerm = []
for p, r, we in zip(rs3.player, rs3.rapm, rs3.window_end):
    k = kOf.get(int(p)); si = SI.get(we)
    if k is None or si is None: continue
    c = comps(int(p), [S[x] for x in range(max(0, si - 2), si + 1)])
    if c: cerm.append([k, si, round(ce(r, *c), 3)])
D["ce"] = {"rows": rows, "n": n, "v": 2}; D["cepeak"] = {"ds": ds, "n": pn, "rows": prow}; D["cerm"] = cerm
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
print("windows", len(rows), "| playoff values", len(cerm))
for j, name in enumerate(ds):
    top = [r for r in prow if r[1] == j][:8]; print(name, ", ".join(f"{nm[r[0]]} {S[r[7]]} {r[4]:+.2f}" for r in top))
