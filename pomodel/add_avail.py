"""Availability CEPM for the site data:
  T.late         : roster CEPM (rs-only 3-yr window) weighted by floor time in the team's last 15 regular-season games
  series[6], [7] : availability for winner / loser going INTO that series: floor time in the team's earlier playoff
                   rounds that postseason (rounds 2+), otherwise the last-15-games value
Run after make_cepm_data.py. Reads ../site/data.json, writes it back."""
import json
import numpy as np, pandas as pd

D = json.load(open("../site/data.json"))
S = D["seasons"]; tid = D["teamIds"]
CE = pd.read_csv("../cepm/cepm3_rs.csv"); cv = {(int(p), s): r for p, s, r in zip(CE.player, CE.window_end, CE.rapm)}
REPL = -2.0
P = pd.read_csv("player_game.csv", dtype={"game_id": str})
P["team"] = np.where((P.team == 1610612740) & (P.season < "2002-03"), 1610612766, P.team)


def value(pp, season):
    if pp.empty or pp.sum() <= 0: return None
    v = np.array([cv.get((int(p), season), REPL) for p in pp.index])
    return round(float(5 * (v * pp.values).sum() / pp.sum()), 3)


rs = P[P.stype == "rs"]; po = P[P.stype == "po"]
late = {}
for (season, team), g in rs.groupby(["season", "team"]):
    last = g.drop_duplicates("game_id").sort_values(["date", "game_id"]).game_id.tolist()[-15:]
    late[(season, team)] = value(g[g.game_id.isin(last)].groupby("p").secs.sum(), season)
T = D["T"]
T["late"] = [late.get((S[s], tid[a])) if t == 0 else None for a, s, t in zip(T["a"], T["s"], T["t"])]
gteams = po.groupby("game_id").team.unique()


def avail(season, team, opp, rnd):
    if rnd > 1:
        t = po[(po.season == season) & (po.team == team)]
        vs = [g for g in t.game_id.unique() if opp in gteams[g]]
        if vs:
            start = t[t.game_id.isin(vs)].date.min()
            prev = t[t.date < start]
            v = value(prev.groupby("p").secs.sum(), season)
            if v is not None: return v
    return late.get((season, team))


ser = []
for x in D["series"]:
    s, rnd, w, l = x[:4]
    ser.append(x[:6] + [avail(S[s], tid[w], tid[l], rnd), avail(S[s], tid[l], tid[w], rnd)])
D["series"] = ser
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
miss = sum(1 for x in ser if x[6] is None or x[7] is None)
print("team rows with late value:", sum(v is not None for v in T["late"]), "| series", len(ser), "missing avail", miss)
