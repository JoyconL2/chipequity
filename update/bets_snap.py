"""Betting board data for the owner's private picks page (not part of the public site).

Every run (hourly, with the model-picks job):
  1  today's games: the model's pregame home-win chance (dist/picks.json, saved by update/snap_picks.mjs) next to
     DraftKings' moneyline from ESPN, turned into a no-vig chance; edge = model - market.
  2  player props (points, rebounds, assists, threes, points+rebounds+assists): DraftKings' over/under lines from ESPN,
     next to a projection from this season's box scores (minutes from his last 5 games, per-minute rates blending
     season and last 10 games, adjusted for the matchup's pace and the opponent's points allowed).
  3  grading: once games are final, each game's and prop's last pregame snapshot is graded (won/lost, units at the
     saved odds, 1 unit per bet).
Props are recorded but not flagged (see PROP_EDGE). Writes bets/bets.json and keeps a box-score cache in bets/boxlog.json. usage: python update/bets_snap.py"""
import json, os, subprocess, time, math, datetime as dt
from zoneinfo import ZoneInfo
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); OUT = os.path.join(ROOT, "bets")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"; CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
ET = ZoneInfo("America/New_York"); NOW = dt.datetime.now(ET); TODAY = NOW.date()
SEASON_START = dt.date(2026, 10, 20)
GAME_EDGE = 0.05            # flag a moneyline when the model is 5+ points above the no-vig line
# Props are recorded (line, projection) but never flagged: a backtest of 6,871 DraftKings props (Nov 8-24, 2026)
# found no edge for these projections (about -6% ROI at every threshold; the lines were the better forecast).
PROP_EDGE = 9.9
PROPS = {"Total Points": "pts", "Total Rebounds": "reb", "Total Assists": "ast", "Total 3-Point Field Goals": "fg3m",
         "Total Points, Rebounds, and Assists": "pra"}
MILE = {"pts": "Points Milestones", "reb": "Rebounds Milestones", "ast": "Assists Milestones", "fg3m": "3-Point Field Goals Milestones",
        "pra": "Points + Assists + Rebounds Milestones"}

def get(url, tries=3):
    for t in range(tries):
        r = subprocess.run(["curl", "-s", "-m", "25", "-A", UA, "-H", "accept: application/json", url], capture_output=True, text=True).stdout
        try: return json.loads(r)
        except Exception: time.sleep(2 * (t + 1))
    return None
def load(name, default):
    f = os.path.join(OUT, name)
    return json.load(open(f)) if os.path.exists(f) else default
def implied(american):
    a = float(american); return 100 / (a + 100) if a > 0 else -a / (-a + 100)
def payout(american):
    a = float(american); return a / 100 if a > 0 else 100 / -a
ncdf = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
def p_over(mu, sd, line):
    """Chance of more than `line` (a .5 line) for a count with this mean and spread: negative binomial, which is
    skewed like real stat lines (books set lines near the median, below the mean). Falls back to Poisson."""
    if mu <= 0.05: return 0.0
    k = int(math.floor(line)); var = max(sd * sd, mu * 1.05)
    r = mu * mu / (var - mu); q = r / (r + mu); cdf = 0.0
    for x in range(k + 1): cdf += math.exp(math.lgamma(x + r) - math.lgamma(r) - math.lgamma(x + 1) + r * math.log(q) + x * math.log(1 - q))
    return max(0.0, min(1.0, 1 - cdf))

# a player's projection for one stat tonight (uses the profiles built below: logs, team, lg_pace, lg_drtg, pace, drtg)
def project(aid, stat, opp):
    L = logs.get(aid)
    if not L or len(L["g"]) < 5: return None
    g = L["g"]; val = lambda x: x[2] + x[3] + x[4] if stat == "pra" else x[{"pts": 2, "reb": 3, "ast": 4, "fg3m": 5}[stat]]
    mins = sum(x[1] for x in g)
    if mins < 150: return None
    rate_s = sum(val(x) for x in g) / mins; last = g[-10:]; rate_l = sum(val(x) for x in last) / sum(x[1] for x in last)
    rate = 0.5 * rate_s + 0.5 * rate_l; mpg = sum(x[1] for x in g[-5:]) / len(g[-5:])
    f = 1 + 0.5 * ((pace(L["team"]) + pace(opp)) / 2 / lg_pace - 1)                   # half the matchup's pace difference
    if stat in ("pts", "pra"): f *= 1 + 0.5 * (drtg(opp) / lg_drtg - 1)                # and half the opponent's points allowed
    mu = rate * mpg * f
    res = [val(x) - rate * x[1] for x in g]                                            # game-to-game spread around his rate
    sd = max(math.sqrt(sum(r * r for r in res) / max(1, len(res) - 1)), math.sqrt(max(mu, 0.5)))
    return {"mu": round(mu, 2), "sd": round(sd, 2), "mpg": round(mpg, 1), "n": len(g)}

os.makedirs(OUT, exist_ok=True)
B = load("bets.json", {"season": "2026-27", "games": {}, "props": {}, "updated": None})
BOX = load("boxlog.json", {"games": {}, "scanned": []})

# ---- scoreboards: today and the last few days (finals for grading and the box cache) ----
def board(d):
    j = get(f"{SITE}/scoreboard?dates={d.strftime('%Y%m%d')}") or {}
    out = []
    for e in j.get("events", []):
        c = e["competitions"][0]; tm = {x["homeAway"]: x for x in c["competitors"]}
        if (e.get("season") or {}).get("type") not in (2, 3, None): continue
        o = (c.get("odds") or [None])[0] or {}
        ml = (o.get("moneyline") or {})
        mlh = ((ml.get("home") or {}).get("close") or (ml.get("home") or {}).get("open") or {}).get("odds")
        mla = ((ml.get("away") or {}).get("close") or (ml.get("away") or {}).get("open") or {}).get("odds")
        out.append({"id": e["id"], "day": d.isoformat(), "state": c["status"]["type"]["state"], "start": e["date"],
                    "home": tm["home"]["team"]["abbreviation"], "away": tm["away"]["team"]["abbreviation"],
                    "hs": int(tm["home"].get("score") or 0), "as": int(tm["away"].get("score") or 0),
                    "mlh": mlh, "mla": mla, "spread": o.get("details"), "total": o.get("overUnder"), "book": (o.get("provider") or {}).get("name")})
    return out
days = [TODAY - dt.timedelta(days=i) for i in range(3, -1, -1)]
scan = [d for d in (SEASON_START + dt.timedelta(days=i) for i in range((TODAY - SEASON_START).days)) if d.isoformat() not in BOX["scanned"]]
boards = {d.isoformat(): board(d) for d in sorted(set(days) | set(scan))}

# ---- box-score cache (every final game this season) ----
def boxscore(gid):
    j = get(f"{SITE}/summary?event={gid}")
    if not j or "boxscore" not in j: return None
    rows = []
    for side in j["boxscore"].get("players", []):
        ab = side["team"]["abbreviation"]; st = side["statistics"][0]; lab = st["labels"]
        for a in st["athletes"]:
            if a.get("didNotPlay") or not a.get("stats"): continue
            s = dict(zip(lab, a["stats"]))
            try: mn = float(s.get("MIN") or 0)
            except ValueError: mn = 0
            if mn <= 0: continue
            f = lambda k: int(str(s.get(k, "0")).split("-")[0] or 0)
            fga = int(str(s.get("FG", "0-0")).split("-")[1] or 0); fta = int(str(s.get("FT", "0-0")).split("-")[1] or 0)
            rows.append([a["athlete"]["id"], a["athlete"]["displayName"], ab, mn, f("PTS"), f("REB"), f("AST"), int(str(s.get("3PT", "0-0")).split("-")[0] or 0),
                         f("TO"), f("OREB"), fga, fta])
    return rows
for d, gs in boards.items():
    for g in gs:
        if g["state"] == "post" and g["id"] not in BOX["games"]:
            rows = boxscore(g["id"]); time.sleep(0.2)
            if rows: BOX["games"][g["id"]] = {"day": d, "home": g["home"], "away": g["away"], "hs": g["hs"], "as": g["as"], "p": rows}
    if d < TODAY.isoformat() and all(g["state"] == "post" for g in gs) and d not in BOX["scanned"]: BOX["scanned"].append(d)

# ---- player and team profiles from the box scores ----
logs, team = {}, {}
for gid, g in sorted(BOX["games"].items(), key=lambda kv: kv[1]["day"]):
    tot = {}
    for r in g["p"]:
        aid, name, ab, mn, pts, reb, ast, f3, to, oreb, fga, fta = r
        logs.setdefault(aid, {"name": name, "team": ab, "g": []}); logs[aid]["team"] = ab; logs[aid]["name"] = name
        logs[aid]["g"].append((g["day"], mn, pts, reb, ast, f3))
        t = tot.setdefault(ab, [0, 0]); t[0] += pts; t[1] += fga + 0.44 * fta - oreb + to
    for ab, (pts, pos) in tot.items():
        opp = g["away"] if ab == g["home"] else g["home"]
        x = team.setdefault(ab, {"pos": 0, "n": 0, "allowed": 0, "opp_pos": 0}); x["pos"] += pos; x["n"] += 1
        y = team.setdefault(opp, {"pos": 0, "n": 0, "allowed": 0, "opp_pos": 0}); y["allowed"] += pts; y["opp_pos"] += pos
lg_pace = sum(x["pos"] for x in team.values()) / max(1, sum(x["n"] for x in team.values()))
lg_drtg = sum(x["allowed"] for x in team.values()) / max(1, sum(x["opp_pos"] for x in team.values())) * 100
pace = lambda ab: team[ab]["pos"] / team[ab]["n"] if ab in team and team[ab]["n"] else lg_pace
drtg = lambda ab: team[ab]["allowed"] / team[ab]["opp_pos"] * 100 if ab in team and team[ab]["opp_pos"] else lg_drtg

# ---- games: model vs market ----
picks = json.load(open(os.path.join(ROOT, "dist/picks.json")))["games"]
for d, gs in boards.items():
    for g in gs:
        G = B["games"].setdefault(g["id"], {"day": d, "home": g["home"], "away": g["away"]})
        G.update({"state": g["state"], "hs": g["hs"], "as": g["as"]})
        if g["state"] == "pre":
            pm = picks.get(g["id"], [None] * 4)[3]
            if pm is not None and g["mlh"] and g["mla"]:
                ih, ia = implied(g["mlh"]), implied(g["mla"]); q = ih / (ih + ia); e = pm - q
                G.update({"p": pm, "q": round(q, 4), "mlh": g["mlh"], "mla": g["mla"], "spread": g["spread"], "total": g["total"],
                          "edge": round(e, 4), "side": "home" if e > 0 else "away", "flag": abs(e) >= GAME_EDGE, "at": NOW.strftime("%Y-%m-%d %H:%M"), "start": g["start"]})
        elif g["state"] == "post" and "p" in G and "won" not in G:
            hw = g["hs"] > g["as"]; won = hw if G["side"] == "home" else not hw
            G["won"] = won; G["units"] = round(payout(G["mlh"] if G["side"] == "home" else G["mla"]) if won else -1, 3)

# ---- props for today's games that haven't started ----
names = {}
for g in boards.get(TODAY.isoformat(), []):
    if g["state"] != "pre": continue
    j = get(f"{CORE}/events/{g['id']}/competitions/{g['id']}/odds/100/propBets?limit=1000")
    if not j: continue
    by = {}
    for it in j.get("items", []):
        ref = (it.get("athlete") or {}).get("$ref", ""); aid = ref.split("/athletes/")[1].split("?")[0] if "/athletes/" in ref else None
        if aid: by.setdefault((aid, it["type"]["name"]), []).append(it)
    for (aid, tname), its in by.items():
        stat = PROPS.get(tname)
        if not stat or len(its) != 2: continue
        line = its[0]["current"]["target"]["value"]; o1, o2 = its[0]["odds"]["american"]["value"], its[1]["odds"]["american"]["value"]
        # which of the pair is the over: the one matching the "line+0.5 or more" milestone when DraftKings lists it, else the first
        ms = {m["current"]["target"]["value"]: implied(m["odds"]["american"]["value"]) for m in by.get((aid, MILE[stat]), [])}
        over, under = o1, o2
        if line + 0.5 in ms and abs(implied(o2) - ms[line + 0.5]) < abs(implied(o1) - ms[line + 0.5]): over, under = o2, o1
        L = logs.get(aid); tm = L["team"] if L else None
        if not L:
            if aid not in names: a = get(ref.replace("http://", "https://")) or {}; names[aid] = a.get("displayName", aid)
        opp = g["away"] if tm == g["home"] else g["home"]
        pj = project(aid, stat, opp) if tm in (g["home"], g["away"]) else None
        io, iu = implied(over), implied(under); q = io / (io + iu)
        rec = {"gid": g["id"], "day": TODAY.isoformat(), "aid": aid, "name": L["name"] if L else names.get(aid), "team": tm, "opp": opp, "stat": stat,
               "line": line, "over": over, "under": under, "q": round(q, 4), "at": NOW.strftime("%Y-%m-%d %H:%M")}
        if pj:
            p = p_over(pj["mu"], pj["sd"], line); e = p - q
            rec.update({"proj": pj["mu"], "sd": pj["sd"], "mpg": pj["mpg"], "p": round(p, 4), "edge": round(e, 4), "side": "over" if e > 0 else "under", "flag": abs(e) >= PROP_EDGE})
        B["props"][f"{g['id']}|{aid}|{stat}"] = rec
    time.sleep(0.3)

# ---- grade props from the box scores ----
for key, r in B["props"].items():
    if "won" in r or "side" not in r or r["gid"] not in BOX["games"]: continue
    row = next((x for x in BOX["games"][r["gid"]]["p"] if x[0] == r["aid"]), None)
    if row is None: r["won"] = None; continue                                          # didn't play: void
    v = row[4] + row[5] + row[6] if r["stat"] == "pra" else row[{"pts": 4, "reb": 5, "ast": 6, "fg3m": 7}[r["stat"]]]
    r["actual"] = v; won = v > r["line"] if r["side"] == "over" else v < r["line"]; r["won"] = won
    r["units"] = round(payout(r["over"] if r["side"] == "over" else r["under"]) if won else -1, 3)

B["updated"] = NOW.strftime("%Y-%m-%d %H:%M ET")
json.dump(B, open(os.path.join(OUT, "bets.json"), "w"), separators=(",", ":"))
json.dump(BOX, open(os.path.join(OUT, "boxlog.json"), "w"), separators=(",", ":"))
tg = [g for g in B["games"].values() if g.get("day") == TODAY.isoformat()]
print(f"{B['updated']}: {len(tg)} games today ({sum(1 for g in tg if g.get('flag'))} flagged), {sum(1 for r in B['props'].values() if r['day'] == TODAY.isoformat())} props today "
      f"({sum(1 for r in B['props'].values() if r['day'] == TODAY.isoformat() and r.get('flag'))} flagged); box cache {len(BOX['games'])} games")
