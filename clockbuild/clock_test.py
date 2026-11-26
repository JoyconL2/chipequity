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
