"""Feature table for the impact model, built only from the pbpstats download.

One row per player-season (regular season). Offensive stats are per 100 offensive possessions,
defensive stats per 100 defensive possessions, and every rate is expressed relative to that
season's league average so eras compare fairly.
Targets: the team's offensive / defensive rating while the player was on the floor, vs league.
"""
import sys
import numpy as np
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "../zip2/pbpstats_data/"
p = pd.read_csv(SRC + "Player_all_seasons.csv", low_memory=False)
t = pd.read_csv(SRC + "Team_all_seasons.csv", low_memory=False)


def g(df, c):
    return df[c].fillna(0).astype(float) if c in df else pd.Series(0.0, index=df.index)


def build(season_type="Regular Season"):
    d = p[p.SeasonType == season_type].copy()
    tt = t[t.SeasonType == season_type]
    # league context per season
    lg = tt.groupby("Season").apply(lambda x: pd.Series({
        "lg_ortg": x.Points.sum() / x.OffPoss.sum() * 100,
        "lg_ts": x.Points.sum() / (2 * (x.FG2A.sum() + x.FG3A.sum() + 0.44 * x.FTA.sum())),
    }), include_groups=False)
    d = d.join(lg, on="Season")
    op = d.OffPoss.clip(lower=1)
    dp = d.DefPoss.clip(lower=1)
    per_o = lambda s: s / op * 100
    per_d = lambda s: s / dp * 100
    fga = g(d, "FG2A") + g(d, "FG3A")
    tsa = fga + 0.44 * g(d, "FTA")
    F = pd.DataFrame(index=d.index)
    # ---- offense ----
    F["o_pts_added"] = per_o(g(d, "Points") - 2 * d.lg_ts * tsa)     # scoring above league-average efficiency
    F["o_tsa"] = per_o(tsa)                                            # shot volume
    F["o_rim_fga"] = per_o(g(d, "AtRimFGA"))
    F["o_mid_fga"] = per_o(g(d, "ShortMidRangeFGA") + g(d, "LongMidRangeFGA"))
    F["o_three_fga"] = per_o(g(d, "FG3A"))
    F["o_fta"] = per_o(g(d, "FTA"))
    F["o_unassisted"] = per_o(g(d, "PtsUnassisted2s") + g(d, "PtsUnassisted3s"))
    F["o_ast"] = per_o(g(d, "Assists"))
    F["o_ast_rim"] = per_o(g(d, "AtRimAssists"))
    F["o_ast_three"] = per_o(g(d, "Arc3Assists") + g(d, "Corner3Assists"))
    F["o_tov_live"] = per_o(g(d, "LiveBallTurnovers"))
    F["o_tov_dead"] = per_o(g(d, "DeadBallTurnovers"))
    F["o_oreb"] = per_o(g(d, "OffRebounds"))
    F["o_fouls_drawn"] = per_o(g(d, "FoulsDrawn"))
    F["o_off_fouls"] = per_o(g(d, "Offensive Fouls"))
    # ---- defense ----
    F["d_dreb"] = per_d(g(d, "DefRebounds"))
    F["d_stl"] = per_d(g(d, "Steals"))
    F["d_blk"] = per_d(g(d, "Blocks"))
    F["d_fouls"] = per_d(g(d, "Fouls"))
    F["d_charges"] = per_d(g(d, "Charge Fouls Drawn"))
    # ---- role ----
    F["mpg"] = g(d, "SecondsPlayed") / 60 / g(d, "GamesPlayed").clip(lower=1)
    # relative to the season's possession-weighted league average
    w = (op + dp) / 2
    for c in F.columns:
        m = (F[c] * w).groupby(d.Season).transform("sum") / w.groupby(d.Season).transform("sum")
        F[c] = F[c] - m
    out = pd.concat([d[["EntityId", "Name", "TeamId", "TeamAbbreviation", "Season", "GamesPlayed", "SecondsPlayed", "OffPoss", "DefPoss"]].reset_index(drop=True),
                     F.reset_index(drop=True)], axis=1)
    out["poss"] = ((d.OffPoss + d.DefPoss) / 2).values
    out["y_off"] = (d.OnOffRtg - d.lg_ortg).values          # team offense while on the floor, vs league
    out["y_def"] = (d.lg_ortg - d.OnDefRtg).values          # team defense while on the floor, vs league (positive = good)
    out["season_type"] = season_type
    return out


rs = build("Regular Season")
po = build("Playoffs")
rs.to_csv("features_rs.csv", index=False)
po.to_csv("features_po.csv", index=False)
print("regular season", rs.shape, "| playoffs", po.shape)
print(rs[["poss", "y_off", "y_def"]].describe().round(2).to_string())
