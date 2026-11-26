"""Box component variants, each scored with box_prior.py's own leave-seasons-out check (error vs 3-year RAPM):
  V0 current inputs
  V1 + clock relief (team shot-timing with him on vs off)
  V2 V1 with one assist input (every assist type gets the same credit)
  V3 V2 + turnovers weighed by on-ball load: turnovers x usage and turnovers x assists (centered per season)
  V4 V2 + turnovers per possession used (turnovers / (shots + 0.44 FTA + assists + turnovers)), centered per season"""
import glob, os, json, numpy as np, pandas as pd
R = "/home/claude/basketball-done-right"
h = open(f"{R}/dist/index.html").read(); i = h.index('const DATA = JSON.parse(') + 24; D = json.loads(json.JSONDecoder().raw_decode(h[i:])[0])
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "pos", "fg2a", "fg3a", "fta", "tov", "ast")}); P = P[P.t == 0]
P = P.groupby(["p", "s"], as_index=False).sum(numeric_only=True); P["EntityId"] = P.p.map(lambda k: int(D["ids"][k])); P["Season"] = P.s.map(lambda s: D["seasons"][s])
use = P.fg2a + P.fg3a + 0.44 * P.fta + P.ast + P.tov; pos = P.pos.clip(lower=1)
P["use100"] = (P.fg2a + P.fg3a + 0.44 * P.fta + P.tov) / pos * 100; P["ast100"] = P.ast / pos * 100; P["tov100"] = P.tov / pos * 100; P["tov_per_use"] = P.tov / use.clip(lower=1) * 100
for c in ("use100", "ast100", "tov100", "tov_per_use"): P[c] = P[c] - P.groupby("Season")[c].transform(lambda x: np.average(x, weights=P.loc[x.index, "pos"]))
P["o_tov_x_use"] = P.tov100 * P.use100 / 10; P["o_tov_x_ast"] = P.tov100 * P.ast100 / 10; P["o_tov_per_use"] = P.tov_per_use
O = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("/home/claude/clockteam/onoff_*.csv"))])
for b in ("late", "early", "hc_early"): O[f"o_relief_{b}"] = (O[f"share_on_{b}"] - O[f"share_off_{b}"]) * 100
O["w"] = 1 / (1 / O.shots_on + 1 / O.shots_off)
A = O.groupby(["pid", "season"]).apply(lambda g: pd.Series({c: np.average(g[c], weights=g.w) for c in ("o_relief_late", "o_relief_early", "o_relief_hc_early")}), include_groups=False).reset_index().rename(columns={"pid": "EntityId", "season": "Season"})
F0 = pd.read_csv(f"{R}/mymodel/features_rs.csv")
F = F0.merge(A, on=["EntityId", "Season"], how="left").merge(P[["EntityId", "Season", "o_tov_x_use", "o_tov_x_ast", "o_tov_per_use"]], on=["EntityId", "Season"], how="left")
EXTRA = ["o_relief_late", "o_relief_early", "o_relief_hc_early", "o_tov_x_use", "o_tov_x_ast", "o_tov_per_use"]
for c in EXTRA: F[c] = F[c].fillna(0)
src = open(f"{R}/cepm/box_prior.py").read().split("# priors for every window")[0].replace('F = pd.read_csv("../mymodel/features_rs.csv")', "F = __F")
def run(cols, drop=()):
    keep = [c for c in F0.columns if c not in drop] + list(cols); os.chdir(f"{R}/cepm"); ns = {"__name__": "bp", "__F": F[keep]}
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()): exec(src, ns)
    T, X = ns["T"], ns["X"]; eo = ed = tot = 0
    for e in sorted(T.e.unique()):
        m = ns["no_overlap"](e - 2, e); te = T.e.values == e; w = T.poss.values[te]; c = ns["fit"](m, ns["LAM"])
        eo += np.sum(w * (T.o.values[te] - X[te] @ c[0] - c[1]) ** 2); ed += np.sum(w * (T.d.values[te] - X[te] @ c[2] - c[3]) ** 2); tot += w.sum()
    return eo / tot, ed / tot, ns
CL = ["o_relief_late", "o_relief_early", "o_relief_hc_early"]; AS = ("o_ast_rim", "o_ast_three")
V = {"V0 current": run([]), "V1 + clock relief": run(CL), "V2 V1, one assist input": run(CL, AS),
     "V3 V2 + turnovers x usage / x assists": run(CL + ["o_tov_x_use", "o_tov_x_ast"], AS), "V4 V2 + turnovers per possession used": run(CL + ["o_tov_per_use"], AS)}
b = V["V0 current"]
print(f"{'variant':40s} {'offense':>8s} {'defense':>8s} {'total':>8s}   vs current")
for k, (eo, ed, ns) in V.items(): print(f"{k:40s} {eo:8.4f} {ed:8.4f} {eo + ed:8.4f}   off {(eo - b[0]) / b[0] * 100:+.1f}%  def {(ed - b[1]) / b[1] * 100:+.1f}%  total {(eo + ed - b[0] - b[1]) / (b[0] + b[1]) * 100:+.1f}%")
for k in ("V2 V1, one assist input", "V3 V2 + turnovers x usage / x assists", "V4 V2 + turnovers per possession used"):
    ns = V[k][2]; c = ns["fit"](np.ones(len(ns["T"]), bool), ns["LAM"])
    print(f"\n{k}: weights (offense / defense)"); [print(f"   {f:18s} {a:+.3f} {d:+.3f}") for f, a, d in zip(ns["FEATS"], c[0], c[2]) if "ast" in f or "tov" in f]

eo, ed, ns = run(CL + ["o_tov_x_use"], AS); print(f"\nV3b V2 + turnovers x usage only: total {(eo + ed - b[0] - b[1]) / (b[0] + b[1]) * 100:+.2f}% (off {(eo - b[0]) / b[0] * 100:+.1f}%, def {(ed - b[1]) / b[1] * 100:+.1f}%)")
c = ns["fit"](np.ones(len(ns["T"]), bool), ns["LAM"]); [print(f"   {f:18s} {a:+.3f} {d:+.3f}") for f, a, d in zip(ns["FEATS"], c[0], c[2]) if "ast" in f or "tov" in f]
F[[c for c in F0.columns if c not in AS] + CL + ["o_tov_x_use"]].to_csv("/home/claude/features_v3b.csv", index=False)
