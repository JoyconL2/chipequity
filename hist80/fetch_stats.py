"""One-off: NBA.com stats season totals for 1979-80 .. 1995-96 (players and teams, regular season and playoffs),
for the box-score Chip Equity v1. Saves the raw JSON answers to hist80/raw/."""
import json, os, sys, time, datetime as dt
import requests
FF = max(158, 140 + (dt.date.today() - dt.date(2025, 6, 24)).days // 28)
H = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{FF}.0) Gecko/20100101 Firefox/{FF}.0",
     "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
     "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "x-nba-stats-origin": "stats", "x-nba-stats-token": "true"}
BASE = "https://stats.nba.com/stats/"
def q(ep, **kw):
    p = dict(LeagueID="00", PerMode="Totals", MeasureType="Base", PaceAdjust="N", PlusMinus="N", Rank="N", LastNGames=0, Month=0,
             OpponentTeamID=0, Period=0, DateFrom="", DateTo="", GameSegment="", Location="", Outcome="", SeasonSegment="",
             VsConference="", VsDivision="", Conference="", Division="", GameScope="", PlayerExperience="", PlayerPosition="",
             StarterBench="", TwoWay=0, ShotClockRange="", PORound=0, TeamID=0)
    p.update(kw)
    for i in range(2):
        try:
            r = requests.get(BASE + ep, params=p, headers=H, timeout=30)
            if r.status_code == 200: return r.json()
            print(ep, kw.get("Season"), kw.get("SeasonType"), "HTTP", r.status_code, flush=True)
        except Exception as e: print(ep, kw.get("Season"), type(e).__name__, flush=True)
        time.sleep(5 * (i + 1))
    return None
os.makedirs("hist80/raw", exist_ok=True); ok = bad = 0
if not q("leaguedashteamstats", Season="1985-86", SeasonType="Regular Season"):      # quick check before the full run
    print("::error::stats.nba.com did not answer from this computer"); sys.exit(1)
years = range(1979, 1997) if len(sys.argv) < 2 else [int(sys.argv[1])]
for y in years:
    season = f"{y}-{str(y + 1)[-2:]}"
    for st in ("Regular Season", "Playoffs"):
        for ep in ("leaguedashplayerstats", "leaguedashteamstats"):
            j = q(ep, Season=season, SeasonType=st)
            tag = f"{ep}_{season}_{'rs' if st[0] == 'R' else 'po'}"
            if j: json.dump(j, open(f"hist80/raw/{tag}.json", "w")); ok += 1; n = len(j["resultSets"][0]["rowSet"]); print(tag, n, "rows", flush=True)
            else: bad += 1
            time.sleep(1.5)
print("::warning::stats.nba.com: saved", ok, "files,", bad, "failed")
