"""Read the NBA.com raw files for 1979-80..1996-97 (hist80/raw/) into one box row per player-season-team-type, in the
shape v1_model.features() expects, plus team totals from the team game logs.
usage: python build80.py   -> hist80/box80.csv (players), hist80/team80.csv (teams), hist80/names80.json"""
import glob, json, os
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(H, "raw")


def rs(path):
    j = json.load(open(path)); r = j["resultSets"][0] if "resultSets" in j else j
    return pd.DataFrame(r["rowSet"], columns=r["headers"])


def season_of(f): return os.path.basename(f).split("_")[2]


# ---- teams: every game, regular season and playoffs ----
teams, names = [], {}
for f in sorted(glob.glob(os.path.join(R, "gamelog_T_*.json"))):
    g = rs(f)
    if not len(g): continue
    season, t = season_of(f), int(f.endswith("_po.json"))
    opp = g[["GAME_ID", "TEAM_ID", "PTS"]].rename(columns={"TEAM_ID": "OPP_ID", "PTS": "OPP_PTS"})
    g = g.merge(opp, on="GAME_ID"); g = g[g.TEAM_ID != g.OPP_ID]
    a = g.groupby(["TEAM_ID", "TEAM_ABBREVIATION"]).agg(GP=("GAME_ID", "nunique"), W=("WL", lambda x: (x == "W").sum()), MIN=("MIN", "sum"),
        FGM=("FGM", "sum"), FGA=("FGA", "sum"), FG3M=("FG3M", "sum"), FG3A=("FG3A", "sum"), FTM=("FTM", "sum"), FTA=("FTA", "sum"),
        OREB=("OREB", "sum"), DREB=("DREB", "sum"), AST=("AST", "sum"), STL=("STL", "sum"), BLK=("BLK", "sum"), TOV=("TOV", "sum"),
        PF=("PF", "sum"), PTS=("PTS", "sum"), OPP_PTS=("OPP_PTS", "sum")).reset_index()
    a["season"], a["t"] = season, t
    teams.append(a)
T = pd.concat(teams, ignore_index=True)
T["T_min"] = T.MIN.where(T.MIN > T.GP * 200, T.GP * 240)   # game-log MIN is team minutes (5 x 48 + OT)
T["T_poss"] = T.FGA + 0.44 * T.FTA - T.OREB + T.TOV
T.to_csv(os.path.join(H, "team80.csv"), index=False)

# ---- players: game logs where NBA.com has them, career totals otherwise ----
rows = []
have = set()
for f in sorted(glob.glob(os.path.join(R, "gamelog_P_*.json"))):
    g = rs(f)
    if not len(g): continue
    season, t = season_of(f), int(f.endswith("_po.json")); have.add((season, t))
    for pid, nm in zip(g.PLAYER_ID, g.PLAYER_NAME): names[int(pid)] = nm
    a = g.groupby(["PLAYER_ID", "TEAM_ID"]).agg(gp=("GAME_ID", "nunique"), min=("MIN", "sum"), pts=("PTS", "sum"), fgm=("FGM", "sum"), fga=("FGA", "sum"),
        fg3m=("FG3M", "sum"), fg3a=("FG3A", "sum"), ftm=("FTM", "sum"), fta=("FTA", "sum"), oreb=("OREB", "sum"), dreb=("DREB", "sum"),
        ast=("AST", "sum"), stl=("STL", "sum"), blk=("BLK", "sum"), tov=("TOV", "sum"), pf=("PF", "sum")).reset_index()
    a["season"], a["t"] = season, t; rows.append(a)
for f in sorted(glob.glob(os.path.join(R, "career", "*.json"))):
    j = json.load(open(f))
    for key, t in (("SeasonTotalsRegularSeason", 0), ("SeasonTotalsPostSeason", 1)):
        if key not in j: continue
        c = pd.DataFrame(j[key]["rowSet"], columns=j[key]["headers"])
        c = c[(c.TEAM_ID != 0) & c.SEASON_ID.isin(T.season.unique())]
        c = c[[(s, t) not in have for s in c.SEASON_ID]]
        if not len(c): continue
        a = pd.DataFrame({"PLAYER_ID": c.PLAYER_ID, "TEAM_ID": c.TEAM_ID, "gp": c.GP, "min": c.MIN, "pts": c.PTS, "fgm": c.FGM, "fga": c.FGA,
            "fg3m": c.FG3M, "fg3a": c.FG3A, "ftm": c.FTM, "fta": c.FTA, "oreb": c.OREB, "dreb": c.DREB, "ast": c.AST, "stl": c.STL,
            "blk": c.BLK, "tov": c.TOV, "pf": c.PF, "season": c.SEASON_ID, "t": t})
        rows.append(a)
B = pd.concat(rows, ignore_index=True).fillna(0)
B = B.merge(T[["TEAM_ID", "season", "t", "TEAM_ABBREVIATION", "T_min", "T_poss", "PTS", "OPP_PTS"]].rename(columns={"PTS": "T_pts", "OPP_PTS": "T_opp"}),
            on=["TEAM_ID", "season", "t"])
B = B.rename(columns={"PLAYER_ID": "p", "TEAM_ID": "tm"})
B.to_csv(os.path.join(H, "box80.csv"), index=False)
json.dump({str(k): v for k, v in names.items()}, open(os.path.join(H, "names80.json"), "w"))
print("teams", len(T), "rows,", T.season.nunique(), "seasons | players", len(B), "rows,", B.p.nunique(), "players | names", len(names))
print(B.groupby(["season", "t"]).size().unstack().to_string())
