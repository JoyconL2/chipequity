"""Does Chip Equity predict playoff series better than CEPM?  Same leave-one-season-out test as fit2.py (450 series,
1996-97 to 2025-26). The site's model: net + top-3 + availability + luck. 'top-3' = the three biggest
(3-year regular-season-only CEPM x share of the team's floor time). Variants swap CEPM for Chip Equity (CEPM x load,
load over the same 3 regular seasons, so nothing comes from the playoffs being predicted)."""
import json, numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm
src = open("fit.py").read()
exec(src[src.index("def series_pv"):src.index('if __name__ == "__main__":')].replace("def evaluate(cols, label):", "def evaluate(cols, label, quiet=False):"))
L0 = open("../load/ce_build.py").read(); exec(L0[L0.index("D = json.load"):L0.index("rows, n = [], {}")].replace('"../site/data.json"', '"../site/data.json"'))
X = pd.DataFrame(json.load(open("series2.json"))); X = X[(X.s >= "2000-01") & (X.s <= "2024-25")].reset_index(drop=True)
T = D["T"]; tnet = {}
for a, s_, t, pts, opp, op, dp, gp in zip(T["a"], T["s"], T["t"], T["pts"], T["opp"], T["op"], T["dp"], T["gp"]):
    if t == 0 and pts is not None: tnet.setdefault(S[s_], []).append((100 * pts / op - 100 * opp / dp, int(D["teamIds"][a]), gp, s_))
DIFF = []
def team_of(season, net):
    c = min(tnet[season], key=lambda x: abs(x[0] - net)); DIFF.append(abs(c[0] - net)); return c
PG = pd.read_csv("player_game.csv", dtype={"game_id": str}); PG = PG[PG.stype == "rs"]
fix = {1610612766: 1610612740, 1610612740: 1610612766}
sec = PG.groupby(["season", "team", "p"]).secs.sum()
CE3 = pd.read_csv("../cepm/cepm3_rs.csv"); r3c = {(int(p), s): r for p, s, r in zip(CE3.player, CE3.window_end, CE3.rapm)}
FC = pd.read_csv("../factors/factor_cepm.csv"); FC = FC[FC.w == 3]; f3 = {(int(p), s): v for p, s, v in zip(FC.player, FC.window_end, FC.fcepm)}
import os; MODE = os.environ.get("RV", "cepm")
r3 = {k: (v if MODE == "cepm" else (f3[k] if MODE == "fac" else (v + f3[k]) / 2)) for k, v in r3c.items() if k in f3}
def roles(k, s):
    a = np.zeros(10); got = False
    for x in range(s - 2, s + 1):
        r = GI.get((k, x))
        if r is not None: a += np.array(r[2:], float); got = True
    if not got: return None
    secs, gp, pos, upos, ob, stsec, ssec, lu, lob, lst = a
    if gp == 0 or pos == 0: return None
    ur, obr = cl(upos / lu), cl(ob / lob); sr = cl((stsec / ssec) / (lst / ssec)) if ssec > 0 else 1.0
    return secs / 60 / gp / 48, 1.0
def top3(season, tid, gp, si, mode):
    try: g = sec.loc[(season, tid)]
    except KeyError: g = sec.loc[(season, fix.get(tid, tid))]
    team_sec = gp * 48 * 60; vals = []
    for p, sc in g.items():
        if sc < 300 * 60 or (int(p), season) not in r3: continue
        v = r3[(int(p), season)]; floor = min(1, sc / team_sec); k = kOf.get(int(p)); rl = roles(k, si) if k is not None else None
        mpg_load, role = rl if rl else (None, 1.0)
        if mode == "cepm": x = v * floor
        elif mode == "ce": x = v * (mpg_load * role if rl else floor)      # Chip Equity: CEPM x load over the 3-yr window
        elif mode == "ce_floor": x = v * floor * role                       # this season's floor share x role
        vals.append(x)
    return sum(sorted(vals, reverse=True)[:3]) if vals else np.nan
for side in "AB":
    tm = [team_of(s, n) for s, n in zip(X.s, X[f"net{side}"])]
    for mode in ("cepm", "ce", "ce_floor"):
        X[f"t3{mode}{side}"] = [top3(s, t[1], t[2], t[3], mode) for s, t in zip(X.s, tm)]
print("team match: max net diff", round(max(DIFF), 3), "| over 0.5:", sum(d > 0.5 for d in DIFF))
print("check: recomputed top-3 vs stored, max diff", float((X.t3cepmA - X.t3A).abs().max()))
import builtins
for cols, lab in ((["net", "t3ce", "avail", "luck"], f"net + top-3 Chip Equity [{MODE}] + availability + luck"), (["net", "t3ce"], f"net + top-3 Chip Equity [{MODE}]")):
    evaluate(cols, lab)
