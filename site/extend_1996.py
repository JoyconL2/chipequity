"""Add 1996-97 .. 1999-00 to the site data (players, teams, records, playoff series, league averages),
built from the play-by-play archive. Input: data.json (2000-01 on). Output: data.json with 30 seasons.
Every existing season index shifts by 4."""
import json, sys, tarfile
import numpy as np, pandas as pd
sys.path.insert(0, "../stintbuild")
from derive_box import derive

NEW = ["1996-97", "1997-98", "1998-99", "1999-00"]
SH = len(NEW)
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "data.json"))
assert d["seasons"][0] == "2000-01", "already extended?"
ids = d["ids"]; names = d["names"]; kidx = {pid: k for k, pid in enumerate(ids)}
nm96 = json.load(open("../src96/names_pre2000.json"))
nm96.setdefault("775", "Melvin Booker")   # only appears as "Booker" in the 1996-97 feed
T0 = pd.DataFrame(d["T"]); T0 = T0[T0.s == 0]
tid2a = {d["teamIds"][a]: a for a in T0.a}
tid2a[1610612740] = tid2a[1610612766]          # Hornets id mix-ups in old feeds
for a, t in zip(d["abbrs"], d["teamIds"]):     # any franchise not in 2000-01
    tid2a.setdefault(t, d["abbrs"].index(a))


def kid(pid):
    if pid not in kidx:
        kidx[pid] = len(ids); ids.append(pid); names.append(nm96.get(str(pid), str(pid)))
    return kidx[pid]


def games(year, po):
    """final score, home/away team ids and date order for every game, straight from the pbp file."""
    p = "po_" if po else ""
    with tarfile.open(f"../nbadata/datasets/nbastats_{p}{year}.tar.xz") as t:
        df = pd.read_csv(t.extractfile(t.getmembers()[0]), dtype=str, keep_default_na=False,
                         usecols=["GAME_ID", "EVENTNUM", "HOMEDESCRIPTION", "VISITORDESCRIPTION", "PLAYER1_TEAM_ID", "SCORE"])
    out = []
    for g, x in df.groupby("GAME_ID", sort=True):
        h = x[(x.HOMEDESCRIPTION != "") & (x.VISITORDESCRIPTION == "") & (x.PLAYER1_TEAM_ID != "")].PLAYER1_TEAM_ID
        v = x[(x.VISITORDESCRIPTION != "") & (x.HOMEDESCRIPTION == "") & (x.PLAYER1_TEAM_ID != "")].PLAYER1_TEAM_ID
        sc = x[x.SCORE.str.contains(" - ")].SCORE
        if h.empty or v.empty or sc.empty: continue
        a_, h_ = (int(s) for s in sc.iloc[-1].split(" - "))
        H, V = int(h.mode().iloc[0]), int(v.mode().iloc[0])
        H = 1610612766 if H == 1610612740 else H; V = 1610612766 if V == 1610612740 else V
        out.append((int(g), H, V, h_, a_))
    return pd.DataFrame(out, columns=["gid", "home", "away", "hp", "ap"])


P_new = {k: [] for k in d["P"]}; T_new = {k: [] for k in d["T"]}; series_new = []; league_new = []
for si, season in enumerate(NEW):
    year = int(season[:4])
    for t, st in ((0, "rs"), (1, "po")):
        W = pd.read_csv(f"../boxraw/box_{season}_{st}.csv").fillna(0)
        W["TeamId"] = W.TeamId.replace({1610612740: 1610612766})
        D = derive(W)
        G = games(year, t == 1)
        # ---- players ----
        for i, r in D.iterrows():
            if r.SecondsPlayed < 60 or r.TeamId not in tid2a: continue
            fga = r.FG2A + r.FG3A; tov = r.LiveBallTurnovers + r.DeadBallTurnovers
            row = dict(p=kid(int(r.EntityId)), s=si, t=t, tm=tid2a[int(r.TeamId)], gp=int(r.GamesPlayed), sec=int(r.SecondsPlayed),
                       pts=int(r.Points), reb=int(r.OffRebounds + r.DefRebounds), ast=int(r.Assists), stl=int(r.Steals), blk=int(r.Blocks),
                       tov=int(tov), fg2a=int(r.FG2A), fg3a=int(r.FG3A), fg3m=int(r.FG3M), fta=int(r.FTA),
                       pos=int(round((r.OffPoss + r.DefPoss) / 2)),
                       usg=round(float((fga + 0.44 * r.FTA + tov) / max(r.OffPoss, 1) * 100 / 1.148), 1),
                       oo=round(float((r.PlusMinus + r.OpponentPoints) / max(r.OffPoss, 1) * 100), 1),
                       od=round(float(r.OpponentPoints / max(r.DefPoss, 1) * 100), 1))
            for k in P_new: P_new[k].append(row[k])
        # ---- teams ----
        g = W.groupby("TeamId"); Dg = D.groupby(W.TeamId)
        cols = lambda end: [c for c in W.columns if c.endswith(end)]
        for tid, x in g:
            if tid not in tid2a: continue
            dx = D.loc[x.index]
            secs = (x.SecondsPlayedOff.sum() + x.SecondsPlayedDef.sum()) / 5
            op, dp = x.OffPoss.sum() / 5, x.DefPoss.sum() / 5
            mine = G[(G.home == tid) | (G.away == tid)]
            won = ((mine.home == tid) & (mine.hp > mine.ap)) | ((mine.away == tid) & (mine.ap > mine.hp))
            pts = int(dx.Points.sum()); opp = int(round(x.OpponentPoints.sum() / 5))
            oreb_o = x[cols("OffReboundedOpportunities")].sum().sum() / 5; oreb_d = x[cols("OffRebounded")].sum().sum() / 5
            dreb_o = x[cols("DefReboundOpportunities")].sum().sum() / 5
            row = dict(a=tid2a[int(tid)], s=si, t=t, gp=len(mine), pts=pts, opp=opp, op=int(round(op)), dp=int(round(dp)),
                       fg2a=int(dx.FG2A.sum()), fg2m=int(dx.FG2M.sum()), fg3a=int(dx.FG3A.sum()), fg3m=int(dx.FG3M.sum()), fta=int(dx.FTA.sum()),
                       tov=int((dx.LiveBallTurnovers + dx.DeadBallTurnovers).sum()), stl=int(dx.Steals.sum()), blk=int(dx.Blocks.sum()),
                       sf=int(x["Shooting Fouls"].sum()), pace=round(float((op + dp) / 2 / (secs / 2880)), 1),
                       ts=round(float(pts / (2 * (dx.FG2A.sum() + dx.FG3A.sum() + 0.44 * dx.FTA.sum()))), 4),
                       efg=round(float((dx.FG2M.sum() + 1.5 * dx.FG3M.sum()) / (dx.FG2A.sum() + dx.FG3A.sum())), 4),
                       oreb=round(float(oreb_d / max(oreb_o, 1) / 0.963), 4), dreb=round(float(dx.DefRebounds.sum() / max(dreb_o, 1) / 1.017), 4),
                       sq=None, rim=round(float(dx.AtRimFGA.sum() / (dx.FG2A.sum() + dx.FG3A.sum())), 4),
                       w=int(won.sum()), l=int(len(mine) - won.sum()))
            for k in T_new: T_new[k].append(row.get(k))
        # ---- playoff series ----
        if t == 1:
            G["pair"] = [tuple(sorted((h, a))) for h, a in zip(G.home, G.away)]
            G["winner"] = np.where(G.hp > G.ap, G.home, G.away)
            seen = {}
            for pair, x in G.sort_values("gid").groupby("pair", sort=False):
                c = x.winner.value_counts(); w = int(c.index[0]); l = pair[0] if pair[1] == w else pair[1]
                first = x.gid.min()
                seen[pair] = (first, w, int(l), int(c.iloc[0]), int(c.iloc[1]) if len(c) > 1 else 0)
            # round = order of the series within each team's run
            runs = {}
            for pair, (first, w, l, ww, lw) in sorted(seen.items(), key=lambda kv: kv[1][0]):
                rnd = max(runs.get(w, 0), runs.get(l, 0)) + 1
                runs[w] = rnd; runs[l] = rnd
                series_new.append([si, rnd, tid2a[w], tid2a[l], ww, lw])
        else:
            # league averages per team-game, Basketball-Reference style (same keys as the 2000-01+ rows)
            from league_rows import league_row
            league_new.append(league_row(f"../boxraw/box_{season}_rs.csv", season, len(G)))

# ---- merge: new seasons first, old indices shift by SH ----
for k in d["P"]: d["P"][k] = P_new[k] + ([v + SH for v in d["P"][k]] if k == "s" else d["P"][k])
for k in d["T"]: d["T"][k] = T_new[k] + ([v + SH for v in d["T"][k]] if k == "s" else d["T"][k])
d["series"] = series_new + [[x[0] + SH] + x[1:] for x in d["series"]]
d["league"] = league_new + d["league"]
d["seasons"] = NEW + d["seasons"]
d["ids"], d["names"] = ids, names
json.dump(d, open("data_1996.json", "w"), separators=(",", ":"), allow_nan=False)
print("players", len(ids), "| P rows", len(d["P"]["p"]), "| T rows", len(d["T"]["a"]), "| series", len(d["series"]))
print("new series:", [(NEW[s], r, d["abbrs"][w], d["abbrs"][l], ww, lw) for s, r, w, l, ww, lw in series_new if r == 4])
