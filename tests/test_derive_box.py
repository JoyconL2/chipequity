"""Raw pbpstats stat keys -> pbpstats.com-style season columns."""
import pandas as pd
from derive_box import derive


def test_shot_and_assist_accounting():
    W = pd.DataFrame([{"EntityId": 1, "TeamId": 9, "Season": "1997-98", "season_type": "rs", "GamesPlayed": 2, "OffPoss": 100, "DefPoss": 100,
        "SecondsPlayedOff": 1000, "SecondsPlayedDef": 1000,
        "AssistedAtRim": 3, "UnassistedAtRim": 2, "MissedAtRim": 4, "AtRimBlocked": 1,
        "UnassistedArc3": 2, "AssistedCorner3": 1, "MissedArc3": 5,
        "FtsMade": 6, "FtsMissed": 2, "AtRimAssists": 4, "Arc3Assists": 2, "LongMidRangeAssists": 1,
        "LostBallTurnovers": 1, "BadPassTurnovers": 2, "DeadBallTurnovers": 3, "LostBallSteals": 1, "BadPassSteals": 1,
        "BlockedAtRim": 2, "AtRimOffRebounds": 3, "FTDefRebounds": 2, "Arc3DefRebounds": 4,
        "Personal Fouls": 2, "Shooting Fouls": 1, "Offensive Fouls": 1}])
    D = derive(W).iloc[0]
    assert D.AtRimFGA == 3 + 2 + 4 + 1                 # made (assisted + unassisted) + missed + blocked
    assert D.FG3A == 2 + 1 + 5 and D.FG3M == 3
    assert D.Points == 2 * 5 + 3 * 3 + 6
    assert D.PtsUnassisted2s == 4 and D.PtsUnassisted3s == 6
    assert D.Assists == 7 and D.AtRimAssists == 4
    assert D.LiveBallTurnovers == 3 and D.DeadBallTurnovers == 3 and D.Steals == 2 and D.Blocks == 2
    assert D.OffRebounds == 3 and D.DefRebounds == 6     # offensive and defensive rebounds kept separate
    assert D.Fouls == 4 and D.SecondsPlayed == 2000
