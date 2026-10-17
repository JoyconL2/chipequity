"""Factor counts for every stint (a stretch with no substitutions), from pbpstats possession logs (2000-01..2024-25).
Each possession is placed in the stint whose clock range contains its midpoint (same game and period); its offense
is the team that isn't OPPONENT. Output per stint and side: possessions, FGA, FGM, 3PM, missed FG, offensive
rebounds, turnovers, free-throw trips (shooting fouls + non-shooting fouls with free throws)."""
import sys, os, json, numpy as np, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]
ab_id = {}
for a, s in zip(D["T"]["a"], D["T"]["s"]): ab_id[(S[s], D["abbrs"][a])] = int(D["teamIds"][a])
ALIAS = {"NOH": ["NOP", "NOK"], "NOP": ["NOH"], "NJN": ["BKN"], "BKN": ["NJN"], "CHA": ["CHO", "CHH"], "CHH": ["CHA"], "SEA": ["OKC"], "OKC": ["SEA"], "VAN": ["MEM"], "PHX": ["PHO"], "GSW": ["GS"], "NOK": ["NOH", "NOP"]}
def tid_of(season, ab):
    for x in [ab] + ALIAS.get(ab, []):
        if (season, x) in ab_id: return ab_id[(season, x)]
    return None
def sec(t): m, s = str(t).split(":"); return int(m) * 60 + float(s)
for y in range(2000, 2025):
    season = f"{y}-{str(y + 1)[-2:]}"; out = f"fstints_{season}.csv"
    if os.path.exists(out): continue
    os.system(f"cd /tmp/claude-0/-home-claude/d45461d2-6819-5ccf-a7df-ceffda37ed81/scratchpad/pbx && rm -f *.csv && tar -xJf ../nbadata/datasets/pbpstats_{y}.tar.xz")
    f = f"../pbx/pbpstats_{y}.csv"
    cols = ["GAMEID", "PERIOD", "STARTTIME", "ENDTIME", "OPPONENT", "FG2A", "FG2M", "FG3A", "FG3M", "OFFENSIVEREBOUNDS", "TURNOVERS", "SHOOTINGFOULSDRAWN", "NONSHOOTINGFOULSTHATRESULTEDINFTS"]
    p = pd.read_csv(f, usecols=cols).drop_duplicates(["GAMEID", "PERIOD", "STARTTIME", "ENDTIME", "OPPONENT"])
    p["mid"] = (p.STARTTIME.map(sec) + p.ENDTIME.map(sec)) / 2
    p["game_id"] = p.GAMEID.astype(int).map(lambda g: f"{g:010d}")
    p["opp_id"] = [tid_of(season, a) for a in p.OPPONENT]
    st = pd.read_csv(f"../stints/stints_{season}_rs.csv", dtype={"game_id": str})
    st["sid"] = np.arange(len(st))
    # match each possession to the stint whose (end_sec, start_sec] contains its midpoint
    st_s = st.loc[st.start_sec > st.end_sec, ["game_id", "period", "start_sec", "end_sec", "sid", "home_team", "away_team"]].sort_values("end_sec")   # zero-length stints (subs at one instant) hold no clock time
    p = p.rename(columns={"PERIOD": "period"}).sort_values("mid")
    m = pd.merge_asof(p, st_s, left_on="mid", right_on="end_sec", by=["game_id", "period"], direction="backward", allow_exact_matches=False)
    m = m[m.sid.notna() & (m["mid"] <= m.start_sec)]
    m["side"] = np.where(m.opp_id == m.away_team, "home", np.where(m.opp_id == m.home_team, "away", None))
    miss = m.side.isna().mean(); m = m[m.side.notna()]
    m["FGA"] = m.FG2A + m.FG3A; m["FGM"] = m.FG2M + m.FG3M; m["MISS"] = m.FGA - m.FGM
    m["FTT"] = m.SHOOTINGFOULSDRAWN + m.NONSHOOTINGFOULSTHATRESULTEDINFTS; m["P"] = 1
    a = m.groupby(["sid", "side"])[["P", "FGA", "FGM", "FG3M", "MISS", "OFFENSIVEREBOUNDS", "TURNOVERS", "FTT"]].sum().reset_index()
    a = a.rename(columns={"OFFENSIVEREBOUNDS": "OREB", "TURNOVERS": "TOV"})
    a = a.merge(st[["sid", "game_id", "home_team", "away_team", "home_players", "away_players"]], on="sid")
    a.to_csv(out, index=False)
    print(season, "possessions", len(p), "matched", len(m), f"(side unknown {miss:.1%})", "| stint-sides", len(a), flush=True)
os.system("rm -f /tmp/claude-0/-home-claude/d45461d2-6819-5ccf-a7df-ceffda37ed81/scratchpad/pbx/*.csv")
