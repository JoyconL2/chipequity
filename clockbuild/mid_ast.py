"""Mid-range assists as their own input. Assists split three ways (rim / three / everything else = mostly mid-range),
each its own input, on top of clock relief. Then the same with the mid-range assist weight held at a floor (a share
of the rim-assist weight), to see what giving them real credit costs in accuracy."""
import os, contextlib, io, numpy as np, pandas as pd
R = "/home/claude/basketball-done-right"
F = pd.read_csv("/home/claude/features_v3b.csv")                      # current inputs + clock relief + o_tov_x_use, assists unsplit
F0 = pd.read_csv(f"{R}/mymodel/features_rs.csv")
F = F.merge(F0[["EntityId", "TeamId", "Season", "o_ast_rim", "o_ast_three"]], on=["EntityId", "TeamId", "Season"], how="left")
F["o_ast_mid"] = F.o_ast - F.o_ast_rim - F.o_ast_three
F = F.drop(columns=["o_ast", "o_tov_x_use"])
src = open(f"{R}/cepm/box_prior.py").read().split("# priors for every window")[0].replace('F = pd.read_csv("../mymodel/features_rs.csv")', "F = __F")
os.chdir(f"{R}/cepm"); ns = {"__name__": "bp", "__F": F}
with contextlib.redirect_stdout(io.StringIO()): exec(src, ns)
T, X, FE = ns["T"], ns["X"], ns["FEATS"]; jm, jr = FE.index("o_ast_mid"), FE.index("o_ast_rim")
def score(floor=None):
    eo = ed = tot = 0
    for e in sorted(T.e.unique()):
        m = ns["no_overlap"](e - 2, e); te = T.e.values == e; w = T.poss.values[te]
        co, io_, cd, idf = ns["fit"](m, ns["LAM"])
        if floor is not None:          # hold the mid-range assist offense weight at floor x rim weight, refit the rest
            fx = floor * co[jr]; keep = [i for i in range(len(FE)) if i != jm]
            y = T.o.values[m] - fx * X[m][:, jm]; c2, i2 = ns["ridge_fit"](X[m][:, keep], y, ns["W"][m], ns["LAM"])
            co = np.zeros(len(FE)); co[keep] = c2; co[jm] = fx; io_ = i2
        eo += np.sum(w * (T.o.values[te] - X[te] @ co - io_) ** 2); ed += np.sum(w * (T.d.values[te] - X[te] @ cd - idf) ** 2); tot += w.sum()
    return eo / tot, ed / tot
base = score(); c = ns["fit"](np.ones(len(T), bool), ns["LAM"])
print("assists as three separate inputs, learned weights (offense / defense per assist per 100):")
for f in ("o_ast_rim", "o_ast_three", "o_ast_mid"): i = FE.index(f); print(f"   {f:12s} {c[0][i]:+.3f} {c[2][i]:+.3f}")
print(f"offense error {base[0]:.4f} (clock-relief version with the old split: 1.3340)")
for fl in (0.25, 0.5, 0.75):
    s = score(fl); print(f"mid-range assist held at {fl:.0%} of a rim assist: offense error {s[0]:.4f} ({(s[0] - base[0]) / base[0] * 100:+.2f}% vs learned)")
