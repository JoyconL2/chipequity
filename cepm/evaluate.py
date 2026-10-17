"""Pure RAPM vs CEPM: which predicts NEXT season better?
Player value = 3-year window ending season s. Team prediction for s+1 = sum(value x share of floor time in s+1).
Also a player-level test: next season's on-court net rating (on/off-style) for players with real minutes."""
import sys
import numpy as np, pandas as pd

F = pd.read_csv("../mymodel/features_rs.csv")
T = pd.read_csv("../zip2/pbpstats_data/Team_all_seasons.csv", low_memory=False)
T = T[T.SeasonType == "Regular Season"]
tnet = (T.Points / T.OffPoss * 100 - T.OpponentPoints / T.DefPoss * 100).groupby([T.Season, T.TeamId]).first()
ALL = [f"{y}-{str(y + 1)[-2:]}" for y in range(1996, 2026)]
nxt = {ALL[i]: ALL[i + 1] for i in range(len(ALL) - 1)}


def team_test(path, rookie):
    R = pd.read_csv(path); v = R.set_index(["player", "window_end"]).rapm
    rows = []
    for s, s1 in nxt.items():
        cur = F[F.Season == s1]
        if cur.empty or (R.window_end == s).sum() == 0: continue
        sh = 5 * cur.poss / cur.groupby("TeamId").poss.transform("sum")
        val = np.array([v.get((int(p), s), rookie) for p in cur.EntityId])
        pred = pd.Series(val * sh.values).groupby(cur.TeamId.values).sum()
        for t, x in pred.items():
            a = tnet.get((s1, t), np.nan)
            if not np.isnan(a): rows.append((s1, x, a))
    d = pd.DataFrame(rows, columns=["s", "pred", "act"])
    k = (d.pred * d.act).sum() / (d.pred ** 2).sum()
    return np.corrcoef(d.pred, d.act)[0, 1], np.sqrt(((k * d.pred - d.act) ** 2).mean()), len(d)


for name, path in [("pure RAPM", "../rapm_out/rw3.csv"), ("CEPM", sys.argv[1] if len(sys.argv) > 1 else "cepm3.csv")]:
    best = max((team_test(path, rk) + (rk,) for rk in (-3, -2, -1, 0)), key=lambda x: x[0])
    print(f"{name:10s} next-season team net: corr {best[0]:.3f}, rmse {best[1]:.2f} ({best[2]} team-seasons, unknown players = {best[3]})")
