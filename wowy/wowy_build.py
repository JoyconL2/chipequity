"""On/off and WOWY (with or without you) for every team-season, regular season and playoffs, garbage time out.
wowy.json = { "<season index>|<team abbr index>|<0 rs / 1 po>": [ team_totals, players, pairs ] }
  team_totals = [possessions, points for, points against]
  players     = [[player k, possessions on, points for, points against, seconds on], ...]   (everyone who played)
  pairs       = [[k1, k2, possessions together, points for, points against], ...]           (12 most-used players)
Off-court and 'neither' numbers follow by subtraction.
lineups/<season>.json = { "<team abbr index>|<0 rs / 1 po>": [[k1, k2, k3, k4, k5, possessions, points for, points against], ...] }
  every five-man unit the team used (garbage time out), so the site can answer any combination: these players on
  together, those off, and the best 2- to 5-man units. Loaded only when a team page is opened."""
import sys, json, itertools, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}; kOf = {int(p): k for k, p in enumerate(D["ids"])}
T = D["T"]; amap = {}
for a, s, t in zip(T["a"], T["s"], T["t"]):
    if t == 0: amap[(s, int(D["teamIds"][a]))] = a
df = pd.read_pickle(__import__("os").environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); g = garbage_time(df).values; df = df[~g]
out = {}
for (stype, season), d in df.groupby(["season_type", "season"]):
    si = SI.get(season)
    if si is None: continue
    tt = 0 if stype == "rs" else 1
    for side, opp in (("home", "away"), ("away", "home")):
        sub = d[[f"{side}_team", f"{side}_players", f"{side}_poss", f"{opp}_poss", f"{side}_pts", f"{opp}_pts", "secs"]].values
        for team, grp in itertools.groupby(sorted(sub, key=lambda r: r[0]), key=lambda r: r[0]):
            a = amap.get((si, int(team)))
            if a is None: continue
            key = f"{si}|{a}|{tt}"; e = out.setdefault(key, {"tot": np.zeros(3), "pl": {}, "pair": {}, "lu": {}})
            for _, pl, p1, p2, pf, pa, sc in grp:
                poss = (p1 + p2) / 2
                if poss <= 0: continue
                ks = sorted({kOf[int(x)] for x in pl.split("-") if int(x) in kOf})
                e["tot"] += (poss, pf, pa)
                if len(ks) == 5: v = e["lu"].setdefault(tuple(ks), np.zeros(3)); v += (poss, pf, pa)
                for k in ks:
                    v = e["pl"].setdefault(k, np.zeros(4)); v += (poss, pf, pa, sc)
                for k1, k2 in itertools.combinations(ks, 2):
                    v = e["pair"].setdefault((k1, k2), np.zeros(3)); v += (poss, pf, pa)
    print(stype, season, flush=True)
J = {}
for key, e in out.items():
    pl = sorted(e["pl"].items(), key=lambda kv: -kv[1][0]); top = {k for k, _ in pl[:12]}
    pairs = [[k1, k2, round(float(v[0]), 1), int(v[1]), int(v[2])] for (k1, k2), v in e["pair"].items() if k1 in top and k2 in top and v[0] >= 25]
    J[key] = [[round(float(e["tot"][0]), 1), int(e["tot"][1]), int(e["tot"][2])],
              [[k, round(float(v[0]), 1), int(v[1]), int(v[2]), int(v[3])] for k, v in pl], pairs]
json.dump(J, open("wowy.json", "w"), separators=(",", ":"))
import os
os.makedirs("lineups", exist_ok=True); LU = {}
for key, e in out.items():
    si, a, tt = key.split("|")
    LU.setdefault(int(si), {})[f"{a}|{tt}"] = [[*k, round(float(v[0]), 1), int(v[1]), int(v[2])] for k, v in sorted(e["lu"].items(), key=lambda kv: -kv[1][0]) if v[0] > 0]
for si, d in LU.items():
    json.dump(d, open(f"lineups/{S[si]}.json", "w"), separators=(",", ":"))
print("lineup files:", len(LU), "| e.g.", S[max(LU)], round(os.path.getsize(f"lineups/{S[max(LU)]}.json") / 1e6, 2), "MB")
import os; print(len(J), "team-seasons", round(os.path.getsize("wowy.json") / 1e6, 2), "MB")
