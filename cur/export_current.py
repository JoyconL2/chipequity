"""Add the current-season model to data.json under its own key ("cur"), separate from the historical model.
  cur.params   : fitted coefficients + backtest (cur_params.json)
  cur.players  : [nba_id, name, prior CEPM, last-season MPG, last-season GP] for everyone with last-season data
  cur.fallback : {abbr: [nba_id, ...]} last season's main team, used only if the live roster feed fails
  cur.starts   : {nba_id: games started last season} (first lineup of every game)
  cur.proj     : projected net rating + record model (proj_final.py)
  players[5]   : 3-year CEPM ending last season, 2-year if no 3-year window (the projection's input)
  players[6,7] : MPG and GP the season before last (returning-star rule)
  players[8]   : 3-year CEPM ending the season before last (healthy form when last season was under 50 games)
  cur.market   : current market win totals (shown beside the projection, not blended in)"""
import json, os
import numpy as np, pandas as pd
D = json.load(open("../site/data.json"))
S = D["seasons"]
# Is the newest season in the data still being played? (a full regular season is 1,230 games)
T = D["T"]; _last = len(S) - 1
_games = sum(g for g, s_, t in zip(T["gp"], T["s"], T["t"]) if s_ == _last and t == 0) / 2
IN_PROGRESS = _games < 1200 or os.environ.get("FORCE_IN_PROGRESS") == "1"
# CURRENT = the season the Live Feed is about; PRIOR = the last finished season (the projection's inputs)
CURRENT = S[-1] if IN_PROGRESS else f"{int(S[-1][:4]) + 1}-{str(int(S[-1][:4]) + 2)[-2:]}"
LAST = S[-2] if IN_PROGRESS else S[-1]; li = S.index(LAST)
prm = json.load(open("cur_params.json"))
cep = pd.read_csv("../cepm/cepm3_rs.csv"); cep = cep[cep.window_end == LAST].set_index("player").rapm.to_dict()
c2w = pd.read_csv("../cepm/disp2.csv"); c2w = c2w[c2w.window_end == LAST].set_index("player").rapm.to_dict()
c3w = pd.read_csv("../cepm/disp3.csv"); c3w = c3w[c3w.window_end == LAST].set_index("player").rapm.to_dict()
c2w = {p: c3w.get(p, v) for p, v in c2w.items()} | {p: v for p, v in c3w.items()}
c3p = pd.read_csv("../cepm/disp3.csv"); c3p = c3p[c3p.window_end == S[li - 1]].set_index("player").rapm.to_dict()   # healthy-form window   # projection input: 3-year CEPM (2-year if no 3-year window)
P = D["P"]
rows = pd.DataFrame({"k": P["p"], "s": P["s"], "t": P["t"], "tm": P["tm"], "gp": P["gp"], "sec": P["sec"]})
rows_all = rows.copy()
rows = rows[(rows.t == 0) & (rows.s == li)]
prv = rows_all[(rows_all.t == 0) & (rows_all.s == li - 1)].groupby("k").agg(gp=("gp", "sum"), sec=("sec", "sum"))   # the season before last
prev2 = {int(D["ids"][k]): (round(r.sec / 60 / max(r.gp, 1), 1), int(r.gp)) for k, r in prv.iterrows()}
tot = rows.groupby("k").agg(gp=("gp", "sum"), sec=("sec", "sum"))
main = rows.sort_values("sec").groupby("k").tail(1)
players, seen = [], set()
for k, r in tot.iterrows():
    pid = int(D["ids"][k]); seen.add(pid)
    players.append([pid, D["names"][k], round(cep[pid], 2) if pid in cep else None, round(r.sec / 60 / max(r.gp, 1), 1), int(r.gp),
                    round(c2w[pid], 2) if pid in c2w else None, *prev2.get(pid, (None, 0)), round(c3p[pid], 2) if pid in c3p else None])
for pid, v in cep.items():                       # CEPM but no regular-season games last year (rare)
    if int(pid) not in seen and int(pid) in set(map(int, D["ids"])):
        k = list(map(int, D["ids"])).index(int(pid)); players.append([int(pid), D["names"][k], round(v, 2), None, 0, round(c2w[pid], 2) if pid in c2w else None, *prev2.get(int(pid), (None, 0)), round(c3p[int(pid)], 2) if int(pid) in c3p else None])
fallback = {}
for r in main.itertuples(): fallback.setdefault(D["abbrs"][r.tm], []).append(int(D["ids"][r.k]))
# games started last season: the first five on the floor for each team in every game (NBA.com play-by-play stints)
st = pd.read_csv(f"../stints/stints_{LAST}_rs.csv", dtype={"game_id": str})
first = st.sort_values(["game_id", "period", "start_sec"], ascending=[True, True, False]).groupby("game_id").head(1)
starts = {}
for h, a in zip(first.home_players, first.away_players):
    for x in str(h).split("-") + str(a).split("-"): starts[int(x)] = starts.get(int(x), 0) + 1
R27 = json.load(open("rosters_2026_27.json")) if (os.path.exists("rosters_2026_27.json") and CURRENT == "2026-27" and not IN_PROGRESS) else None
now = {}
if IN_PROGRESS:
    # rosters and starts come from the season being played: each player's team with the most minutes so far
    cur_rows = rows_all[(rows_all.t == 0) & (rows_all.s == _last)]
    fallback = {}
    for r in cur_rows.sort_values("sec").groupby("k").tail(1).itertuples(): fallback.setdefault(D["abbrs"][r.tm], []).append(int(D["ids"][r.k]))
    st = pd.read_csv(f"../stints/stints_{S[-1]}_rs.csv", dtype={"game_id": str})
    first = st.sort_values(["game_id", "period", "start_sec"], ascending=[True, True, False]).groupby("game_id").head(1)
    starts = {}
    for h, a in zip(first.home_players, first.away_players):
        for x in str(h).split("-") + str(a).split("-"): starts[int(x)] = starts.get(int(x), 0) + 1
    # record + net rating so far, from the season's own data (used when the live standings feed doesn't load)
    for a, s_, t, w, l, pts, opp, op, dp in zip(T["a"], T["s"], T["t"], T["w"], T["l"], T["pts"], T["opp"], T["op"], T["dp"]):
        if s_ == _last and t == 0 and w is not None: now[D["abbrs"][a]] = [w, l, w + l, round(100 * pts / op - 100 * opp / dp, 2)]
if R27:                                                   # rosters from reported offseason moves replace last season's
    fallback = {ab: v["ids"] + [{"name": n} for n in v["new"]] + [{"id": x, "tw": 1} for x in v.get("two_way", [])] + [{"name": n, "tw": 1} for n in v.get("two_way_new", [])]
                for ab, v in R27["teams"].items()}
_have = {pl[0] for pl in players}; _ids = [int(x) for x in D["ids"]]
for _ab, _lst in fallback.items():                     # players on a roster with NBA history but no recent data
    for x in _lst:
        x = x["id"] if isinstance(x, dict) and "id" in x else x
        if isinstance(x, int) and x not in _have:
            players.append([x, D["names"][_ids.index(x)], None, None, 0, None, *prev2.get(x, (None, 0)), c3p.get(x)]); _have.add(x)
# last season's roster value per team (standings-first projection): each player's share of that team's
# minutes last season x 5 x the same CEPM rating the projection uses (3-year, 2-year if no 3-year window)
_pg = pd.read_csv("../pomodel/player_game.csv", dtype={"game_id": str}); _pg = _pg[(_pg.stype == "rs") & (_pg.season == LAST)]
_tm = _pg.groupby(["team", "p"]).secs.sum().reset_index(); _tt = _tm.groupby("team").secs.sum()
_id2ab = {int(D["teamIds"][a]): D["abbrs"][a] for a, s_, t_ in zip(T["a"], T["s"], T["t"]) if s_ == li and t_ == 0}   # last season's names
xprev, core = {}, {}
for t, g in _tm.groupby("team"):
    ab = _id2ab.get(int(t))
    if ab is None: continue
    sh = g.secs.values / _tt[t] * 5; v = np.array([c2w.get(int(p), np.nan) for p in g.p]); k = ~np.isnan(v)
    xprev[ab] = round(float((sh[k] * v[k]).sum()), 3)
    top = g.sort_values("secs", ascending=False).head(8)          # last season's core: top-8 minute players (continuity prior)
    core[ab] = [[int(p), round(float(x) / 60, 1)] for p, x in zip(top.p, top.secs)]
mk = f"market/win_totals_{CURRENT}.csv"
ek = f"espn/bpi_{CURRENT}.csv"     # ESPN BPI projected wins (the top 10 published; the page loads all 30 live from ESPN when it can)
D["cur"] = {"season": CURRENT, "xprev": xprev, "core": core, "prior": LAST, "in_progress": IN_PROGRESS, "now": now, "params": prm, "players": players, "fallback": fallback, "fallback_src": (R27["source"] + ", " + R27["date"]) if R27 else (f"{CURRENT} games so far" if IN_PROGRESS else f"{LAST} rosters"), "two_way": R27["two_way_names"] if R27 else [], "starts": {str(k): v for k, v in starts.items()}, "proj": json.load(open("proj_params.json")), "espn": {"wins": pd.read_csv(ek).set_index("abbr").wins.to_dict(), "source": "ESPN BPI projected wins", "date": "2026-10-07", "via": "Last Word on Sports"} if os.path.exists(ek) else None, "market": {"wins": pd.read_csv(mk).set_index("abbr").wins.to_dict(), "source": "Kalshi projected wins", "date": "2026-07-29"} if os.path.exists(mk) else None}
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
print("cur:", D["cur"]["season"], "| in progress:", IN_PROGRESS, "| prior:", LAST, "| players", len(players), "with CEPM", sum(p[2] is not None for p in players), "| fallback teams", len(fallback))
