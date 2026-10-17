"""Per-game box scores straight from NBA.com play-by-play (pbpstats parser).
  playoffs        -> one row per player per game (for series lines)
  regular season  -> one row per team per game (for opponent TS% allowed, SRS)
usage: python box_games.py <nbastats csv> <season> <rs|po> <out csv>       (1996-97 .. 2024-25)
       python box_games.py --live <cdnnba csv> <season> <rs|po> <out csv>  (2025-26)"""
import sys, os, json, shutil, tempfile
from collections import defaultdict
from multiprocessing import Pool
import pandas as pd
import build_stints as B
import box_from_pbp as X
from derive_box import derive
from pbpstats.client import Client
from pbpstats.resources.enhanced_pbp.live.enhanced_pbp_item import LiveEnhancedPbpItem
LiveEnhancedPbpItem.shot_type = "UnknownDistance2pt"   # a few live-feed events reference a shot type they don't carry


def drop_teamless_fouls(headers, rowset):
    """old feeds have some fouls with no team attached (team/bench technicals); the parser can't place them"""
    ti, pi = headers.index("EVENTMSGTYPE"), headers.index("PLAYER1_TEAM_ID")
    return [r for r in rowset if not (r[ti] == 6 and not r[pi])]

KEEP = ["Points", "FG2A", "FG2M", "FG3A", "FG3M", "FTA", "FTM", "OffRebounds", "DefRebounds", "Assists", "Steals", "Blocks",
        "LiveBallTurnovers", "DeadBallTurnovers", "SecondsPlayed", "OffPoss", "DefPoss", "PlusMinus", "OpponentPoints"]


def to_rows(gid, poss_obj):
    tot = defaultdict(float)
    for s in poss_obj.player_stats:
        if X.SKIP.match(s["stat_key"]): continue
        tot[(s["player_id"], s["team_id"], s["stat_key"])] += s["stat_value"]
    rows = defaultdict(dict)
    for (p, t, k), v in tot.items(): rows[(p, t)][k] = v
    W = pd.DataFrame([{"EntityId": p, "TeamId": t, "Season": "", "season_type": "", "GamesPlayed": 1, **v} for (p, t), v in rows.items()]).fillna(0)
    D = derive(W)
    D["SecondsPlayed"] = W.get("SecondsPlayedOff", 0) + W.get("SecondsPlayedDef", 0)
    D["FTM"] = W.get("FtsMade", 0) + W.get("TechFtsMade", 0)
    out = D[["EntityId", "TeamId"] + KEEP].copy(); out.insert(0, "game_id", gid)
    return out


def work_stats(args):
    gid, headers, rowset = args
    d = tempfile.mkdtemp(prefix="bg_")
    try:
        rowset = X.fix_franchise_ids(headers, rowset); rowset = B.add_period_markers(headers, rowset)
        os.makedirs(f"{d}/pbp"); os.makedirs(f"{d}/game_details")
        json.dump({"resultSets": [{"name": "PlayByPlay", "headers": headers, "rowSet": rowset}]}, open(f"{d}/pbp/stats_{gid}.json", "w"))
        for side in ("home", "away"): json.dump(B.EMPTY_SHOTS, open(f"{d}/game_details/stats_{side}_shots_{gid}.json", "w"))
        parse = lambda: Client({"dir": d, "Possessions": {"source": "file", "data_provider": "stats_nba"}}).Game(gid).possessions
        try:
            poss = parse(); return to_rows(gid, poss), None
        except Exception as e:
            if "EventOrderError" in type(e).__name__: rowset = X.drop_orphan_rebounds(headers, rowset)
            elif isinstance(e, KeyError): rowset = drop_teamless_fouls(headers, rowset)
            else: raise
            json.dump({"resultSets": [{"name": "PlayByPlay", "headers": headers, "rowSet": rowset}]}, open(f"{d}/pbp/stats_{gid}.json", "w"))
            poss = parse()
        return to_rows(gid, poss), None
    except Exception as e:
        return None, f"{gid} {type(e).__name__}: {str(e)[:100]}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def work_live(args):
    gid, actions = args
    d = tempfile.mkdtemp(prefix="bgl_")
    try:
        os.makedirs(f"{d}/pbp")
        json.dump({"game": {"gameId": gid, "actions": actions}}, open(f"{d}/pbp/live_{gid}.json", "w"))
        poss = Client({"dir": d, "Possessions": {"source": "file", "data_provider": "live"}}).Game(gid).possessions
        return to_rows(gid, poss), None
    except Exception as e:
        return None, f"{gid} {type(e).__name__}: {str(e)[:100]}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    live = sys.argv[1] == "--live"
    src, season, stype, out = sys.argv[2:6] if live else sys.argv[1:5]
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    jobs = []
    if live:
        import build_live as L
        cols = list(df.columns)
        for g, gdf in df.groupby("gameId", sort=True):
            gid = str(g).zfill(10)
            if stype == "po" and not gid.startswith("004"): continue
            acts = [{k: v for k, v in ((k, L.conv(k, v)) for k, v in zip(cols, r) if k != "gameId") if v is not None} for r in gdf.itertuples(index=False, name=None)]
            jobs.append((gid, acts))
        fn = work_live
    else:
        headers = list(df.columns)
        for g, gdf in df.groupby("GAME_ID", sort=True):
            gid = str(int(g)).zfill(10)
            if stype == "po" and not gid.startswith("004"): continue
            rows = [[X.conv(v) for v in r] for r in gdf.itertuples(index=False, name=None)]
            for r in rows: r[0] = gid
            jobs.append((gid, headers, rows))
        fn = work_stats
    parts, errs = [], []
    with Pool(2) as pool:
        for res, err in pool.imap_unordered(fn, jobs, chunksize=4):
            if err: errs.append(err); continue
            parts.append(res)
    P = pd.concat(parts, ignore_index=True)
    P = P[(P.EntityId > 0) & (P.EntityId < 1610612700) | (P.EntityId == 0)]
    if stype == "rs":   # team-level per game is all the regular season needs
        P = P.groupby(["game_id", "TeamId"], as_index=False)[[c for c in KEEP if c not in ("SecondsPlayed", "OffPoss", "DefPoss", "PlusMinus", "OpponentPoints")]].sum()
    else:
        P = P[P.EntityId > 0]
    P.insert(1, "season", season)
    P.to_csv(out, index=False)
    print(f"{season} {stype}: {len(jobs)} games, {len(errs)} failed, {len(P)} rows")


if __name__ == "__main__":
    main()
