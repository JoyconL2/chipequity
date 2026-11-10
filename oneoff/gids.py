"""One-off (runs on the self-hosted runner): NBA.com game ids for every game 1996-97 .. 2025-26, so the Live Feed can
open old games from NBA.com and link plays to NBA.com video. Also probes how far back NBA.com's play-by-play files
and play videos go. Writes oneoff/out/gids_<season>.json and oneoff/out/probe.json."""
import json, os, time, datetime as dt
import requests
FF = max(158, 140 + (dt.date.today() - dt.date(2025, 6, 24)).days // 28)
H = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{FF}.0) Gecko/20100101 Firefox/{FF}.0",
     "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9",
     "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com", "x-nba-stats-origin": "stats", "x-nba-stats-token": "true"}
def get(url, **p):
    for i in range(3):
        try:
            r = requests.get(url, params=p, headers=H, timeout=30)
            if r.status_code == 200: return r
            if r.status_code in (403, 404): return r
        except Exception as e: print(url, type(e).__name__, flush=True)
        time.sleep(4 * (i + 1))
    return None
O = "oneoff/out"; os.makedirs(O, exist_ok=True)
probe = {}
for y in range(1996, 2026):
    season = f"{y}-{str(y + 1)[-2:]}"; games = {}
    for st in ("Regular Season", "Playoffs"):
        r = get("https://stats.nba.com/stats/leaguegamelog", LeagueID="00", Season=season, SeasonType=st, PlayerOrTeam="T", Direction="ASC", Sorter="DATE", Counter=0, DateFrom="", DateTo="")
        if not r or r.status_code != 200: print(season, st, "failed", r and r.status_code, flush=True); continue
        rs = r.json()["resultSets"][0]; h = rs["headers"]
        for row in rs["rowSet"]:
            x = dict(zip(h, row)); g = games.setdefault(x["GAME_ID"], {"d": x["GAME_DATE"][:10]})
            if " vs. " in x["MATCHUP"]: g["h"] = x["TEAM_ABBREVIATION"]
            elif " @ " in x["MATCHUP"]: g["a"] = x["TEAM_ABBREVIATION"]
        time.sleep(1.0)
    out = sorted([gid, g["d"], g.get("h", ""), g.get("a", "")] for gid, g in games.items())
    json.dump(out, open(f"{O}/gids_{season}.json", "w"), separators=(",", ":"))
    # probes on one regular-season game a quarter of the way into the season
    rsg = [x for x in out if x[0].startswith("002")]; p = {"games": len(out)}
    if rsg:
        gid = rsg[len(rsg) // 4][0]; p["gid"] = gid
        r = get(f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{gid}.json"); p["cdn_pbp"] = r.status_code if r else None
        nums = []
        if r is not None and r.status_code == 200:
            nums = [a["actionNumber"] for a in r.json()["game"]["actions"] if a.get("actionType") in ("2pt", "3pt") and a.get("shotResult") == "Made"][:3]
        else:
            v = get("https://stats.nba.com/stats/playbyplayv3", GameID=gid, StartPeriod=0, EndPeriod=0)
            p["stats_pbp"] = v.status_code if v else None
            if v is not None and v.status_code == 200:
                nums = [a["actionNumber"] for a in v.json()["game"]["actions"] if a.get("shotResult") == "Made"][:3]
        vids = []
        for n in nums:
            v = get("https://stats.nba.com/stats/videoeventsasset", GameID=gid, GameEventID=n)
            try: u = v.json()["resultSets"]["Meta"]["videoUrls"]; vids.append(bool(u and (u[0].get("lurl") or u[0].get("murl"))))
            except Exception: vids.append(None)
            time.sleep(0.8)
        p["video"] = vids
    probe[season] = p; print(season, p, flush=True)
json.dump(probe, open(f"{O}/probe.json", "w"), indent=1)
