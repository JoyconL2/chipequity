"""Does possession timing help the box component? Adds late-clock / early-clock features to the box prior's inputs and
reruns its own leave-seasons-out check (cepm/box_prior.py), with and without them.
  o_late_fga         late-clock attempts per 100 offensive possessions
  o_late_pts_added   late-clock points above what the league scores on that many late-clock shots, per 100
  o_early_fga        early (transition) attempts per 100
  o_early_pts_added  early points above the league's early-shot average, per 100
All relative to the season's league average, like the other inputs."""
import glob, os, sys, numpy as np, pandas as pd
R = "/home/claude/basketball-done-right"
C = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("/home/claude/clockout/clock_*.csv"))])
lg = C.groupby("season")[["late_fga", "late_pts", "early_fga", "early_pts"]].sum()
lg["late_ppa"] = lg.late_pts / lg.late_fga; lg["early_ppa"] = lg.early_pts / lg.early_fga
C = C.join(lg[["late_ppa", "early_ppa"]], on="season")
F0 = pd.read_csv(f"{R}/mymodel/features_rs.csv")
F = F0.merge(C.rename(columns={"player_id": "EntityId", "team_id": "TeamId", "season": "Season"}), on=["EntityId", "TeamId", "Season"], how="left")
op = F.OffPoss.clip(lower=1)
F["o_late_fga"] = F.late_fga / op * 100; F["o_late_pts_added"] = (F.late_pts - F.late_ppa * F.late_fga) / op * 100
F["o_early_fga"] = F.early_fga / op * 100; F["o_early_pts_added"] = (F.early_pts - F.early_ppa * F.early_fga) / op * 100
NEW = ["o_late_fga", "o_late_pts_added", "o_early_fga", "o_early_pts_added"]
w = (F.OffPoss + F.DefPoss).clip(lower=1) / 2
for c in NEW:
    F[c] = F[c].fillna(np.nan)
    m = (F[c].fillna(0) * w).groupby(F.Season).transform("sum") / w.where(F[c].notna(), 0).groupby(F.Season).transform("sum")
    F[c] = (F[c] - m).fillna(0)
cov = F[F.late_fga.notna()].Season.nunique(); print(f"clock data for {cov} seasons; matched {F.late_fga.notna().mean():.1%} of player-team-season rows")
src = open(f"{R}/cepm/box_prior.py").read().split("# priors for every window")[0]
def run(cols_drop, label):
    G = F.drop(columns=[c for c in cols_drop]) if cols_drop else F
    os.chdir(f"{R}/cepm"); ns = {"__name__": "bp"}
    code = src.replace('F = pd.read_csv("../mymodel/features_rs.csv")', "F = __F")
    ns["__F"] = G[[c for c in G.columns if c in F0.columns or c in NEW]]
    print(f"--- {label}"); exec(code, ns); return ns
base = run(NEW, "current inputs")
new = run(None, "with possession timing")
co, io, cd, idf = new["fit"](np.ones(len(new["T"]), bool), new["LAM"])
print("weights on the new inputs (offense / defense, per 100):")
for f, a, b in zip(new["FEATS"], co, cd):
    if f in NEW: print(f"  {f:18s} {a:+.3f} {b:+.3f}")

# who moves: one-season box estimate (offense) with each model fit on everything
import json, lzma
D = json.load(lzma.open(f"{R}/base/data.json.xz")); name = {int(i): n for i, n in zip(D["ids"], D["names"])}; byname = {v: k for k, v in name.items()}
fb = base["fit"](np.ones(len(base["T"]), bool), base["LAM"]); fn = new["fit"](np.ones(len(new["T"]), bool), new["LAM"])
show = [("LeBron James", "2008-09"), ("LeBron James", "2009-10"), ("LeBron James", "2012-13"), ("LeBron James", "2016-17"), ("Stephen Curry", "2015-16"), ("Stephen Curry", "2016-17"),
        ("Nikola Jokic", "2023-24"), ("Kobe Bryant", "2005-06"), ("James Harden", "2018-19"), ("Kevin Durant", "2013-14"), ("Chris Paul", "2014-15"), ("Kawhi Leonard", "2018-19"),
        ("Dirk Nowitzki", "2010-11"), ("Shai Gilgeous-Alexander", "2024-25"), ("Russell Westbrook", "2016-17"), ("Giannis Antetokounmpo", "2019-20")]
rows = []
for n, s in show:
    p = byname.get(n) or next((k for k, v in name.items() if v.replace("ć", "c").replace("č", "c") == n), None)
    if p is None: continue
    xb = base["window_feats"]([p], s, 1).get(p); xn = new["window_feats"]([p], s, 1).get(p)
    if xb is None or xn is None: continue
    ob, on_ = xb[0] @ fb[0] + fb[1], xn[0] @ fn[0] + fn[1]; db, dn = xb[0] @ fb[2] + fb[3], xn[0] @ fn[2] + fn[3]
    rows.append((n, s, ob, on_, db, dn))
print("box estimate, one season (offense before -> after | defense before -> after):")
for n, s, ob, on_, db, dn in rows: print(f"  {n:24s} {s}  O {ob:+.2f} -> {on_:+.2f} ({on_ - ob:+.2f})   D {db:+.2f} -> {dn:+.2f} ({dn - db:+.2f})")

# offense-only variant: new inputs feed the offense model only; defense keeps the current inputs
T, X0, Xn = base["T"], base["X"], new["X"]
for lam in (30, 100):
    err_b = err_n = err_o = 0; tot = 0
    for e in sorted(T.e.unique()):
        m = base["no_overlap"](e - 2, e); te = T.e.values == e; w = T.poss.values[te]
        cb = base["fit"](m, lam); cn = new["fit"](m, lam)
        ob, db = X0[te] @ cb[0] + cb[1], X0[te] @ cb[2] + cb[3]; on_, dn = Xn[te] @ cn[0] + cn[1], Xn[te] @ cn[2] + cn[3]
        yo, yd = T.o.values[te], T.d.values[te]
        err_b += np.sum(w * ((yo - ob) ** 2 + (yd - db) ** 2)); err_n += np.sum(w * ((yo - on_) ** 2 + (yd - dn) ** 2)); err_o += np.sum(w * ((yo - on_) ** 2 + (yd - db) ** 2)); tot += w.sum()
    print(f"lambda {lam}: current {err_b / tot:.4f} | timing both sides {err_n / tot:.4f} | timing offense only {err_o / tot:.4f}")
