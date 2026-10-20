"""Teams per player-season (regular season), for players who played for more than one team that season:
data.json ptm = [[k, season_index, [[abbr_index, games], ...]], ...] in the order he played for them."""
import json, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}
kOf = {int(p): k for k, p in enumerate(D["ids"])}
T = D["T"]; amap = {}
for a, s, t in zip(T["a"], T["s"], T["t"]):
    if t == 0: amap[(s, D["teamIds"][a])] = a
G = pd.read_csv("../pomodel/player_game.csv", dtype={"game_id": str}); G = G[(G.stype == "rs") & (G.secs > 0)]
g = G.groupby(["p", "season", "team"]).agg(gp=("game_id", "nunique"), first=("date", "min")).reset_index()
multi = g.groupby(["p", "season"]).team.transform("nunique") > 1
out, miss = [], 0
for (p, s), x in g[multi].groupby(["p", "season"]):
    k = kOf.get(int(p)); si = SI.get(s)
    if k is None or si is None: continue
    x = x.sort_values("first"); teams = [[amap.get((si, int(t))), int(n)] for t, n in zip(x.team, x.gp)]
    if any(a is None for a, _ in teams): miss += 1; continue
    out.append([k, si, teams])
D["ptm"] = out; json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
nm = D["names"]; print(len(out), "multi-team seasons, unmapped", miss)
for r in out:
    if nm[r[0]] in ("Kevin Durant", "James Harden", "Russell Westbrook"): print(nm[r[0]], S[r[1]], [(D["abbrs"][a], n) for a, n in r[2]])
