"""Chip Equity (v3, version A): the site's one impact stat (replaces CEPM in every display).
  Chip Equity = (0.60 x CEPM + 0.40 x LeadMargin) x (0.5 + 0.5 x CompShare)        (offense and defense the same way)
  CEPM       = the ridge regression (cepm/disp{w}.csv), points per 100 possessions on the floor
  LeadMargin = offense: his team's points scored vs league per 100 in the stints where he is the lead (best player on the
               floor, load/lead_map.py), shrunk x n/(n+K); defense: points allowed vs league, credited to the best defender on
               the floor by 3-year defensive rating (load/def_share.py), shrunk the same way, x n/(n+K)
               (1.1: was the lead's for both ends, with one shrink). Garbage time out.
  CompShare  = his share of his team's non-garbage minutes, in games he played. Only half of its gap from 1 counts
               (tested 1997-2026: better next-season player and team prediction than the full share)
LeadMargin also counts his playoff lead stints (one lead for both ends), each playoff possession worth 6 regular-season ones
(1.1; was 2), with the margin adjusted for the opponent: + the opponent team's regular-season offense/defense vs league
(load/po_lead.py).
Lead margin is also adjusted for teammates, offense and defense separately: the four teammates' 3-year o (or d), centred
by season, x 0.5 when they are above average and x 2.0 when below.
Playoff-only Chip Equity (pcepm) = (0.70 x playoff-only regression + 0.30 x opponent-adjusted playoff lead margin, offense
and defense each x n/(n+2000)) x (0.5 + 0.5 x playoff competitive share) (1.1; tested on next-postseason team results).
Single seasons are steadied 70% toward the 3-season window (first full window 1996-99 for the first two seasons), and the
single-season lead margin is shrunk with K = 6000 (window: 9000). Each season with playoffs then blends in playoff-only
Chip Equity: weight 0.2 x n/(n+500), n = his playoff possessions. (1.1, tested on next-season team prediction 1997-98..2025-26.)
2-5 year windows (only for players with a rated season in every year of the window) are the possession-weighted average of the single seasons in them, each steadied 20% (2-year
windows) or not at all (3-5 years).
Writes data.json rw (1-5 year rows), peak (best 2-5 year windows + decades), cerm (playoff model, regular season only)
and empties the old Chip Equity layer (ce, cepeak)."""
import json, numpy as np, pandas as pd
from decimal import Decimal, ROUND_HALF_UP
WL, B, K1, KS, MPO, KPO = 0.40, 0.7, 6000, 9000, 6.0, 2000
KD = 1.0                     # the defensive half of lead margin is shrunk with KD x the possessions of the offensive half
WLPO = 0.30                  # lead-margin weight in playoff-only Chip Equity
POB, POK = 0.2, 500          # playoff-only Chip Equity blended into each season with playoffs, by his playoff possessions
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}
ids = [int(x) for x in D["ids"]]; kOf = {p: k for k, p in enumerate(ids)}
M = pd.read_csv("margin_attr_od.csv"); LEAD = {(int(p), s): (n, o) for p, s, n, o in zip(M.p, M.season, M.lead_poss, M.lead_off)}
DSH = pd.read_csv("def_share.csv")          # defensive credit (best defender on the floor): possessions, defensive margin, teammates' 3-year defense
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
_g = DSH.assign(w=DSH.dtm * DSH.dposs).groupby("season"); _cdd = (_g.w.sum() / _g.dposs.sum()).to_dict()
DEF = {}
for p, s_, n_, d_, t_ in zip(DSH.p, DSH.season, DSH.dposs, DSH.dlead, DSH.dtm):
    ad = t_ - _cdd[s_]; DEF[(int(p), s_)] = (n_, d_ - bet(ad) * ad)
OFF = {}
for k_, (n_, o_) in LEAD.items():
    ao = TMA.get((k_[0], k_[1], "rs"), (0.0, 0.0))[0]; OFF[k_] = (n_, o_ - bet(ao) * ao)
# per player-season: (offensive lead possessions, offensive lead margin, defensive credit possessions, defensive margin)
LEAD = {k_: (*OFF.get(k_, (0.0, 0.0)), *DEF.get(k_, (0.0, 0.0))) for k_ in set(OFF) | set(DEF)}
for k_, q in POL.items():
    if q["n"] > 0:
        ao, ad = TMA.get((k_[0], k_[1], "po"), (0.0, 0.0)); bo, bd = bet(ao), bet(ad); q["lead_t"] -= bo * ao + bd * ad; q["off_t"] -= bo * ao; q["de_t"] -= bd * ad
C = pd.read_csv("comp_share.csv"); COMP = {(int(p), s): (a, b) for p, s, a, b in zip(C.p, C.season, C.comp, C.t_comp)}
def comps(p, seas, K, po_seas=None):
    no = so = nd = sd = ca = cb = 0.0
    for s in seas:
        v = LEAD.get((p, s)); c = COMP.get((p, s))
        if v:
            if v[0] > 0: no += v[0]; so += v[0] * v[1]
            if v[2] > 0: nd += v[2]; sd += v[2] * v[3]
        if c: ca += c[0]; cb += c[1]
    if cb <= 0: return None
    for s in (seas if po_seas is None else po_seas):      # playoff lead stints (one lead for both ends), opponent-adjusted, x MPO
        q = POL.get((p, s))
        if q and q["n"] > 0: w = MPO * q["n"]; no += w; so += w * q["off_t"]; nd += w; sd += w * q["de_t"]
    lo = so / (no + K) if no + K > 0 else 0.0; ld = sd / (nd + K * KD) if nd + K * KD > 0 else 0.0
    return lo + ld, lo, ld, ca / cb
disp = {w: pd.read_csv(f"../cepm/disp{w}.csv") for w in (1, 2, 3, 4, 5)}
c3 = disp[3]; C3 = {(int(p), s): (r, o, d) for p, s, r, o, d in zip(c3.player, c3.window_end, c3.rapm, c3.o_rapm, c3.d_rapm)}
SOFT = lambda sh: 0.5 + 0.5 * sh          # half the minutes-share penalty
def po_lead(q):
    """playoff-only lead margin, offense and defense shrunk separately (defense with KD x the possessions)"""
    if not q or q["n"] <= 0: return 0.0, 0.0
    return q["off_t"] * q["n"] / (q["n"] + KPO), q["de_t"] * q["n"] / (q["n"] + KPO * KD)
# playoff-only Chip Equity per player-season (same formula as the pcepm rows below), for the playoff blend
PCV = {}
for k_, si_, v_, o_, d_, poss_, rank_, n_ in json.load(open("pcepm_raw.json")):
    q_ = POL.get((ids[k_], S[si_])); sh_ = q_["po_share"] if q_ and np.isfinite(q_["po_share"]) else 0.6
    lo_, ld_ = po_lead(q_); sh_ = SOFT(sh_)
    PCV[(ids[k_], si_)] = (((1 - WLPO) * v_ + WLPO * (lo_ + ld_)) * sh_, ((1 - WLPO) * o_ + WLPO * lo_) * sh_, ((1 - WLPO) * d_ + WLPO * ld_) * sh_, poss_)
def value(p, si, w, r, o, d, b=None):
    seas = [S[x] for x in range(max(0, si - w + 1), si + 1)]; c = comps(p, seas, K1)
    if c is None: return None
    ln, lo, ld, sh = c
    if w == 1:
        j = max(si, 2); rr = C3.get((p, S[j]), (r, o, d)); x = comps(p, [S[t] for t in range(j - 2, j + 1)], KS)
        Bw = B if b is None else b
        r, o, d = [(1 - Bw) * a + Bw * c_ for a, c_ in zip((r, o, d), rr)]
        if x: ln, lo, ld = [(1 - Bw) * a + Bw * c_ for a, c_ in zip((ln, lo, ld), x[:3])]
    f = lambda cep, lead: ((1 - WL) * cep + WL * lead) * SOFT(sh)
    out = (f(r, ln), f(o, lo), f(d, ld))
    pc = PCV.get((p, si)) if w == 1 else None
    if pc:
        a = POB * pc[3] / (pc[3] + POK); out = tuple((1 - a) * x + a * y for x, y in zip(out, pc[:3]))
    return out
def split(r, o, d):
    """Offense/defense scaled to add up to the total: the gap between the total fit and the split fit is shared in
    proportion to |o| and |d|, then rounded so the 1-decimal numbers on the site add up exactly."""
    gap = r - (o + d); a, b = abs(o), abs(d); t = a + b
    o += gap * (a / t if t else 0.5); d += gap * (b / t if t else 0.5)
    O1 = round(o, 1); R1 = float(Decimal(round(r, 2)).quantize(Decimal("0.1"), ROUND_HALF_UP))   # how the site shows the stored total (JS toFixed)
    return O1, round(R1 - O1, 1)
MINP = {2: 3000, 3: 4500, 4: 6000, 5: 7500}
rw_rows, rw_n, best, bestx = [], {}, {}, {}   # bestx: (k, w, kind) -> best window by total (0) / offense (1) / defense (2)
# Multi-year windows = the possession-weighted average of his steadied single seasons in the window, so a window
# can never rate higher than his best season in it (a pooled fit, unsteadied, could).
# Each season in a window is steadied less than a lone season (40%), since the window average already smooths it:
# 20% inside a 2-year window, none inside 3-5 year windows (tested 1997-2026 on next-season prediction).
WIN_B = {1: B, 2: 0.2, 3: 0.0, 4: 0.0, 5: 0.0}
SVB = {b_: {} for b_ in set(WIN_B.values())}
d1_ = disp[1]
for p, r, o, dd, we, poss in zip(d1_.player, d1_.rapm, d1_.o_rapm, d1_.d_rapm, d1_.window_end, d1_.poss):
    si = SI.get(we)
    if si is None or kOf.get(int(p)) is None: continue
    for b_ in SVB:
        v = value(int(p), si, 1, r, o, dd, b_)
        if v is not None: SVB[b_][(int(p), si)] = (*v, float(poss))
SV = SVB[B]
def window_value(p, si, w):
    sv = SVB[WIN_B[w]]
    if si - w + 1 < 0: return None
    xs = [sv[(p, t)] for t in range(si - w + 1, si + 1) if (p, t) in sv]
    if len(xs) < w: return None          # a w-year window needs a rated season in every one of its w years
    tot = sum(x[3] for x in xs)
    if not xs or tot <= 0: return None
    return tuple(sum(x[j] * x[3] for x in xs) / tot for j in range(3))
for w in sorted(disp):
    d = disp[w]
    out = []
    for p, r, o, dd, we, poss in zip(d.player, d.rapm, d.o_rapm, d.d_rapm, d.window_end, d.poss):
        p = int(p); k = kOf.get(p); si = SI.get(we)
        if k is None or si is None: continue
        v = SV[(p, si)][:3] if w == 1 and (p, si) in SV else window_value(p, si, w) if w > 1 else None
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
            if c: sh_ = SOFT(c[3]); items.append((((1 - WL) * r + WL * c[0]) * sh_, k, (((1 - WL) * r + WL * c[0]) * sh_, ((1 - WL) * o + WL * c[1]) * sh_, ((1 - WL) * de + WL * c[2]) * sh_)))
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
    lo, ld = po_lead(q); sh = SOFT(sh)
    pc.append([k, si, ((1 - WLPO) * v + WLPO * (lo + ld)) * sh, ((1 - WLPO) * o + WLPO * lo) * sh, ((1 - WLPO) * d + WLPO * ld) * sh, poss, n])
PC = pd.DataFrame(pc, columns=["k", "si", "v", "o", "d", "poss", "n"]); PC["rank"] = PC.groupby("si").v.rank(ascending=False, method="min").astype(int)
D["pcepm"] = [[int(a), int(b), round(c, 2), *split(c, e, f_), int(g_), int(h), int(i)] for a, b, c, e, f_, g_, h, i in zip(PC.k, PC.si, PC.v, PC.o, PC.d, PC.poss, PC["rank"], PC.n)]
D["rw"] = {"rows": rw_rows, "n": rw_n, "src": "Chip Equity: 60% CEPM ridge regression + 40% lead margin (defense to the best defender on the floor), times (0.5 + 0.5 x share of competitive minutes); seasons with playoffs blend in playoff-only Chip Equity"}
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
