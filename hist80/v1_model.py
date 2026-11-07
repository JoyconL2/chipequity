"""Chip Equity v1: a box-score estimate of single-season Chip Equity, for seasons before play-by-play (1979-80..1995-96).

Trained on 1996-97..2025-26, where real Chip Equity exists. Every input is something the 1980s box score has too:
minutes, points, shooting, rebounds, assists, steals, blocks, turnovers, fouls, and the team's results. Rates are per
100 possessions the player was on the floor for (estimated the same way in both eras: team possessions from the box
score, FGA + 0.44 FTA - OREB + TOV, shared out by minutes) and taken relative to that season's league average.

usage: python v1_model.py test                 # train 1997-2011, test 2012-2026: accuracy
       python v1_model.py fit <features csv>   # train on everything, write predictions for the rows in the csv"""
import json, lzma, os, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATES = ["pts", "fga", "fg3a", "fta", "ast", "tov", "oreb", "dreb", "stl", "blk", "pf"]


def features(B):
    """B: one row per player-season-team-type with box counts: season, t, tm, p, gp, min, pts, fgm, fga, fg3m, fg3a,
    ftm, fta, oreb, dreb, ast, stl, blk, tov, pf; and team columns T_min, T_poss, T_pts, T_opp.
    Returns one row per player-season-type with the model inputs."""
    B = B.copy()
    B["on"] = B.T_poss * B["min"] / (B.T_min / 5).clip(lower=1)                 # possessions he was on the floor for (est.)
    B["tnet"] = 100 * (B.T_pts - B.T_opp) / B.T_poss.clip(lower=1)
    B["tnet_w"] = B.tnet * B["min"]
    g = B.groupby(["p", "season", "t"])
    A = g[["gp", "min", "on", "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk", "tov", "pf", "tnet_w"]].sum().reset_index()
    A["tnet"] = A.tnet_w / A["min"].clip(lower=1)
    tm = B.groupby(["p", "season", "t"]).apply(lambda x: (x["min"] / (x.T_min / 5)).sum() / max(len(x), 1), include_groups=False)
    A = A.merge(tm.rename("mshare").reset_index(), on=["p", "season", "t"])
    on = A.on.clip(lower=1)
    for c in RATES: A[c + "_100"] = 100 * A[c] / on
    A["ts"] = A.pts / (2 * (A.fga + 0.44 * A.fta)).clip(lower=1)
    A["usg"] = 100 * (A.fga + 0.44 * A.fta + A.tov) / on
    A["mpg"] = A["min"] / A.gp.clip(lower=1)
    # league-relative (possession-weighted league average of each season / season type)
    for c in [r + "_100" for r in RATES] + ["ts", "usg"]:
        lg = A.groupby(["season", "t"]).apply(lambda x: np.average(x[c], weights=x.on), include_groups=False).rename("lg").reset_index()
        A = A.merge(lg, on=["season", "t"]); A[c + "_rel"] = A[c] - A.lg; A = A.drop(columns="lg")
    A["ts_x_usg"] = A.ts_rel * A.usg
    A["tnet_x_ms"] = A.tnet * A.mshare
    A["ast_x_usg"] = A.ast_100_rel * A.usg
    return A


X_COLS = [r + "_100_rel" for r in RATES] + ["ts_rel", "usg_rel", "usg", "ts_x_usg", "mshare", "mpg", "tnet", "tnet_x_ms", "ast_x_usg"]


def modern_box():
    """1996-97..2025-26 in the same shape as the 1980s data (from the site's own player and team rows)"""
    D = json.load(lzma.open(os.path.join(ROOT, "base", "data.json.xz"))); S = D["seasons"]
    P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "tm", "gp", "sec", "pts", "reb", "ast", "stl", "blk", "tov", "fg2a", "fg2m", "fg3a", "fg3m", "fta", "ftm", "oreb", "dreb", "pf")})
    P = P.dropna(subset=["fg2m", "ftm", "oreb", "dreb", "pf"])
    P["season"] = [S[s] for s in P.s]; P["min"] = P.sec / 60
    P["fga"] = P.fg2a + P.fg3a; P["fgm"] = P.fg2m + P.fg3m
    T = pd.DataFrame({c: D["T"][c] for c in ("a", "s", "t", "pts", "opp")})
    tb = P.groupby(["s", "t", "tm"]).agg(T_min=("min", "sum"), T_fga=("fga", "sum"), T_fta=("fta", "sum"), T_oreb=("oreb", "sum"), T_tov=("tov", "sum")).reset_index()
    tb["T_poss"] = tb.T_fga + 0.44 * tb.T_fta - tb.T_oreb + tb.T_tov
    tb = tb.merge(T.rename(columns={"a": "tm", "pts": "T_pts", "opp": "T_opp"}), on=["s", "t", "tm"])
    P = P.merge(tb[["s", "t", "tm", "T_min", "T_poss", "T_pts", "T_opp"]], on=["s", "t", "tm"])
    rw = pd.DataFrame(D["rw"]["rows"], columns=["p", "s", "w", "o", "d", "r", "rank", "poss"]); rw = rw[(rw.w == 1) & (rw.poss >= 1500)]
    rw["season"] = [S[s] for s in rw.s]
    return P, rw, D


def models():
    return {"ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
            "gbm": lambda: HistGradientBoostingRegressor(max_iter=400, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0)}


def main():
    P, rw, D = modern_box()
    F = features(P[P.t == 0]); F = F.merge(rw[["p", "season", "o", "d", "r"]], on=["p", "season"])
    F = F[F.season != "1996-97"]                                     # 3-year steadying has no history for the first season
    yr = F.season.str[:4].astype(int)
    if sys.argv[1:2] == ["test"]:
        tr, te = F[yr <= 2011], F[yr >= 2012]
        for name, mk in models().items():
            preds = {}
            for tgt in ("o", "d"):
                m = mk(); m.fit(tr[X_COLS], tr[tgt]); preds[tgt] = m.predict(te[X_COLS])
            pr = preds["o"] + preds["d"]
            for lab, p_, y_ in (("total", pr, te.r), ("off", preds["o"], te.o), ("def", preds["d"], te.d)):
                print(f"{name:5s} {lab:5s} r={np.corrcoef(p_, y_)[0, 1]:.3f} rmse={np.sqrt(np.mean((p_ - y_) ** 2)):.2f}  (test n={len(te)})")
            te2 = te.assign(pred=pr); top = te2.sort_values("pred", ascending=False).head(12)
            nm = D["names"]; print("   top predicted test seasons:", "; ".join(f"{nm[k]} {s} {p:+.1f} (real {r:+.1f})" for k, s, p, r in zip(top.p, top.season, top.pred, top.r)))
        return
    if sys.argv[1:2] == ["fit"]:
        X = pd.read_csv(sys.argv[2]); mk = models()[os.environ.get("V1_MODEL", "gbm")]
        for tgt in ("o", "d"):
            m = mk(); m.fit(F[X_COLS], F[tgt]); X[tgt] = m.predict(X[X_COLS])
        X["r"] = X.o + X.d; X.to_csv(sys.argv[3] if len(sys.argv) > 3 else "v1_pred.csv", index=False); print("wrote", len(X), "rows")


if __name__ == "__main__":
    main()
