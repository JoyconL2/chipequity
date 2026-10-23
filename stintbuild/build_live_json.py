"""Stints + per-game playoff box scores from raw NBA.com live play-by-play JSON files
(playbyplay_<gameId>.json from cdn.nba.com, one file per game).
usage: python build_live_json.py <folder of json> <season> <rs|po> <stints out csv> <box out csv>"""
import sys, os, json, glob, time
from multiprocessing import Pool
import pandas as pd
import build_stints as B
import build_live as L
import box_games as G
from live_fix import fix

NUM = {"scoreHome", "scoreAway"}


def load(path):
    acts = json.load(open(path))["game"]["actions"]
    acts, _ = fix(acts)
    for a in acts:
        for k in NUM:
            if k in a and isinstance(a[k], str): a[k] = int(a[k]) if a[k].lstrip("-").isdigit() else 0
    return acts


def both(args):
    gid, acts, season, stype, date = args
    st = L.work((gid, acts, season, stype, date))      # -> gid, rows, note, err
    bx = G.work_live((gid, acts))                       # -> df, err
    return st, bx


def main():
    folder, season, stype, out_st, out_bx = sys.argv[1:6]
    jobs = []
    for f in sorted(glob.glob(f"{folder}/*.json")):
        gid = os.path.basename(f).split(".")[0][-10:]
        acts = load(f)
        t = next((a.get("timeActual") for a in acts if a.get("timeActual")), "")
        date = (pd.Timestamp(t) - pd.Timedelta(hours=8)).strftime("%Y-%m-%d") if t else ""
        jobs.append((gid, acts, season, stype, date))
    srows, bparts, bad, warn = [], [], [], []
    with Pool(2) as pool:
        for (gid, rows, note, err), (bdf, berr) in pool.imap_unordered(both, jobs, chunksize=2):
            if err: bad.append(f"{gid} stints {err}")
            else: srows += rows
            if note: warn.append(f"{gid} {note}")
            if berr: bad.append(f"{gid} box {berr}")
            else: bparts.append(bdf)
    pd.DataFrame(srows, columns=B.COLS).to_csv(out_st, index=False)
    print(f"{season} {stype}: {len(jobs)} games | stints {len(srows)} | failed {len(bad)} | score mismatches {len(warn)}")
    for x in (bad + warn)[:8]: print("  ", x)
    if jobs and len(bad) > len(jobs):                   # every game failed one way or the other: stop here, with the reasons above
        sys.exit(f"no {season} {stype} game could be read")
    if not bparts: sys.exit(f"no {season} {stype} box scores could be built")
    bx = pd.concat(bparts, ignore_index=True); bx = bx[(bx.EntityId > 0) & (bx.EntityId < 1610612700)]
    bx.insert(1, "season", season); bx.to_csv(out_bx, index=False)
    print(f"  box rows {len(bx)}")


if __name__ == "__main__":
    main()
