"""Search ESPN by name for every silhouette player without an ESPN headshot yet; keep a match only when exactly one
NBA player on ESPN has that name and ESPN has a headshot for him. Writes espn_more.json {nbaId: espnId}."""
import json, subprocess, urllib.parse, unicodedata, re, time
names = dict(l.split("\t") for l in open("players.tsv").read().splitlines())
sil = open("sil.txt").read().split(); M = json.load(open("alt_headshots.json"))
todo = [p for p in sil if not (isinstance(M.get(p), str) and M[p].startswith("e"))]
norm = lambda s: re.sub(r"[^a-z ]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())).split()
get = lambda u: subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", u], capture_output=True, text=True).stdout
code = lambda u: subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-A", "Mozilla/5.0", u], capture_output=True, text=True).stdout
out, stats = {}, {"one": 0, "none": 0, "many": 0, "nophoto": 0}
for p in todo:
    n = names.get(p, ""); want = norm(n); hits = set()
    for q in {n, " ".join(want)}:
        try: J = json.loads(get("https://site.web.api.espn.com/apis/search/v2?limit=10&query=" + urllib.parse.quote(q)))
        except Exception: continue
        for g in J.get("results", []):
            for c in g.get("contents", []):
                if c.get("type") == "player" and c.get("uid", "").startswith("s:40~l:46~a:") and norm(c.get("displayName", "")) == want:
                    hits.add(c["uid"].split("a:")[1])
        time.sleep(0.2)
    if not hits: stats["none"] += 1; continue
    if len(hits) > 1: stats["many"] += 1; continue
    e = hits.pop()
    if code(f"https://a.espncdn.com/i/headshots/nba/players/full/{e}.png") != "200": stats["nophoto"] += 1; continue
    out[p] = e; stats["one"] += 1
print("searched", len(todo), stats)
json.dump(out, open("espn_more.json", "w"))
