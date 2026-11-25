"""Prop backtest: for every final game since Nov 8, fetch DraftKings' player props from ESPN, project each player from
games BEFORE that day only, and grade against his box score. Prints results by edge."""
import json, sys, os, math, time, subprocess, collections
sys.argv = ["x"]
src = open("update/bets_snap.py").read().split("os.makedirs(OUT, exist_ok=True)")[0]
ns = {"__name__": "bt", "__file__": os.path.abspath("update/bets_snap.py")}; exec(src, ns)
get, implied, payout, p_over, PROPS, MILE, CORE = ns["get"], ns["implied"], ns["payout"], ns["p_over"], ns["PROPS"], ns["MILE"], ns["CORE"]
BOX = json.load(open("bets/boxlog.json"))["games"]
games = sorted(BOX.items(), key=lambda kv: kv[1]["day"])
def profiles(cut):
    logs, team = {}, {}
    for gid, g in games:
        if g["day"] >= cut: break
        tot = {}
        for r in g["p"]:
            aid, name, ab, mn, pts, reb, ast, f3, to, oreb, fga, fta = r
            logs.setdefault(aid, {"name": name, "team": ab, "g": []}); logs[aid]["team"] = ab; logs[aid]["g"].append((g["day"], mn, pts, reb, ast, f3))
            t = tot.setdefault(ab, [0, 0]); t[0] += pts; t[1] += fga + 0.44 * fta - oreb + to
        for ab, (pts, pos) in tot.items():
            opp = g["away"] if ab == g["home"] else g["home"]
            x = team.setdefault(ab, {"pos": 0, "n": 0, "allowed": 0, "opp_pos": 0}); x["pos"] += pos; x["n"] += 1
            y = team.setdefault(opp, {"pos": 0, "n": 0, "allowed": 0, "opp_pos": 0}); y["allowed"] += pts; y["opp_pos"] += pos
    return logs, team
rows = []; cache = {}
for gid, g in games:
    if g["day"] < "2026-11-08": continue
    if g["day"] not in cache:
        logs, team = profiles(g["day"]); ns["logs"], ns["team"] = logs, team
        ns["lg_pace"] = sum(x["pos"] for x in team.values()) / max(1, sum(x["n"] for x in team.values()))
        ns["lg_drtg"] = sum(x["allowed"] for x in team.values()) / max(1, sum(x["opp_pos"] for x in team.values())) * 100
        exec('pace = lambda ab: team[ab]["pos"] / team[ab]["n"] if ab in team and team[ab]["n"] else lg_pace\ndrtg = lambda ab: team[ab]["allowed"] / team[ab]["opp_pos"] * 100 if ab in team and team[ab]["opp_pos"] else lg_drtg', ns)
        cache[g["day"]] = 1
    j = get(f"{CORE}/events/{gid}/competitions/{gid}/odds/100/propBets?limit=1000"); time.sleep(0.3)
    if not j or not j.get("items"): print("no props", gid, g["day"]); continue
    by = {}
    for it in j["items"]:
        ref = (it.get("athlete") or {}).get("$ref", ""); aid = ref.split("/athletes/")[1].split("?")[0] if "/athletes/" in ref else None
        if aid: by.setdefault((aid, it["type"]["name"]), []).append(it)
    act = {r[0]: r for r in g["p"]}
    for (aid, tname), its in by.items():
        stat = PROPS.get(tname)
        if not stat or len(its) != 2 or aid not in act: continue
        line = its[0]["current"]["target"]["value"]; o1, o2 = its[0]["odds"]["american"]["value"], its[1]["odds"]["american"]["value"]
        ms = {m["current"]["target"]["value"]: implied(m["odds"]["american"]["value"]) for m in by.get((aid, MILE[stat]), [])}
        over, under = o1, o2
        if line + 0.5 in ms and abs(implied(o2) - ms[line + 0.5]) < abs(implied(o1) - ms[line + 0.5]): over, under = o2, o1
        L = ns["logs"].get(aid)
        if not L: continue
        opp = g["away"] if L["team"] == g["home"] else g["home"]
        pj = ns["project"](aid, stat, opp)
        if not pj: continue
        r = act[aid]; v = r[4] + r[5] + r[6] if stat == "pra" else r[{"pts": 4, "reb": 5, "ast": 6, "fg3m": 7}[stat]]
        io, iu = implied(over), implied(under); q = io / (io + iu); p = p_over(pj["mu"], pj["sd"], line)
        rows.append({"day": g["day"], "stat": stat, "line": line, "q": q, "p": p, "mu": pj["mu"], "v": v, "over": over, "under": under})
json.dump(rows, open("props_bt.json", "w"))
print("props graded", len(rows), "days", len(cache))
y = [r["v"] > r["line"] for r in rows]
print(f"over hit rate {sum(y)/len(y):.3f}; market says {sum(r['q'] for r in rows)/len(rows):.3f}; model says {sum(r['p'] for r in rows)/len(rows):.3f}")
ll = lambda key: -sum(math.log(min(.99, max(.01, r[key])) if r["v"] > r["line"] else 1 - min(.99, max(.01, r[key]))) for r in rows) / len(rows)
print(f"log loss market {ll('q'):.4f} model {ll('p'):.4f}")
for a in (0.25, 0.5):
    for r in rows: r["b"] = a * r["p"] + (1 - a) * r["q"]
    print(f"blend {a}: log loss {ll('b'):.4f}")
for th in (0.04, 0.06, 0.08, 0.10, 0.12, 0.15):
    n = w = 0; u = 0.0; per = collections.Counter()
    for r in rows:
        e = r["p"] - r["q"]
        if abs(e) < th: continue
        side = e > 0; won = (r["v"] > r["line"]) if side else (r["v"] < r["line"]); n += 1; w += won
        u += payout(r["over"] if side else r["under"]) if won else -1; per[r["stat"]] += 1
    print(f"edge >= {th:.2f}: {n} bets {w}-{n-w} units {u:+.1f} ROI {u/max(n,1)*100:+.1f}%  {dict(per)}")
