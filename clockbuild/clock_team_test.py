"""Clock usage and offense across all seasons.
  1 team: within each season, how a team's offense (points per 100 vs league) relates to its shot-timing mix
  2 players: 'clock relief' = how his team's shot mix changes with him on vs off; does it predict his offensive
    lineup rating (3-year RAPM, the box component's target) beyond his own box score? Same leave-seasons-out check."""
import glob, os, json, lzma, numpy as np, pandas as pd
R = "/home/claude/basketball-done-right"
T = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("/home/claude/clockteam/team_*.csv"))])
n = T[[c for c in T if c.startswith("n_")]].sum(axis=1)
for b in ("early", "hc_early", "hc_mid", "late", "putback"): T[f"sh_{b}"] = T[f"n_{b}"] / n
T["ortg_rel"] = T.ortg - T.groupby("season").ortg.transform("mean")
for c in [c for c in T if c.startswith("sh_")]: T[c + "_rel"] = (T[c] - T.groupby("season")[c].transform("mean")) * 100      # percentage points vs league that year
X = T[["sh_early_rel", "sh_hc_early_rel", "sh_late_rel", "sh_putback_rel"]].values; y = T.ortg_rel.values
b = np.linalg.lstsq(np.c_[np.ones(len(X)), X], y, rcond=None)[0]; r2 = 1 - np.sum((y - np.c_[np.ones(len(X)), X] @ b) ** 2) / np.sum((y - y.mean()) ** 2)
print(f"1  TEAMS ({len(T)} team-seasons, {T.season.nunique()} seasons): shot-timing mix explains {r2:.0%} of the gaps between offenses")
for lab, v in zip(["transition", "half court 10+ s", "late clock", "putbacks"], b[1:]): print(f"   +1 point of shots that are {lab:17s} -> {v:+.2f} points per 100 (other mix held equal; the rest is 7-10 s / other)")
for c, lab in (("sh_late_rel", "late clock"), ("sh_early_rel", "transition"), ("sh_hc_early_rel", "half court 10+ s")):
    print(f"   correlation with offense, {lab:17s}: {np.corrcoef(T[c], T.ortg_rel)[0, 1]:+.2f}")
O = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("/home/claude/clockteam/onoff_*.csv"))])
for b_ in ("late", "early", "hc_early"): O[f"relief_{b_}"] = (O[f"share_on_{b_}"] - O[f"share_off_{b_}"]) * 100
O["w"] = 1 / (1 / O.shots_on + 1 / O.shots_off)
A = O.groupby(["pid", "season"]).apply(lambda g: pd.Series({c: np.average(g[c], weights=g.w) for c in ("relief_late", "relief_early", "relief_hc_early")} | {"w": g.w.sum()}), include_groups=False).reset_index()
# year-to-year: is clock relief a stable trait?
A["y"] = A.season.str[:4].astype(int); M = A.merge(A.assign(y=A.y - 1), on=["pid", "y"], suffixes=("", "_n"))
print(f"\n2  PLAYERS ({len(A)} player-seasons)")
for c, lab in (("relief_late", "late-clock share"), ("relief_early", "transition share"), ("relief_hc_early", "half court 10+ s share")):
    print(f"   change in team {lab:24s} with him on: year-to-year r {np.corrcoef(M[c], M[c + '_n'])[0, 1]:.2f}")
# box component test: add clock relief to the offense inputs
F0 = pd.read_csv(f"{R}/mymodel/features_rs.csv")
F = F0.merge(A.rename(columns={"pid": "EntityId", "season": "Season"})[["EntityId", "Season", "relief_late", "relief_early", "relief_hc_early"]], on=["EntityId", "Season"], how="left")
NEW = ["o_relief_late", "o_relief_early", "o_relief_hc_early"]
for c, src in zip(NEW, ("relief_late", "relief_early", "relief_hc_early")): F[c] = F[src].fillna(0)
src = open(f"{R}/cepm/box_prior.py").read().split("# priors for every window")[0]
def run(G, label):
    os.chdir(f"{R}/cepm"); ns = {"__name__": "bp", "__F": G}; print(f"--- {label}"); exec(src.replace('F = pd.read_csv("../mymodel/features_rs.csv")', "F = __F"), ns); return ns
base = run(F0, "current inputs"); new = run(F[[c for c in F.columns if c in F0.columns or c in NEW]], "with clock relief")
Tt, X0, Xn = base["T"], base["X"], new["X"]
for lam in (30,):
    eb = eo = tot = 0
    for e in sorted(Tt.e.unique()):
        m = base["no_overlap"](e - 2, e); te = Tt.e.values == e; w = Tt.poss.values[te]
        cb = base["fit"](m, lam); cn = new["fit"](m, lam)
        eb += np.sum(w * ((Tt.o.values[te] - X0[te] @ cb[0] - cb[1]) ** 2)); eo += np.sum(w * ((Tt.o.values[te] - Xn[te] @ cn[0] - cn[1]) ** 2)); tot += w.sum()
    print(f"   OFFENSE only: current {eb / tot:.4f} -> with clock relief {eo / tot:.4f} ({(eo - eb) / eb * 100:+.1f}%)")
co = new["fit"](np.ones(len(Tt), bool), new["LAM"])[0]
for f, a in zip(new["FEATS"], co):
    if f in NEW: print(f"   weight {f:20s} {a:+.3f} offense per 100 for each point of shot share")
