"""Basketball-Reference-style league averages (per team, per game) computed from play-by-play box totals."""
import sys
import pandas as pd
sys.path.insert(0, "../stintbuild")
from derive_box import derive


def league_row(path, season, n_games):
    W = pd.read_csv(path).fillna(0)
    team_tov = float(derive(W[(W.EntityId == 0) | (W.EntityId >= 1610612700)])[["LiveBallTurnovers", "DeadBallTurnovers"]].sum().sum())
    W = W[(W.EntityId > 0) & (W.EntityId < 1610612700)]                                # drop team rows (team rebounds etc.); BBRef counts players only
    D = derive(W)
    tg = float(W.groupby("TeamId").GamesPlayed.max().sum())        # team-games actually parsed
    s = lambda c: float(D[c].sum())
    fgm, fga = s("FG2M") + s("FG3M"), s("FG2A") + s("FG3A")
    ftm, fta, tov = s("FTM"), s("FTA"), s("LiveBallTurnovers") + s("DeadBallTurnovers") + team_tov
    secs = float((W.SecondsPlayedOff + W.SecondsPlayedDef).sum()) / 5      # team seconds
    poss = float((W.OffPoss + W.DefPoss).sum()) / 10                      # team possessions (avg of off/def)
    pts = s("Points")
    r = {"G": n_games, "MP": round(5 * secs / 60 / tg, 1), "FG": fgm / tg, "FGA": fga / tg, "3P": s("FG3M") / tg, "3PA": s("FG3A") / tg,
         "FT": ftm / tg, "FTA": fta / tg, "ORB": s("OffRebounds") / tg, "DRB": s("DefRebounds") / tg,
         "TRB": (s("OffRebounds") + s("DefRebounds")) / tg, "AST": s("Assists") / tg, "STL": s("Steals") / tg, "BLK": s("Blocks") / tg,
         "TOV": tov / tg, "PF": s("Fouls") / tg, "PTS": pts / tg, "FG%": fgm / fga, "3P%": s("FG3M") / s("FG3A"), "FT%": ftm / fta,
         "Pace": poss / (secs / 2880), "eFG%": (fgm + 0.5 * s("FG3M")) / fga, "TOV%": 100 * tov / (fga + 0.44 * fta + tov),
         "TS%": pts / (2 * (fga + 0.44 * fta)), "Season": season}
    return {k: (round(v, 4) if isinstance(v, float) and k.endswith("%") and k != "TOV%" else round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}


if __name__ == "__main__":
    import json
    print(league_row("../boxraw/box_2000-01_rs.csv", "2000-01", 1189))
    print(json.load(open("data_2000.json"))["league"][0] if False else "")
