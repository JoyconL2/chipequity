"""On/off and WOWY (with or without you) for every team-season, regular season and playoffs, garbage time out.
wowy.json = { "<season index>|<team abbr index>|<0 rs / 1 po>": [ team_totals, players, pairs ] }
  team_totals = [possessions, points for, points against]
  players     = [[player k, possessions on, points for, points against, seconds on], ...]   (everyone who played)
  pairs       = [[k1, k2, possessions together, points for, points against], ...]           (12 most-used players)
Off-court and 'neither' numbers follow by subtraction.
lineups/<season>.json = { "<team abbr index>|<0 rs / 1 po>": [[k1, k2, k3, k4, k5, possessions, points for, points against], ...] }
  playoff rows add [.., opp offense x poss, opp defense x poss]: the opponents' regular-season offense / defense vs
  league per 100 (non-garbage, + = good), possession-weighted, so the site can show opponent-adjusted playoff results
  every five-man unit the team used (garbage time out), so the site can answer any combination: these players on
  together, those off, and the best 2- to 5-man units. Loaded only when a team page is opened."""
import sys, json, itertools, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
D = json.load(open("../site/data.json")); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}; kOf = {int(p): k for k, p in enumerate(D["ids"])}
T = D["T"]; amap = {}
for a, s, t in zip(T["a"], T["s"], T["t"]):
    if t == 0: amap[(s, int(D["teamIds"][a]))] = a
df = pd.read_pickle(__import__("os").environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); g = garbage_time(df).values; df = df[~g]
# each team's regular-season strength vs league per 100 (non-garbage): (offense, defense), + = good (as load/po_lead.py)
TSR = {}
for season, d in df[df.season_type == "rs"].groupby("season"):
    lg = 100 * (d.home_pts.sum() + d.away_pts.sum()) / (d.home_poss.sum() + d.away_poss.sum()); acc = {}
    for side, opp in (("home", "away"), ("away", "home")):
        q = d.groupby(f"{side}_team")[[f"{side}_pts", f"{opp}_pts", f"{side}_poss", f"{opp}_poss"]].sum()
        for t, r in q.iterrows():
            a_ = acc.setdefault(int(t), np.zeros(4)); a_ += r.values
    for t, a_ in acc.items(): TSR[(season, t)] = (100 * a_[0] / a_[2] - lg, lg - 100 * a_[1] / a_[3])
out = {}
for (stype, season), d in df.groupby(["season_type", "season"]):
    si = SI.get(season)
    if si is None: continue
    tt = 0 if stype == "rs" else 1
    for side, opp in (("home", "away"), ("away", "home")):
        sub = d[[f"{side}_team", f"{side}_players", f"{side}_poss", f"{opp}_poss", f"{side}_pts", f"{opp}_pts", "secs", f"{opp}_team"]].values
        for team, grp in itertools.groupby(sorted(sub, key=lambda r: r[0]), key=lambda r: r[0]):
            a = amap.get((si, int(team)))
            if a is None: continue
            key = f"{si}|{a}|{tt}"; e = out.setdefault(key, {"tot": np.zeros(3), "pl": {}, "pair": {}, "lu": {}})
            for _, pl, p1, p2, pf, pa, sc, ot in grp:
                poss = (p1 + p2) / 2
                if poss <= 0: continue
                ks = sorted({kOf[int(x)] for x in pl.split("-") if int(x) in kOf})
                e["tot"] += (poss, pf, pa)
                if len(ks) == 5:
                    oo, od = TSR.get((season, int(ot)), (0.0, 0.0)) if tt else (0.0, 0.0)
                    v = e["lu"].setdefault(tuple(ks), np.zeros(5)); v += (poss, pf, pa, poss * oo, poss * od)
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
    LU.setdefault(int(si), {})[f"{a}|{tt}"] = [[*k, round(float(v[0]), 1), int(v[1]), int(v[2]), *([round(float(v[3]), 1), round(float(v[4]), 1)] if tt == "1" else [])] for k, v in sorted(e["lu"].items(), key=lambda kv: -kv[1][0]) if v[0] > 0]
for si, d in LU.items():
    json.dump(d, open(f"lineups/{S[si]}.json", "w"), separators=(",", ":"))
print("lineup files:", len(LU), "| e.g.", S[max(LU)], round(os.path.getsize(f"lineups/{S[max(LU)]}.json") / 1e6, 2), "MB")
import os; print(len(J), "team-seasons", round(os.path.getsize("wowy.json") / 1e6, 2), "MB")
