"""One-off: the 2026-27 regular-season results so far, from NBA.com's schedule file -> oneoff/games_2026-27.csv"""
import csv, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "update"))
import fetch_season as F
sch = F.get(f"{F.CDN}/staticData/scheduleLeagueV2.json")
if not sch: sys.exit(f"schedule not readable: {F.STATUS}")
rows = []
for day in sch["leagueSchedule"]["gameDates"]:
    for g in day["games"]:
        if g.get("gameStatus") != 3 or not g["gameId"].startswith("002"): continue
        h, a = g["homeTeam"], g["awayTeam"]
        rows.append([g["gameId"], (g.get("gameDateEst") or "")[:10], h["teamTricode"], a["teamTricode"], h.get("score"), a.get("score"), g.get("isNeutral", False)])
rows.sort()
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "games_2026-27.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["gid", "date", "home", "away", "hp", "ap", "neutral"]); w.writerows(rows)
print(len(rows), "games")
