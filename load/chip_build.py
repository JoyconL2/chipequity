"""Chip Equity (v3, version A): the site's one impact stat (replaces CEPM in every display).
  Chip Equity = (0.65 x CEPM + 0.35 x LeadMargin) x CompShare        (offense and defense the same way)
  CEPM       = the ridge regression (cepm/disp{w}.csv), points per 100 possessions on the floor
  LeadMargin = his team's margin per 100 in the stints where he is the best player on the floor, split into offense
               (points scored vs league) and defense (points allowed vs league), garbage time out, x n/(n+3000)
  CompShare  = his share of his team's non-garbage minutes, in games he played
LeadMargin also counts his playoff lead stints, each playoff possession worth 2 regular-season ones, with the margin
adjusted for the opponent: + the opponent team's regular-season offense/defense vs league (load/po_lead.py).
Lead margin is also adjusted for teammates, offense and defense separately: the four teammates' 3-year o (or d), centred
by season, x 0.5 when they are above average and x 2.0 when below.
Playoff-only Chip Equity (pcepm) = (0.65 x playoff-only regression + 0.35 x opponent-adjusted playoff lead margin
x n/(n+1000)) x playoff competitive share.
Single seasons are steadied 40% toward the 3-season window (first full window 1996-99 for the first two seasons).
Writes data.json rw (1-5 year rows), peak (best 2-5 year windows + decades), cerm (playoff model, regular season only)
and empties the old Chip Equity layer (ce, cepeak)."""
import json, numpy as np, pandas as pd
from decimal import Decimal, ROUND_HALF_UP
WL, B, K1, KS, MPO, KPO = 0.35, 0.4, 3000, 9000, 2.0, 1000
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}
ids = [int(x) for x in D["ids"]]; kOf = {p: k for k, p in enumerate(ids)}
M = pd.read_csv("margin_attr_od.csv"); LEAD = {(int(p), s): (n, v, o, dd) for p, s, n, v, o, dd in zip(M.p, M.season, M.lead_poss, M.lead, M.lead_off, M.lead_def)}
PO = pd.read_csv("po_lead.csv"); POL = {(int(p), s): r for p, s, r in zip(PO.p, PO.season, PO.to_dict("records"))}
# teammate adjustment (half strength): in his lead stints, subtract 0.5 x his four teammates' 3-year o and d, centred
# on the season average, so a star carrying a thin roster isn't marked down for his teammates (load/tm_sums.py)
BETA = 0.5
_TM = pd.read_csv("tm_sums.csv"); _g = _TM.assign(wo=_TM.tmo * _TM.n, wd=_TM.tmd * _TM.n).groupby(["stype", "season"])
_co = (_g.wo.sum() / _g.n.sum()).to_dict(); _cd = (_g.wd.sum() / _g.n.sum()).to_dict()
TMA = {(int(p), s_, t): (o - _co[(t, s_)], d - _cd[(t, s_)]) for p, s_, t, o, d in zip(_TM.p, _TM.season, _TM.stype, _TM.tmo, _TM.tmd)}
# per side: where his teammates were below average (offense or defense), give back twice their shortfall (x2.0);
# where they were above average, take off half (x0.5). Tested 1997-2026: better next-season player and team prediction.
BETA_WEAK = 2.0
bet = lambda a: BETA_WEAK if a < 0 else BETA
for k_, (n_, v_, o_, d_) in list(LEAD.items()):
    ao, ad = TMA.get((k_[0], k_[1], "rs"), (0.0, 0.0)); bo, bd = bet(ao), bet(ad); LEAD[k_] = (n_, v_ - bo * ao - bd * ad, o_ - bo * ao, d_ - bd * ad)
for k_, q in POL.items():
    if q["n"] > 0:
        ao, ad = TMA.get((k_[0], k_[1], "po"), (0.0, 0.0)); bo, bd = bet(ao), bet(ad); q["lead_t"] -= bo * ao + bd * ad; q["off_t"] -= bo * ao; q["de_t"] -= bd * ad
C = pd.read_csv("comp_share.csv"); COMP = {(int(p), s): (a, b) for p, s, a, b in zip(C.p, C.season, C.comp, C.t_comp)}
def comps(p, seas, K, po_seas=None):
    n = net = off = de = ca = cb = 0.0
    for s in seas:
        v = LEAD.get((p, s)); c = COMP.get((p, s))
        if v and v[0] > 0: n += v[0]; net += v[0] * v[1]; off += v[0] * v[2]; de += v[0] * v[3]
        if c: ca += c[0]; cb += c[1]
    if cb <= 0: return None
    for s in (seas if po_seas is None else po_seas):      # playoff lead stints, opponent-adjusted, x MPO
        q = POL.get((p, s))
        if q and q["n"] > 0: w = MPO * q["n"]; n += w; net += w * q["lead_t"]; off += w * q["off_t"]; de += w * q["de_t"]
    f = (1 / n) * n / (n + K) if n else 0.0
    return net * f, off * f, de * f, ca / cb
disp = {w: pd.read_csv(f"../cepm/disp{w}.csv") for w in (1, 2, 3, 4, 5)}
c3 = disp[3]; C3 = {(int(p), s): (r, o, d) for p, s, r, o, d in zip(c3.player, c3.window_end, c3.rapm, c3.o_rapm, c3.d_rapm)}
def value(p, si, w, r, o, d):
    seas = [S[x] for x in range(max(0, si - w + 1), si + 1)]; c = comps(p, seas, K1)
    if c is None: return None
    ln, lo, ld, sh = c
    if w == 1:
        j = max(si, 2); rr = C3.get((p, S[j]), (r, o, d)); x = comps(p, [S[t] for t in range(j - 2, j + 1)], KS)
        r, o, d = [(1 - B) * a + B * b for a, b in zip((r, o, d), rr)]
        if x: ln, lo, ld = [(1 - B) * a + B * b for a, b in zip((ln, lo, ld), x[:3])]
    f = lambda cep, lead: ((1 - WL) * cep + WL * lead) * sh
    return f(r, ln), f(o, lo), f(d, ld)
def split(r, o, d):
    """Offense/defense scaled to add up to the total: the gap between the total fit and the split fit is shared in
    proportion to |o| and |d|, then rounded so the 1-decimal numbers on the site add up exactly."""
    gap = r - (o + d); a, b = abs(o), abs(d); t = a + b
    o += gap * (a / t if t else 0.5); d += gap * (b / t if t else 0.5)
    O1 = round(o, 1); R1 = float(Decimal(round(r, 2)).quantize(Decimal("0.1"), ROUND_HALF_UP))   # how the site shows the stored total (JS toFixed)
    return O1, round(R1 - O1, 1)
MINP = {2: 3000, 3: 4500, 4: 6000, 5: 7500}
rw_rows, rw_n, best, bestx = [], {}, {}, {}   # bestx: (k, w, kind) -> best window by total (0) / offense (1) / defense (2)
for w, d in disp.items():
    out = []
    for p, r, o, dd, we, poss in zip(d.player, d.rapm, d.o_rapm, d.d_rapm, d.window_end, d.poss):
        p = int(p); k = kOf.get(p); si = SI.get(we)
        if k is None or si is None: continue
        v = value(p, si, w, r, o, dd)
        if v is None: continue
        out.append((k, si, w, v[1], v[2], v[0], poss))
        if w >= 2 and poss >= MINP[w]:
            b = best.get((k, w))
            if b is None or v[0] > b[0]: best[(k, w)] = v
            O1, D1 = split(v[0], v[1], v[2])
            for kind, val in ((0, v[0]), (1, O1), (2, D1)):
                b = bestx.get((k, w, kind))
                if b is None or val > b[0]: bestx[(k, w, kind)] = (val, v[0], O1, D1, si)
    R = pd.DataFrame(out, columns=["k", "s", "w", "o", "d", "r", "poss"])
    R["rank"] = R.groupby("s").r.rank(ascending=False, method="min").astype(int)
    if w <= 5:
        for s_, gg in R.groupby("s"): rw_n[f"{s_}_{w}"] = int(len(gg))
        rw_rows += [[int(a), int(b_), int(c_), *split(r_, o, dd_), round(r_, 2), int(rk), int(round(ps))] for a, b_, c_, o, dd_, r_, ps, rk in zip(R.k, R.s, R.w, R.o, R.d, R.r, R.poss, R["rank"])]
DS = D["peak"]["ds"]; prow, pn = [], []
for j, name in enumerate(DS):
    if name.startswith("Peak"):
        w = int(name.split()[1][0]); items = sorted(((v[0], k, v) for (k, ww), v in best.items() if ww == w), reverse=True)
    else:
        f = {"1990s CEPM": ("ddec1990.csv", "1996-97", "1999-00"), "2000s CEPM": ("ddec2000.csv", "2000-01", "2009-10"), "2010s CEPM": ("ddec2010.csv", "2010-11", "2019-20"), "2020s CEPM": ("ddec2020.csv", "2020-21", S[-1])}[name]
        dd_ = pd.read_csv(f"../cepm/{f[0]}"); dd_ = dd_[dd_.poss >= 3000]; seas = [S[x] for x in range(SI[f[1]], SI[f[2]] + 1)]; items = []
        for p, r, o, de in zip(dd_.player, dd_.rapm, dd_.o_rapm, dd_.d_rapm):
            k = kOf.get(int(p)); c = comps(int(p), seas, K1) if k is not None else None
            if c: items.append((((1 - WL) * r + WL * c[0]) * c[3], k, (((1 - WL) * r + WL * c[0]) * c[3], ((1 - WL) * o + WL * c[1]) * c[3], ((1 - WL) * de + WL * c[2]) * c[3])))
        items.sort(reverse=True)
    pn.append(len(items))
    for rk, (v, k, x) in enumerate(items, 1): prow.append([k, j, *split(x[0], x[1], x[2]), round(x[0], 2), rk])
# playoff model: regular-season-only 3-year CEPM in the same formula
rs3 = pd.read_csv("../cepm/cepm3_rs.csv"); cerm = []
for p, r, we in zip(rs3.player, rs3.rapm, rs3.window_end):
    k = kOf.get(int(p)); si = SI.get(we)
    if k is None or si is None: continue
    c = comps(int(p), [S[x] for x in range(max(0, si - 2), si + 1)], K1, po_seas=[S[x] for x in range(max(0, si - 2), si)])   # earlier postseasons only
    if c: cerm.append([k, si, round(((1 - WL) * r + WL * c[0]) * c[3], 3)])
# playoff-only Chip Equity
pc = []
for k, si, v, o, d, poss, rank, n in json.load(open("pcepm_raw.json")):   # playoff-only regression rows, as fit
    q = POL.get((ids[k], S[si])); sh = q["po_share"] if q and np.isfinite(q["po_share"]) else 0.6
    f = q["n"] / (q["n"] + KPO) if q else 0.0; L = (lambda x: q[x] * f) if q else (lambda x: 0.0)
    pc.append([k, si, ((1 - WL) * v + WL * L("lead_t")) * sh, ((1 - WL) * o + WL * L("off_t")) * sh, ((1 - WL) * d + WL * L("de_t")) * sh, poss, n])
PC = pd.DataFrame(pc, columns=["k", "si", "v", "o", "d", "poss", "n"]); PC["rank"] = PC.groupby("si").v.rank(ascending=False, method="min").astype(int)
D["pcepm"] = [[int(a), int(b), round(c, 2), *split(c, e, f_), int(g_), int(h), int(i)] for a, b, c, e, f_, g_, h, i in zip(PC.k, PC.si, PC.v, PC.o, PC.d, PC.poss, PC["rank"], PC.n)]
D["rw"] = {"rows": rw_rows, "n": rw_n, "src": "Chip Equity: 65% CEPM ridge regression + 35% lead margin, times share of competitive minutes"}
D["peak"] = {"ds": DS, "n": pn, "rows": prow}
# each player's best 2- to 5-year stretch by total, by offense and by defense, with the window's last season
D["peakx"] = {"cols": ["k", "w", "kind", "r", "o", "d", "end"], "rows": [[int(k), int(w), kind, round(r, 2), o, d, int(si)] for (k, w, kind), (_, r, o, d, si) in bestx.items()]}; D["cerm"] = cerm; D["ce"] = {"rows": [], "n": {}}; D["cepeak"] = {"ds": [], "n": [], "rows": []}
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
nm = D["names"]; print("rw rows", len(rw_rows), "| peaks", dict(zip(DS, pn)))
for j, name in enumerate(DS[:4]): print(name, ", ".join(f"{nm[r[0]]} {r[4]:+.2f}" for r in [x for x in prow if x[1] == j][:8]))
one = sorted([r for r in rw_rows if r[2] == 1 and r[1] > 0 and r[7] >= 1500], key=lambda r: -r[5]); seen = set(); top = []
for r in one:
    if r[0] in seen: continue
    seen.add(r[0]); top.append(f"{nm[r[0]]} {S[r[1]]} {r[5]:+.2f}")
    if len(top) == 10: break
print("best single seasons:", ", ".join(top))
