"""Season box totals per player straight from play-by-play (+ shot coordinates), using the same pbpstats
parser that pbpstats.com uses - so 1996-97 to 1999-00 get the same stats as later seasons.

usage: python box_from_pbp.py <nbastats csv> <shotdetail csv> <season> <rs|po> <out csv>"""
import sys, os, json, shutil, tempfile, re
from collections import defaultdict
from multiprocessing import Pool
import pandas as pd
import build_stints as B
from pbpstats.client import Client

SKIP = re.compile(r"^(Period|Penalty|SecondChance|\d+:)")


def drop_orphan_rebounds(headers, rowset):
    ti, hi, vi = headers.index("EVENTMSGTYPE"), headers.index("HOMEDESCRIPTION"), headers.index("VISITORDESCRIPTION")
    keep, last = [], None
    for r in rowset:
        t = r[ti]
        if t == 4 and last != "miss": continue
        if t == 2: last = "miss"
        elif t == 3: last = "miss" if "MISS" in " ".join(str(x) for x in (r[hi], r[vi]) if x).upper() else "make"
        elif t in (1, 5, 6, 7, 10, 12, 13): last = "other"
        elif t == 4: last = "reb"
        keep.append(r)
    return keep


SWAP = {1610612740: 1610612766, 1610612766: 1610612740}   # Hornets/Pelicans franchise ids get mixed in old feeds


def fix_franchise_ids(headers, rowset):
    ti = headers.index("PLAYER1_TEAM_ID")
    teams = {r[ti] for r in rowset if isinstance(r[ti], int)}
    bad = {a: b for a, b in SWAP.items() if b in teams and a not in teams}
    if not bad: return rowset
    return [[bad.get(v, v) if isinstance(v, int) else v for v in r] for r in rowset]


def work(args):
    gid, headers, rowset, sh_headers, sh_rows = args
    d = tempfile.mkdtemp(prefix="box_")
    try:
        rowset = fix_franchise_ids(headers, rowset)
        rowset = B.add_period_markers(headers, rowset)
        os.makedirs(f"{d}/pbp"); os.makedirs(f"{d}/game_details")
        json.dump({"resultSets": [{"name": "PlayByPlay", "headers": headers, "rowSet": rowset}]}, open(f"{d}/pbp/stats_{gid}.json", "w"))
        json.dump({"resultSets": [{"name": "Shot_Chart_Detail", "headers": sh_headers, "rowSet": sh_rows}]}, open(f"{d}/game_details/stats_home_shots_{gid}.json", "w"))
        json.dump(B.EMPTY_SHOTS, open(f"{d}/game_details/stats_away_shots_{gid}.json", "w"))
        parse = lambda: Client({"dir": d, "Possessions": {"source": "file", "data_provider": "stats_nba"}}).Game(gid).possessions
        try:
            poss = parse()
        except Exception as e:
            if "EventOrderError" not in type(e).__name__: raise
            json.dump({"resultSets": [{"name": "PlayByPlay", "headers": headers, "rowSet": drop_orphan_rebounds(headers, rowset)}]}, open(f"{d}/pbp/stats_{gid}.json", "w"))
            poss = parse()
        tot = defaultdict(float)
        for s in poss.player_stats:
            if SKIP.match(s["stat_key"]): continue
            tot[(s["player_id"], s["team_id"], s["stat_key"])] += s["stat_value"]
        return gid, dict(tot), None
    except Exception as e:
        return gid, {}, f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def conv(v):
    return int(v) if v.lstrip("-").isdigit() else (v or None)


def main():
    src, shots, season, stype, out = sys.argv[1:6]
    df = pd.read_csv(src, dtype=str, keep_default_na=False); headers = list(df.columns)
    sd = pd.read_csv(shots, dtype=str, keep_default_na=False) if os.path.exists(shots) else None
    sgroups = {g: x for g, x in sd.groupby("GAME_ID")} if sd is not None else {}
    jobs = []
    for g, gdf in df.groupby("GAME_ID", sort=True):
        gid = str(int(g)).zfill(10)
        rows = [[conv(v) for v in r] for r in gdf.itertuples(index=False, name=None)]
        for r in rows: r[0] = gid
        s = sgroups.get(g)
        srows = [[conv(v) for v in r] for r in s.itertuples(index=False, name=None)] if s is not None else []
        jobs.append((gid, headers, rows, list(sd.columns) if sd is not None else ["GAME_EVENT_ID"], srows))
    season_tot = defaultdict(float); games = defaultdict(set); bad = 0; errs = []
    with Pool(2) as pool:
        for gid, tot, err in pool.imap_unordered(work, jobs, chunksize=4):
            if err: bad += 1; errs.append(err); continue
            for (p, t, k), v in tot.items():
                season_tot[(p, t, k)] += v
                if k in ("SecondsPlayedOff", "SecondsPlayedDef") and v > 0: games[(p, t)].add(gid)
    rows = defaultdict(dict)
    for (p, t, k), v in season_tot.items(): rows[(p, t)][k] = v
    W = pd.DataFrame([{"EntityId": p, "TeamId": t, "Season": season, "season_type": stype, "GamesPlayed": len(games[(p, t)]), **v}
                      for (p, t), v in rows.items()]).fillna(0)
    W.to_csv(out, index=False)
    print(f"{season} {stype}: {len(jobs)} games ({bad} failed), {len(W)} player-team rows")
    from collections import Counter
    for e, n in Counter(x[:60] for x in errs).most_common(4): print("   ", n, e)


if __name__ == "__main__":
    main()
