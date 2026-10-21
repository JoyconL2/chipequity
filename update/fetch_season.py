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
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = [{"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"},
           {"User-Agent": UA, "Accept": "*/*"},                     # plainer request, in case the first set is refused
           {}]
STATUS = {}                                                          # url -> what NBA.com answered (shown if the run fails)
SESSION = requests.Session()


def get(url, tries=3):
    for i in range(tries):
        for h in HEADERS:
            try:
                r = SESSION.get(url, headers=h, timeout=30)
                STATUS[url] = r.status_code
                if r.status_code == 200: return r.json()
                if r.status_code == 404: return None
            except (requests.RequestException, ValueError) as e:
                STATUS[url] = type(e).__name__
        time.sleep(2 * (i + 1))
    return None


def note(msg):
    """a one-line message that shows up as an annotation on the GitHub run (and in the log)"""
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else msg, flush=True)


def games_from_ids(season):
    """Fallback when the schedule file can't be read: walk the game ids (regular season 002YY0nnnn, playoffs
    004YY00RSG) and keep the games whose box score says they're final. Box scores already on disk are reused."""
    yy = season[2:4]; out = []
    def box(gid):
        return get(f"{CDN}/liveData/boxscore/boxscore_{gid}.json", tries=1)
    def keep(gid, B):
        g = B["game"]; ht, at = g["homeTeam"], g["awayTeam"]
        out.append(dict(gid=gid, stype="rs" if gid[:3] == "002" else "po", date=(g.get("gameEt") or g.get("gameTimeUTC") or "")[:10],
                        home=ht["teamId"], away=at["teamId"], home_ab=ht["teamTricode"], away_ab=at["teamTricode"], hp=int(ht.get("score") or 0), ap=int(at.get("score") or 0)))
    misses, n = 0, 1
    while n <= 1320 and misses < 40:                        # ids are handed out roughly in date order
        ids = [f"002{yy}{i:05d}" for i in range(n, n + 20)]; n += 20
        with ThreadPoolExecutor(6) as ex: got = list(ex.map(box, ids))
        for gid, B in zip(ids, got):
            if B and B.get("game", {}).get("gameStatus") == 3: keep(gid, B); misses = 0
            else: misses += 1
    if time.localtime().tm_mon in (4, 5, 6, 7):            # playoffs: round 1-4, series 0-7, game 1-7
        ids = [f"004{yy}00{r}{s}{g}" for r in range(1, 5) for s in range(8) for g in range(1, 8)]
        with ThreadPoolExecutor(6) as ex: got = list(ex.map(box, ids))
        for gid, B in zip(ids, got):
            if B and B.get("game", {}).get("gameStatus") == 3: keep(gid, B)
    return out


def main():
    out = sys.argv[1]
    url = f"{CDN}/staticData/scheduleLeagueV2.json"
    sch = get(url)
    want = sys.argv[2] if len(sys.argv) > 2 else None
    if not sch:
        note(f"NBA.com schedule not readable (answer: {STATUS.get(url)}); finding finished games by game id instead")
        if not want: sys.exit("no season given and no schedule")
        season, games = want, None
    else:
        L = sch["leagueSchedule"]; season = want or L["seasonYear"]
        if L["seasonYear"] != season: sys.exit(f"schedule is for {L['seasonYear']}, not {season}")
        games = []
    d = os.path.join(out, season)
    for sub in ("pbp_rs", "pbp_po", "box"): os.makedirs(os.path.join(d, sub), exist_ok=True)
    if games is None:
        games = games_from_ids(season)
        if not games:
            bad = sorted({str(v) for v in STATUS.values()})
            note(f"no finished {season} games found by id either (NBA.com answers seen: {', '.join(bad)})"); sys.exit("could not download games")
    for day in ([] if sch is None else L["gameDates"]):
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
    if missing: note(f"{len(missing)} finished games' files couldn't be downloaded yet (e.g. {missing[0]}: {STATUS.get(f'{CDN}/liveData/playbyplay/playbyplay_{missing[0]}.json')})")
    if games == [] and missing: sys.exit("no game files could be downloaded")


if __name__ == "__main__":
    main()
