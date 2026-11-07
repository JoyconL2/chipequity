"""One-off: NBA.com box-score data for 1979-80 .. 1995-96 (plus 1996-97 to line up with the play-by-play era), for the
box-score Chip Equity v1. Season-level league tables are empty before 1996-97 on NBA.com, so this uses:
  leaguegamelog (teams: every game, regular season + playoffs) -> team totals, opponents' points, margins
  leaguegamelog (players), if NBA.com has it for that season, else playercareerstats for every player active then
Raw JSON answers go to hist80/raw/."""
import json, os, sys, time, datetime as dt
import requests
FF = max(158, 140 + (dt.date.today() - dt.date(2025, 6, 24)).days // 28)
H = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{FF}.0) Gecko/20100101 Firefox/{FF}.0",
     "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
     "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "x-nba-stats-origin": "stats", "x-nba-stats-token": "true"}
BASE = "https://stats.nba.com/stats/"
def q(ep, **p):
    for i in range(3):
        try:
            r = requests.get(BASE + ep, params=p, headers=H, timeout=30)
            if r.status_code == 200: return r.json()
            print(ep, p, "HTTP", r.status_code, flush=True)
        except Exception as e: print(ep, p, type(e).__name__, flush=True)
        time.sleep(4 * (i + 1))
    return None
R = "hist80/raw"; os.makedirs(R, exist_ok=True)
for f in os.listdir(R):
    if f.startswith("leaguedash"): os.remove(os.path.join(R, f))          # the empty first attempt
rows = lambda j: j["resultSets"][0]["rowSet"] if j else []
need_career = set()
for y in range(1979, 1997):
    season = f"{y}-{str(y + 1)[-2:]}"
    for st, tag in (("Regular Season", "rs"), ("Playoffs", "po")):
        for who in ("T", "P"):
            f = f"{R}/gamelog_{who}_{season}_{tag}.json"
            if os.path.exists(f) and rows(json.load(open(f))): continue
            j = q("leaguegamelog", LeagueID="00", Season=season, SeasonType=st, PlayerOrTeam=who, Direction="ASC", Sorter="DATE", Counter=0, DateFrom="", DateTo="")
            n = len(rows(j)); print(season, tag, who, n, "rows", flush=True)
            if j: json.dump(j, open(f, "w"))
            if who == "P" and n == 0: need_career.add(y)
            time.sleep(1.2)
print("::warning::game logs done; seasons without player game logs:", sorted(need_career))
if need_career:
    ap = q("commonallplayers", LeagueID="00", Season="1996-97", IsOnlyCurrentSeason=0)
    h = ap["resultSets"][0]["headers"]; P = [dict(zip(h, r)) for r in rows(ap)]
    lo, hi = min(need_career), max(need_career)
    ids = [p["PERSON_ID"] for p in P if int(p["FROM_YEAR"] or 0) <= hi and int(p["TO_YEAR"] or 0) >= lo]
    print("career totals for", len(ids), "players", flush=True); done = 0
    os.makedirs(f"{R}/career", exist_ok=True)
    for pid in ids:
        f = f"{R}/career/{pid}.json"
        if os.path.exists(f): continue
        j = q("playercareerstats", PlayerID=pid, PerMode="Totals", LeagueID="00")
        if j: json.dump({rs["name"]: rs for rs in j["resultSets"] if rs["name"] in ("SeasonTotalsRegularSeason", "SeasonTotalsPostSeason")}, open(f, "w")); done += 1
        time.sleep(0.8)
    print(f"::warning::career totals saved for {done} of {len(ids)} players")
