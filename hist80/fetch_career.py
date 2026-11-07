"""One-off: season totals (playercareerstats) for every player active 1979-80..1982-83, where NBA.com's game logs
are missing rebounds / turnovers / steals for many games. Saves hist80/raw/career/<id>.json"""
import json, os, time, datetime as dt, requests
FF = max(158, 140 + (dt.date.today() - dt.date(2025, 6, 24)).days // 28)
H = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{FF}.0) Gecko/20100101 Firefox/{FF}.0", "Accept": "application/json, text/plain, */*",
     "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "x-nba-stats-origin": "stats", "x-nba-stats-token": "true"}
def q(ep, **p):
    for i in range(3):
        try:
            r = requests.get("https://stats.nba.com/stats/" + ep, params=p, headers=H, timeout=30)
            if r.status_code == 200: return r.json()
        except Exception as e: print(ep, p, type(e).__name__, flush=True)
        time.sleep(4 * (i + 1))
R = "hist80/raw/career"; os.makedirs(R, exist_ok=True)
ap = q("commonallplayers", LeagueID="00", Season="1996-97", IsOnlyCurrentSeason=0); h = ap["resultSets"][0]["headers"]
P = [dict(zip(h, r)) for r in ap["resultSets"][0]["rowSet"]]
json.dump(ap, open("hist80/raw/commonallplayers.json", "w"))
ids = [p["PERSON_ID"] for p in P if int(p["FROM_YEAR"] or 0) <= 1982 and int(p["TO_YEAR"] or 0) >= 1979]
print("players", len(ids), flush=True); done = 0
for pid in ids:
    f = f"{R}/{pid}.json"
    if os.path.exists(f): continue
    j = q("playercareerstats", PlayerID=pid, PerMode="Totals", LeagueID="00")
    if j: json.dump({rs["name"]: rs for rs in j["resultSets"] if rs["name"] in ("SeasonTotalsRegularSeason", "SeasonTotalsPostSeason")}, open(f, "w")); done += 1
    time.sleep(0.7)
print(f"::warning::career totals saved for {done} of {len(ids)} players")
