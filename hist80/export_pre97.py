"""Chip Equity v1 for 1979-80..1995-96 -> dist/pre97.json (the site's "1980-96" page, loaded when it opens).

Inputs (local, not in git): v1_rs_all.csv / v1_po_all.csv (v1 regular-season and playoff estimates, every era) and
box80.csv (teams). Regular season gets the light playoff weighting:
    new = v1 + 0.5 x delta x n / (n + 1000),  delta = playoff v1 - what his season v1 predicts for n playoff possessions
(expected playoff value = b x season value x n / (n + K0), fit on all eras). Offense and defense are moved the same way,
so they still add up to the total. The file is static: these seasons never change."""
import json, os
import numpy as np, pandas as pd
from scipy.optimize import curve_fit

H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "..", "dist", "pre97.json")
rs = pd.read_csv(os.path.join(H, "v1_rs_all.csv")); po = pd.read_csv(os.path.join(H, "v1_po_all.csv"))
m = rs.merge(po[["pid", "season", "on", "r", "o", "d"]].rename(columns={"on": "pn", "r": "pr", "o": "po", "d": "pd"}), on=["pid", "season"], how="left")
f = lambda z, b, K0: b * z[0] * z[1] / (z[1] + K0); ok = m.pr.notna()
(b, K0), _ = curve_fit(f, np.vstack([m[ok].r, m[ok].pn]), m[ok].pr, p0=[0.8, 500])
m["pn"] = m.pn.fillna(0); g = 0.5 * m.pn / (m.pn + 1000)
for side, ps in (("o", "po"), ("d", "pd")):
    m["L" + side] = m[side] + g * (m[ps] - f(np.vstack([m[side], m.pn]), b, K0)).fillna(0)
m["L"] = m.Lo + m.Ld
m = m[m.season < "1996-97"]; po = po[po.season < "1996-97"]
# team: the one he played the most regular-season minutes for
B = pd.read_csv(os.path.join(H, "box80.csv")); B = B[B.t == 0].sort_values("min", ascending=False).drop_duplicates(["p", "season"])
FIX = {"GOS": "GSW", "PHL": "PHI", "SAN": "SAS", "UTH": "UTA"}
tm = {(int(p), s): FIX.get(t, t) for p, s, t in zip(B.p, B.season, B.TEAM_ABBREVIATION)}
r2 = lambda x: round(float(x), 2)
out = {"note": "Chip Equity v1 (box-score estimate), 1979-80..1995-96; regular season with the light playoff weighting",
       "fit": {"b": r2(b), "K0": round(float(K0))},
       "cols": ["pid", "name", "season", "team", "mpg", "poss", "off", "def", "total", "before"],
       "rs": [[int(x.pid), x.name, x.season, tm.get((int(x.pid), x.season), ""), round(float(x.mpg), 1), int(round(x.on)), r2(x.Lo), r2(x.Ld), r2(x.L), r2(x.r)]
              for x in m.sort_values("L", ascending=False).itertuples()],
       "pcols": ["pid", "name", "season", "team", "gp", "poss", "off", "def", "total"],
       "po": [[int(x.pid), x.name, x.season, tm.get((int(x.pid), x.season), ""), int(x.gp), int(round(x.on)), r2(x.o), r2(x.d), r2(x.r)]
              for x in po.sort_values("r", ascending=False).itertuples()]}
json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print(f"wrote {OUT}: {len(out['rs'])} seasons, {len(out['po'])} playoff runs; fit b={b:.2f} K0={K0:.0f}")
print("top:", [(r[1], r[2], r[8]) for r in out["rs"][:6]])
