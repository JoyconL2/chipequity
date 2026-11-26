"""One-off: regular-season live play-by-play for one finished season (game ids 002YY00001..), then clock relief."""
import os, sys, json, subprocess
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "update"); import fetch_season as F
season = sys.argv[1]; yy = season[2:4]; d = f"pbp/{season}"; os.makedirs(d, exist_ok=True)
def one(i):
    gid = f"002{yy}{i:05d}"; p = f"{d}/playbyplay_{gid}.json"
    if os.path.exists(p): return 1
    j = F.get(f"{F.CDN}/liveData/playbyplay/playbyplay_{gid}.json", tries=3)
    if j and j.get("game", {}).get("actions"): json.dump(j, open(p, "w")); return 1
    return 0
with ThreadPoolExecutor(8) as ex: got = list(ex.map(one, range(1, 1231)))
print(season, "games downloaded", sum(got), "statuses", sorted({str(v) for v in F.STATUS.values()})[:5])
st = f"base/stints/stints_{season}_rs.csv.xz"
subprocess.run(["xz", "-dk", st], check=True)
subprocess.run([sys.executable, "clockbuild/relief.py", d, season, st[:-3], f"out/relief_{season}.csv"], check=True, env=dict(os.environ))
