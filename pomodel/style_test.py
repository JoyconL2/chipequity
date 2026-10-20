"""Style matchups in the playoff series model. Base = the site's model (net, top-3, availability, luck), tested
leave-one-season-out on all 450 series. Each style term is a clash: A's tendency (vs league) x B's matching weakness
(vs league), minus the same for B against A, so it's antisymmetric like everything else in the model."""
import os, json, numpy as np, pandas as pd
os.environ.setdefault("CERMF", "cerm_built.json")
src = open("ce_playoffs_alpha.py").read(); exec(src[:src.index("import builtins")])
T = pd.DataFrame(D["T"]); T = T[T.t == 0].copy(); T["tid"] = [int(D["teamIds"][a]) for a in T.a]
T["fga"] = T.fg2a + T.fg3a; T["poss"] = T.op
T["r3"] = T.fg3a / T.fga; T["ftr"] = T.fta / T.fga; T["tovr"] = T.tov / T.poss; T["stlr"] = T.stl / T.dp; T["blkr"] = T.blk / T.dp; T["sfr"] = T.sf / T.dp
for c in ("r3", "ftr", "tovr", "stlr", "blkr", "sfr", "oreb", "dreb", "rim", "pace"):
    T[c + "_z"] = T.groupby("s")[c].transform(lambda x: (x - x.mean()) / (x.std() + 1e-9))
def trow(si, tid, net):
    c = T[(T.s == si) & (T.tid == tid)]
    if len(c) > 1: c = c.iloc[[np.argmin([abs(100 * r.pts / r.op - 100 * r.opp / r.dp - net) for r in c.itertuples()])]]
    return c.iloc[0] if len(c) else None
R = {}
for side in "AB":
    tm = [team_of(s, n) for s, n in zip(X.s, X[f"net{side}"])]
    R[side] = [trow(t[3], t[1], t[0]) for t in tm]
def fz(side, c): return np.array([r[c + "_z"] if r is not None else 0.0 for r in R[side]])
clash = {   # (attacker tendency, defender weakness sign)
    "reb": ("oreb", "dreb", -1),      # A crashes the glass, B defends the glass badly
    "tov": ("tovr", "stlr", +1),      # A turns it over, B forces turnovers  (bad for A -> sign flipped below)
    "rim": ("rim", "blkr", -1),       # A attacks the rim, B doesn't protect it
    "ftd": ("ftr", "sfr", +1),        # A draws fouls, B fouls a lot
}
for name, (a_c, d_c, sg) in clash.items():
    X[f"{name}A"] = fz("A", a_c) * sg * fz("B", d_c); X[f"{name}B"] = fz("B", a_c) * sg * fz("A", d_c)
X["tovA"], X["tovB"] = -X.tovA, -X.tovB
X["paceA"], X["paceB"] = X.paceA, X.paceB          # (kept for the pace scaling in design())
X["slowA"], X["slowB"] = -fz("A", "pace"), -fz("B", "pace")       # do slower teams gain in the playoffs?
X["r3A"], X["r3B"] = fz("A", "r3"), fz("B", "r3")                  # do three-heavy teams under/over-perform?
base = ["net", "t3v2", "avail", "luck"]
evaluate(base, "base (live model)")
for extra in (["reb"], ["tov"], ["rim"], ["ftd"], ["slow"], ["r3"], ["reb", "tov", "rim", "ftd"], ["reb", "tov", "rim", "ftd", "slow", "r3"]):
    evaluate(base + extra, "base + " + "+".join(extra))
