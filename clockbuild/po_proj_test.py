"""Does regular-season early half-court efficiency help predict playoff Chip Equity beyond the regular-season rating?
Target: each player's playoff Chip Equity (site values, runs with 300+ playoff possessions), weighted by possessions.
Base: his regular-season 1-year Chip Equity. Added one at a time: his regular-season efficiency (points per shot above
league, shrunk toward 0 by shots/(shots+300)) on all shots / half court / half court with 10+ s left / transition / late clock.
Scored leave-one-season-out: error on each season from a fit on all the others."""
import json, glob, numpy as np, pandas as pd
P = pd.DataFrame(json.load(open("/tmp/claude-0/-home-claude/d45461d2-6819-5ccf-a7df-ceffda37ed81/scratchpad/po_ce.json")))
P = P[(P.po_poss >= 300) & P.rs_r.notna()]
C = pd.concat([pd.read_csv(f) for f in glob.glob("/home/claude/clockout2/clock_*.csv")]).groupby(["player_id", "season"], as_index=False).sum(numeric_only=True)
C["hc_fga"] = C.hc_early_fga + C.hc_mid_fga + C.late_fga; C["hc_pts"] = C.hc_early_pts + C.hc_mid_pts + C.late_pts; C["all_fga"], C["all_pts"] = C.fga, C.pts
B = {"all": "all shots", "hc": "half court", "hc_early": "half court, 10+ s left", "early": "transition", "late": "late clock"}
for b in B:
    lg = C.groupby("season")[[f"{b}_fga", f"{b}_pts"]].sum(); C = C.join((lg[f"{b}_pts"] / lg[f"{b}_fga"]).rename(f"lg_{b}"), on="season")
    n = C[f"{b}_fga"]; C[f"x_{b}"] = (C[f"{b}_pts"] / n.replace(0, np.nan) - C[f"lg_{b}"]).fillna(0) * n / (n + 300) * 100   # points per 100 shots, shrunk
D = P.merge(C, left_on=["pid", "season"], right_on=["player_id", "season"])
print(f"{len(D)} playoff runs, {D.season.nunique()} postseasons")
def cv(target, base, extra):
    err = tot = 0
    for s in D.season.unique():
        tr, te = D[D.season != s], D[D.season == s]
        X = lambda d: np.c_[np.ones(len(d)), d[base].values, *(d[e].values for e in extra)]
        w = tr.po_poss.values; Xt = X(tr); beta = np.linalg.solve(Xt.T @ (Xt * w[:, None]) + 1e-6 * np.eye(Xt.shape[1]), Xt.T @ (tr[target].values * w))
        err += np.sum(te.po_poss.values * (te[target].values - X(te) @ beta) ** 2); tot += te.po_poss.sum()
    return err / tot, beta
for target, base in (("po_o", "rs_o"), ("po_r", "rs_r")):
    e0, b0 = cv(target, base, [])
    print(f"\npredicting playoff {'offense' if target == 'po_o' else 'Chip Equity'} from regular-season {'offense' if base == 'rs_o' else 'Chip Equity'}: error {e0:.3f} (weight {b0[1]:.2f})")
    for b, lab in B.items():
        e, bb = cv(target, base, [f"x_{b}"])
        print(f"   + {lab:24s} error {e:.3f} ({(e - e0) / e0 * 100:+.1f}%)  weight per 10 pts/100 shots: {bb[2] * 10:+.2f}")
    e, bb = cv(target, base, ["x_hc_early", "x_early", "x_late"])
    print(f"   + early half court, transition and late clock together: error {e:.3f} ({(e - e0) / e0 * 100:+.1f}%)  weights x10: {bb[2]*10:+.2f} / {bb[3]*10:+.2f} / {bb[4]*10:+.2f}")
