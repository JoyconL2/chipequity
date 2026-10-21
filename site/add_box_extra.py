"""Add the box-score counts the site didn't carry yet to data.json's player rows: 2-pointers made, free throws made,
offensive and defensive rebounds, personal fouls (P.fg2m, P.ftm, P.oreb, P.dreb, P.pf). Source: the same
pbpstats.com-style season files the features come from (src96/Player_all_seasons.csv: play-by-play for 1996-97 to
1999-00, pbpstats.com from 2000-01). Free throws made = points - 2 x 2PM - 3 x 3PM.
usage: python add_box_extra.py [data.json] [src96 dir]"""
import json, sys
import pandas as pd
path = sys.argv[1] if len(sys.argv) > 1 else "data.json"
src = sys.argv[2] if len(sys.argv) > 2 else "../src96"
D = json.load(open(path)); S = D["seasons"]; P = D["P"]; ids = D["ids"]; tids = D["teamIds"]
x = pd.read_csv(f"{src}/Player_all_seasons.csv", low_memory=False)
x["t"] = (x.SeasonType == "Playoffs").astype(int)
for c in ("FG2M", "FG3M", "Points", "OffRebounds", "DefRebounds", "Fouls"): x[c] = pd.to_numeric(x[c], errors="coerce").fillna(0)
SWAP = {1610612740: 1610612766, 1610612766: 1610612740}       # Hornets / Pelicans ids mixed in old feeds
by = {}
for r in x.itertuples(index=False):
    v = (int(r.FG2M or 0), int(round((r.Points or 0) - 2 * (r.FG2M or 0) - 3 * (r.FG3M or 0))), int(r.OffRebounds or 0), int(r.DefRebounds or 0), int(r.Fouls or 0), int(r.Points or 0))
    by[(int(r.EntityId), int(r.TeamId), r.Season, int(r.t))] = v
cols = {c: [] for c in ("fg2m", "ftm", "oreb", "dreb", "pf")}
hit = miss = bad = 0
for p, s, t, tm, pts in zip(P["p"], P["s"], P["t"], P["tm"], P["pts"]):
    key = (int(ids[p]), int(tids[tm]), S[s], int(t)); v = by.get(key) or by.get((key[0], SWAP.get(key[1], key[1]), key[2], key[3]))
    if v is None:
        miss += 1
        for c in cols: cols[c].append(None)
        continue
    hit += 1; bad += v[5] != pts
    v = list(v); v[1] = max(0, pts - 2 * v[0] - 3 * P["fg3m"][len(cols["fg2m"])])   # free throws from the site's own points, so the row adds up
    for c, val in zip(cols, v[:5]): cols[c].append(val)
# keep values already in the file for rows the source doesn't have (the season being played, added by update/add_season.py)
for c in cols:
    old = P.get(c)
    if old and len(old) == len(cols[c]): cols[c] = [n if n is not None else o for n, o in zip(cols[c], old)]
    P[c] = cols[c]
json.dump(D, open(path, "w"), separators=(",", ":"), allow_nan=False)
print(f"player rows: {hit} matched, {miss} not in the source, source points differ on {bad} (1990s play-by-play rebuild; the site keeps its own points)")
