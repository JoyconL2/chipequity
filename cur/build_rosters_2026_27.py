"""2026-27 rosters for the site when ESPN's live feed doesn't load.
last season's rosters (main team by minutes) - players who left + players who arrived (AP 2026 offseason
player-movement tracker, moves_2026.txt) + stars returning from a lost season; then trimmed to 15:
every arrival is kept, returning players fill the rest by last season's minutes per game."""
import json, re, unicodedata
import pandas as pd
D = json.load(open("../site/data.json")); C = D["cur"]
ids = [int(x) for x in D["ids"]]
norm = lambda n: re.sub(r"\s+", " ", re.sub(r"\b(jr|sr|ii|iii|iv)\b", " ", re.sub(r"[,'’`-]", " ", unicodedata.normalize("NFD", n).encode("ascii", "ignore").decode().lower().replace(".", "")))).strip()
recent = {p[0] for p in C["players"]}                       # active last season (or with a current CEPM window)
byname = {}
for k, n in enumerate(D["names"]):
    key = norm(n); pid = ids[k]
    if key not in byname or (pid in recent and byname[key] not in recent): byname[key] = pid
ALIAS = {"nicolas claxton": "nic claxton"}
find = lambda n: byname.get(ALIAS.get(norm(n), norm(n)))
mpg = {p[0]: (p[3] or 0) for p in C["players"]}
moves = {}
for line in open("moves_2026.txt"):
    ab, add, left = [x.strip() for x in line.split("|")]
    moves[ab] = ([x.strip() for x in add.split(",") if x.strip()], [x.strip() for x in left.split(",") if x.strip()])
RETURNING = {"Kyrie Irving": "DAL", "Damian Lillard": "POR", "Fred VanVleet": "HOU", "Tyrese Haliburton": "IND"}   # missed 2025-26 injured
# last season's rosters: each player's main team by minutes in 2025-26 (straight from the season data)
_P = D["P"]; _li = len(D["seasons"]) - 1
_r = pd.DataFrame({k: _P[k] for k in ("p", "s", "t", "tm", "sec")}); _r = _r[(_r.t == 0) & (_r.s == _li)]
_main = _r.sort_values("sec").groupby("p").tail(1)
roster = {}
for r in _main.itertuples(): roster.setdefault(D["abbrs"][r.tm], set()).add(ids[r.p])
arrived = {ab: set() for ab in roster}; new_names = {ab: [] for ab in roster}; issues = []
for ab, (add, left) in moves.items():
    for n in left:
        pid = find(n)
        if pid is None: continue
        for t in roster: roster[t].discard(pid)
for ab, (add, left) in moves.items():
    for n in add:
        pid = find(n)
        if pid is None: new_names[ab].append(n); continue
        for t in roster: roster[t].discard(pid)
        roster[ab].add(pid); arrived[ab].add(pid)
for n, ab in RETURNING.items():
    pid = find(n); assert pid is not None, n
    for t in roster: roster[t].discard(pid)
    roster[ab].add(pid); arrived[ab].add(pid)
# two-way contracts (Yardbarker 2026-27 two-way tracker, 2026-07-07): listed on the roster, not counted toward the 15
TW = {}
for line in open("two_way_2026.txt"):
    ab, names = line.split(":", 1); TW[ab.strip()] = {norm(n) for n in names.split(",") if n.strip()}
tw_all = set().union(*TW.values())
is_tw = lambda ab, pid=None, name=None: norm(name if name else nm_of[pid]) in TW.get(ab, set())
nm_of = {i: D["names"][k] for k, i in enumerate(ids)}
out = {}
for ab in roster:
    tw_ids = [p for p in roster[ab] if is_tw(ab, pid=p)]; tw_new = [n for n in new_names[ab] if is_tw(ab, name=n)]
    reg_new = [n for n in new_names[ab] if n not in tw_new]
    keep = sorted(p for p in arrived[ab] if p not in tw_ids); room = max(0, 15 - len(keep) - len(reg_new))
    rest = sorted(roster[ab] - arrived[ab] - set(tw_ids), key=lambda p: -mpg.get(p, 0))[:room]
    out[ab] = {"ids": keep + rest, "new": reg_new, "two_way": sorted(tw_ids), "two_way_new": tw_new}
# verified rosters where a full current list is known (replaces the moves-based guess for that team)
VERIFIED = {"PHI": ["Joel Embiid", "Jaylen Brown", "Tyrese Maxey", "VJ Edgecombe", "Dean Wade", "Anfernee Simons", "LeBron James",
                    "Labaron Philon", "Jabari Walker", "Dominick Barlow", "Ariel Hukporti", "Dalen Terry", "Adem Bona", "Justin Edwards",
                    "Kentavious Caldwell-Pope"]}     # Bleacher Report 76ers payroll (2026-27) + KCP (AP tracker); Broome moved to LAC
for ab, names in VERIFIED.items():
    out[ab]["ids"] = [find(n) for n in names if find(n) is not None]; out[ab]["new"] = [n for n in names if find(n) is None]
json.dump({"source": "AP 2026 NBA offseason player-movement tracker, applied to 2025-26 rosters", "date": "2026-10-16", "two_way_source": "Yardbarker 2026-27 two-way contract tracker, 2026-07-07", "two_way_names": sorted(tw_all), "teams": out}, open("rosters_2026_27.json", "w"), indent=1)
nm = {i: D["names"][k] for k, i in enumerate(ids)}
for ab in ("PHI", "MIA", "IND", "LAL", "BOS", "LAC"):
    print(ab, len(out[ab]["ids"]) + len(out[ab]["new"]), ", ".join(nm[p] for p in out[ab]["ids"]), "| new:", ", ".join(out[ab]["new"]), "| two-way:", ", ".join([nm[p] for p in out[ab]["two_way"]] + out[ab]["two_way_new"]))
