"""Where in the possession every shot came, from NBA play-by-play (shufinskiy/nba_data nbastats_<year>.csv).

For each field-goal attempt: seconds since the shot clock last reset (start of the possession, or an offensive rebound),
read from the game clock. A shot is
  late   when 6 or fewer seconds were left on the shot clock (24-second clock; after an offensive rebound it resets
         to 24, or to 14 from 2018-19 on),
  early  when it came within 7 seconds of a new possession (not after an offensive rebound): mostly transition,
  hc_early  a half-court shot (7+ seconds into a new possession) with more than 10 seconds left on the shot clock,
  hc_mid    a half-court shot with 7-10 seconds left (late is 6 or fewer), putback  within 4 seconds of an offensive rebound.
Possessions that started with less than 24 seconds on the game clock are skipped (the game clock runs out first), and
so are attempts that can't be placed in a possession.
Output per player and team: fga, pts (field-goal points), placed_fga, late_fga, late_pts, late_3a, early_fga, early_pts.
usage: python clock_build.py nbastats_2016.csv 2016-17 out.csv"""
import sys, pandas as pd, numpy as np
f, season, out = sys.argv[1:4]
RESET_OREB = 14 if int(season[:4]) >= 2018 else 24
d = pd.read_csv(f, low_memory=False, usecols=["GAME_ID", "EVENTNUM", "EVENTMSGTYPE", "EVENTMSGACTIONTYPE", "PERIOD", "PCTIMESTRING",
                                             "HOMEDESCRIPTION", "VISITORDESCRIPTION", "PLAYER1_ID", "PLAYER1_TEAM_ID"])
d = d.sort_values(["GAME_ID", "PERIOD", "EVENTNUM"], kind="stable")
def secs(s):
    try: m, x = str(s).split(":"); return int(m) * 60 + float(x)
    except Exception: return np.nan
d["left"] = d.PCTIMESTRING.map(secs)
d["desc"] = (d.HOMEDESCRIPTION.fillna("") + " " + d.VISITORDESCRIPTION.fillna("")).str.upper()
KEYS = ["fga", "pts", "placed_fga", "late_fga", "late_pts", "late_3a", "early_fga", "early_pts", "hc_early_fga", "hc_early_pts", "hc_mid_fga", "hc_mid_pts", "putback_fga", "putback_pts"]
acc = {}
import os
SHOTS = [] if os.environ.get("SHOTS") else None          # SHOTS=<path>: also write every shot (game, period, clock, team, shooter, bucket, points)
def add(pid, tid, **kv):
    r = acc.setdefault((int(pid), int(tid)), dict.fromkeys(KEYS, 0))
    for k, v in kv.items(): r[k] += v
games = 0
for gid, g in d.groupby("GAME_ID", sort=False):
    teams = [int(x) for x in g.PLAYER1_TEAM_ID.dropna().unique() if x > 1e9]
    if len(teams) != 2: continue
    games += 1; other = lambda t: teams[1] if t == teams[0] else teams[0]
    off, reset_left, kind, last_shot = None, None, None, None
    for e in g.itertuples(index=False):
        t, left = e.EVENTMSGTYPE, e.left
        team = int(e.PLAYER1_TEAM_ID) if pd.notna(e.PLAYER1_TEAM_ID) else (int(e.PLAYER1_ID) if pd.notna(e.PLAYER1_ID) and e.PLAYER1_ID > 1e9 else None)
        if t == 12: off, reset_left, kind, last_shot = None, left, "start", None; continue
        if team not in teams: continue
        if t in (1, 2):
            if pd.isna(e.PLAYER1_ID) or e.PLAYER1_ID <= 0 or e.PLAYER1_ID > 1e9: continue
            pts = (3 if "3PT" in e.desc else 2) if t == 1 else 0
            kv = {"fga": 1, "pts": pts}
            if off == team and reset_left is not None and reset_left >= 24 and not np.isnan(left):
                el = reset_left - left; clock = RESET_OREB if kind == "oreb" else 24
                if -0.5 <= el <= clock + 1:
                    kv["placed_fga"] = 1
                    if clock - el <= 6: kv.update(late_fga=1, late_pts=pts, late_3a=int("3PT" in e.desc))
                    if kind in ("new", "start") and el <= 7: kv.update(early_fga=1, early_pts=pts)
                    if kind in ("new", "start") and 7 < el and clock - el > 10: kv.update(hc_early_fga=1, hc_early_pts=pts)     # half court, 10+ left
                    if kind in ("new", "start") and clock - el <= 10 and clock - el > 6: kv.update(hc_mid_fga=1, hc_mid_pts=pts)  # half court, 7-10 left
                    if kind == "oreb" and el <= 4: kv.update(putback_fga=1, putback_pts=pts)
            add(e.PLAYER1_ID, team, **kv); last_shot = team
            if SHOTS is not None:
                bk = "late" if kv.get("late_fga") else "early" if kv.get("early_fga") else "hc_early" if kv.get("hc_early_fga") else "hc_mid" if kv.get("hc_mid_fga") else "putback" if kv.get("putback_fga") else "other"
                SHOTS.append((gid, e.PERIOD, left, team, int(e.PLAYER1_ID), bk, pts))
            if t == 1: off, reset_left, kind = other(team), left, "new"      # made: the other team's ball
            else: off = team
        elif t == 3:                                                         # a made last free throw ends the possession
            if e.EVENTMSGACTIONTYPE in (10, 12, 15) and "MISS" not in e.desc and "TECHNICAL" not in e.desc: off, reset_left, kind = other(team), left, "new"
        elif t == 4:                                                         # rebound
            if last_shot is not None and team == last_shot: off, reset_left, kind = team, left, "oreb"
            else: off, reset_left, kind = team, left, "new"
            last_shot = None
        elif t == 5:                                                         # turnover
            off, reset_left, kind = other(team), left, "new"
if SHOTS is not None: pd.DataFrame(SHOTS, columns=["game_id", "period", "left", "team_id", "player_id", "bucket", "pts"]).to_csv(os.environ["SHOTS"], index=False)
rows = [{"player_id": p, "team_id": tm, "season": season, **v} for (p, tm), v in acc.items()]
pd.DataFrame(rows).to_csv(out, index=False)
T = pd.DataFrame(rows).sum(numeric_only=True)
print(f"{season}: {games} games, {int(T.fga)} FGA, placed {T.placed_fga / T.fga:.1%}, late {T.late_fga / T.placed_fga:.1%} of placed (pts/FGA {T.late_pts / max(T.late_fga, 1):.3f} vs all {T.pts / T.fga:.3f}), early {T.early_fga / T.placed_fga:.1%} (pts/FGA {T.early_pts / max(T.early_fga, 1):.3f})")
