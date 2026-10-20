"""Append the season being played to the site data, the same way site/extend_1996.py built the 1990s seasons:
players, teams, records, league averages and (once the playoffs start) playoff series, all from NBA.com play-by-play.
Seasons already in the base file are untouched; new players get new indices at the end, so every existing index stays.

usage: python update/add_season.py <base data.json> <season> <work dir> <out data.json>
  work dir holds box_<season>_<rs|po>.csv (stintbuild/box_from_live.py), stints_<season>_<rs|po>.csv,
  games.csv and names.json (update/fetch_season.py)"""
import json, os, sys
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stintbuild")); sys.path.insert(0, os.path.join(ROOT, "site"))
from derive_box import derive
from league_rows import league_row

base, season, wd, out = sys.argv[1:5]
d = json.load(open(base))
assert season not in d["seasons"], f"{season} is already in {base}"
assert int(season[:4]) == int(d["seasons"][-1][:4]) + 1, "seasons must be added in order"
si = len(d["seasons"])
ids = d["ids"]; names = d["names"]; kidx = {int(pid): k for k, pid in enumerate(ids)}
nm_new = json.load(open(os.path.join(wd, "names.json"))) if os.path.exists(os.path.join(wd, "names.json")) else {}
T0 = pd.DataFrame(d["T"]); T0 = T0[T0.s == si - 1]
tid2a = {int(d["teamIds"][a]): int(a) for a in T0.a}          # this season's franchises = last season's
G_all = pd.read_csv(os.path.join(wd, "games.csv"), dtype={"gid": str})


def kid(pid):
    pid = int(pid)
    if pid not in kidx:
        kidx[pid] = len(ids); ids.append(pid); names.append(nm_new.get(str(pid), str(pid)))
    return kidx[pid]


def stint_len(path):
    """average minutes per check-in (same as load/stint_len.py)"""
    if not os.path.exists(path): return {}
    x = pd.read_csv(path, dtype={"game_id": str}, usecols=["game_id", "period", "start_sec", "end_sec", "home_players", "away_players"])
    x = x.sort_values(["game_id", "period", "start_sec"], ascending=[True, True, False]).reset_index(drop=True)
    x["row"] = np.arange(len(x)); x["dur"] = (x.start_sec - x.end_sec).clip(lower=0)
    parts = []
    for side in ("home", "away"):
        y = x[["game_id", "row", "dur", f"{side}_players"]].rename(columns={f"{side}_players": "pl"}); y["side"] = side
        parts.append(y.assign(p=y.pl.str.split("-")).explode("p")[["game_id", "side", "row", "dur", "p"]])
    y = pd.concat(parts); y["p"] = y.p.astype(int)
    rows = x[["game_id", "row"]].copy(); rows["prev"] = rows.groupby("game_id").row.shift(1)
    y = y.merge(rows[["row", "prev"]], on="row"); present = set(zip(y.side, y.row, y.p))
    y["entry"] = [not ((s, pr, p) in present) if pr == pr else True for s, pr, p in zip(y.side, y.prev, y.p)]
    g = y.groupby("p").agg(sec=("dur", "sum"), entries=("entry", "sum"))
    return {int(p): round(float(r.sec / 60 / max(r.entries, 1)), 2) for p, r in g.iterrows() if r.sec >= 600}


STL = stint_len(os.path.join(wd, f"stints_{season}_rs.csv"))
P_new = {k: [] for k in d["P"]}; T_new = {k: [] for k in d["T"]}; series_new = []
for t, st in ((0, "rs"), (1, "po")):
    f = os.path.join(wd, f"box_{season}_{st}.csv")
    if not os.path.exists(f) or os.path.getsize(f) < 100: continue
    W = pd.read_csv(f).fillna(0); D = derive(W)
    G = G_all[G_all.stype == st].rename(columns={})[["gid", "home", "away", "hp", "ap"]].copy()
    G["gid"] = G.gid.astype(int)
    # ---- players ----
    for i, r in D.iterrows():
        if r.SecondsPlayed < 60 or int(r.TeamId) not in tid2a or not (0 < r.EntityId < 1610612700): continue
        fga = r.FG2A + r.FG3A; tov = r.LiveBallTurnovers + r.DeadBallTurnovers
        row = dict(p=kid(r.EntityId), s=si, t=t, tm=tid2a[int(r.TeamId)], gp=int(r.GamesPlayed), sec=int(r.SecondsPlayed),
                   pts=int(r.Points), reb=int(r.OffRebounds + r.DefRebounds), ast=int(r.Assists), stl=int(r.Steals), blk=int(r.Blocks),
                   tov=int(tov), fg2a=int(r.FG2A), fg3a=int(r.FG3A), fg3m=int(r.FG3M), fta=int(r.FTA),
                   pos=int(round((r.OffPoss + r.DefPoss) / 2)),
                   usg=round(float((fga + 0.44 * r.FTA + tov) / max(r.OffPoss, 1) * 100 / 1.148), 1),
                   oo=round(float((r.PlusMinus + r.OpponentPoints) / max(r.OffPoss, 1) * 100), 1),
                   od=round(float(r.OpponentPoints / max(r.DefPoss, 1) * 100), 1),
                   stint=STL.get(int(r.EntityId)))
        for k in P_new: P_new[k].append(row.get(k))
    # ---- teams ----
    cols = lambda end: [c for c in W.columns if c.endswith(end)]
    for tid, x in W.groupby("TeamId"):
        if int(tid) not in tid2a: continue
        dx = D.loc[x.index]
        secs = (x.SecondsPlayedOff.sum() + x.SecondsPlayedDef.sum()) / 5
        op, dp = x.OffPoss.sum() / 5, x.DefPoss.sum() / 5
        mine = G[(G.home == tid) | (G.away == tid)]
        won = ((mine.home == tid) & (mine.hp > mine.ap)) | ((mine.away == tid) & (mine.ap > mine.hp))
        pts = int(dx.Points.sum()); opp = int(round(x.OpponentPoints.sum() / 5))
        oreb_o = x[cols("OffReboundedOpportunities")].sum().sum() / 5; oreb_d = x[cols("OffRebounded")].sum().sum() / 5
        dreb_o = x[cols("DefReboundOpportunities")].sum().sum() / 5
        sf = x["Shooting Fouls"].sum() if "Shooting Fouls" in x else 0
        row = dict(a=tid2a[int(tid)], s=si, t=t, gp=len(mine), pts=pts, opp=opp, op=int(round(op)), dp=int(round(dp)),
                   fg2a=int(dx.FG2A.sum()), fg2m=int(dx.FG2M.sum()), fg3a=int(dx.FG3A.sum()), fg3m=int(dx.FG3M.sum()), fta=int(dx.FTA.sum()),
                   tov=int((dx.LiveBallTurnovers + dx.DeadBallTurnovers).sum()), stl=int(dx.Steals.sum()), blk=int(dx.Blocks.sum()),
                   sf=int(sf), pace=round(float((op + dp) / 2 / max(secs / 2880, 1e-9)), 1),
                   ts=round(float(pts / max(2 * (dx.FG2A.sum() + dx.FG3A.sum() + 0.44 * dx.FTA.sum()), 1)), 4),
                   efg=round(float((dx.FG2M.sum() + 1.5 * dx.FG3M.sum()) / max(dx.FG2A.sum() + dx.FG3A.sum(), 1)), 4),
                   oreb=round(float(oreb_d / max(oreb_o, 1) / 0.963), 4), dreb=round(float(dx.DefRebounds.sum() / max(dreb_o, 1) / 1.017), 4),
                   sq=None, rim=round(float(dx.AtRimFGA.sum() / max(dx.FG2A.sum() + dx.FG3A.sum(), 1)), 4),
                   w=int(won.sum()), l=int(len(mine) - won.sum()), late=None)
        for k in T_new: T_new[k].append(row.get(k))
    if t == 0:
        lg = league_row(f, season, len(G))
    else:   # playoff series so far (round = order within each team's run)
        G["pair"] = [tuple(sorted((h, a))) for h, a in zip(G.home, G.away)]
        G["winner"] = np.where(G.hp > G.ap, G.home, G.away); runs = {}
        for pair, x in sorted(G.groupby("pair"), key=lambda kv: kv[1].gid.min()):
            c = x.winner.value_counts(); w = int(c.index[0]); l = int(pair[0] if pair[1] == w else pair[1])
            if w not in tid2a or l not in tid2a: continue
            rnd = max(runs.get(w, 0), runs.get(l, 0)) + 1; runs[w] = runs[l] = rnd
            series_new.append([si, rnd, tid2a[w], tid2a[l], int(c.iloc[0]), int(c.iloc[1]) if len(c) > 1 else 0])

if not P_new["p"]: sys.exit(f"no {season} games to add")
for k in d["P"]: d["P"][k] = d["P"][k] + P_new[k]
for k in d["T"]: d["T"][k] = d["T"][k] + T_new[k]
d["series"] = d["series"] + series_new
d["league"] = d["league"] + [lg]
d["seasons"] = d["seasons"] + [season]
d["ids"], d["names"] = ids, names
rs = G_all[G_all.stype == "rs"]
d["inprog"] = {"season": season, "games": int(len(rs)), "team_games": round(2 * len(rs) / max(len(tid2a), 1), 1),
               "through": str(G_all.date.max()) if len(G_all) else "", "playoffs": bool(series_new),
               "done": bool(len(rs) >= 1230 and any(r[1] == 4 and r[4] == 4 for r in series_new))}
json.dump(d, open(out, "w"), separators=(",", ":"), allow_nan=False)
print(f"{season}: {len(P_new['p'])} player rows, {len(T_new['a'])} team rows, {len(series_new)} series, {len(ids)} players in all"
      f" | through {d['inprog']['through']} ({d['inprog']['team_games']} games per team){' | season complete' if d['inprog']['done'] else ''}")
