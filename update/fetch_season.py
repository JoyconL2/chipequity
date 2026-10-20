"""Download every finished game of the season being played from NBA.com's public CDN:
  schedule  https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json
  per game  https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_<gameId>.json
            https://cdn.nba.com/static/json/liveData/boxscore/boxscore_<gameId>.json   (full player names)
Regular season = game ids 002..., playoffs = 004... (preseason, play-in and the NBA Cup final don't count, as in
every earlier season). Files already on disk are not downloaded again.

usage: python update/fetch_season.py <out dir> [season, e.g. 2026-27]
writes <out>/<season>/pbp_rs/*.json, pbp_po/*.json, box/*.json, games.csv, names.json"""
import sys, os, json, time, csv
from concurrent.futures import ThreadPoolExecutor
import requests

CDN = os.environ.get("NBA_CDN", "https://cdn.nba.com/static/json")   # override only for testing
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept": "application/json", "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"}


def get(url, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 200: return r.json()
            if r.status_code in (403, 404) and i >= 1: return None
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (i + 1))
    return None


def main():
    out = sys.argv[1]
    sch = get(f"{CDN}/staticData/scheduleLeagueV2.json")
    if not sch: sys.exit("could not load the NBA.com schedule")
    L = sch["leagueSchedule"]; season = sys.argv[2] if len(sys.argv) > 2 else L["seasonYear"]
    if L["seasonYear"] != season: sys.exit(f"schedule is for {L['seasonYear']}, not {season}")
    d = os.path.join(out, season)
    for sub in ("pbp_rs", "pbp_po", "box"): os.makedirs(os.path.join(d, sub), exist_ok=True)
    games = []
    for day in L["gameDates"]:
        for g in day["games"]:
            gid = g["gameId"]
            if g.get("gameStatus") != 3 or gid[:3] not in ("002", "004"): continue
            ht, at = g["homeTeam"], g["awayTeam"]
            games.append(dict(gid=gid, stype="rs" if gid[:3] == "002" else "po", date=(g.get("gameDateEst") or "")[:10],
                              home=ht["teamId"], away=at["teamId"], home_ab=ht["teamTricode"], away_ab=at["teamTricode"],
                              hp=int(ht.get("score") or 0), ap=int(at.get("score") or 0)))
    games.sort(key=lambda g: g["gid"])

    def one(g):
        p = os.path.join(d, f"pbp_{g['stype']}", f"{g['gid']}.json"); b = os.path.join(d, "box", f"{g['gid']}.json")
        ok = True
        for path, url in ((p, f"{CDN}/liveData/playbyplay/playbyplay_{g['gid']}.json"), (b, f"{CDN}/liveData/boxscore/boxscore_{g['gid']}.json")):
            if os.path.exists(path) and os.path.getsize(path) > 1000: continue
            j = get(url)
            if j is None: ok = False; continue
            with open(path + ".tmp", "w") as f: json.dump(j, f)
            os.replace(path + ".tmp", path)
        return g["gid"], ok

    with ThreadPoolExecutor(6) as ex: res = dict(ex.map(one, games))
    missing = [g for g, ok in res.items() if not ok]
    for g in missing:          # a game without play-by-play can't be used anywhere, so leave it out
        for sub in ("pbp_rs", "pbp_po"):
            q = os.path.join(d, sub, f"{g}.json")
            if os.path.exists(q) and os.path.getsize(q) < 1000: os.remove(q)
    games = [g for g in games if res.get(g["gid"])]
    with open(os.path.join(d, "games.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(games[0].keys()) if games else ["gid"]); w.writeheader(); w.writerows(games)
    names = {}
    for g in games:
        try: B = json.load(open(os.path.join(d, "box", f"{g['gid']}.json")))["game"]
        except Exception: continue
        for side in ("homeTeam", "awayTeam"):
            for p in B[side].get("players", []):
                nm = p.get("name") or f"{p.get('firstName', '')} {p.get('familyName', '')}".strip()
                if nm: names[str(p["personId"])] = nm
    json.dump(names, open(os.path.join(d, "names.json"), "w"))
    n_rs = sum(g["stype"] == "rs" for g in games)
    print(f"{season}: {len(games)} finished games ({n_rs} regular season, {len(games) - n_rs} playoffs), {len(missing)} not available yet, through {games[-1]['date'] if games else '-'}")
    if games == [] and missing: sys.exit("no game files could be downloaded")


if __name__ == "__main__":
    main()
