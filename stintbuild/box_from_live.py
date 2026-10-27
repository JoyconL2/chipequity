"""Season box totals per player from NBA.com live play-by-play files (playbyplay_<gameId>.json), using the same
pbpstats parser as box_from_pbp.py, so the season being played gets the same stats (and box-score prior inputs)
as every earlier season. Output has the same raw pbpstats stat keys as box_from_pbp.py (read with derive_box.py).

usage: python box_from_live.py <folder of playbyplay json> <season> <rs|po> <out csv>"""
import sys, os, glob, json, shutil, tempfile, re
from collections import defaultdict
from multiprocessing import Pool
import pandas as pd
import build_stints  # noqa: F401  (puts ../pbplib on the path)
from pbpstats.client import Client
from live_fix import fix

SKIP = re.compile(r"^(Period|Penalty|SecondChance|\d+:)")


def clean(path, out):
    """Since 2025-26 an end-of-quarter heave is its own action type ("heave"), not a shot; pbpstats doesn't know it,
    so a rebound that points back to a heave can't find its missed shot. Those rebounds are dropped."""
    J = json.load(open(path)); A = J["game"]["actions"]
    J["game"]["actions"], _ = fix(A)
    json.dump(J, open(out, "w"))


def work(path):
    gid = os.path.basename(path).split(".")[0][-10:]
    d = tempfile.mkdtemp(prefix="lbox_")
    try:
        os.makedirs(f"{d}/pbp")
        clean(path, f"{d}/pbp/live_{gid}.json")
        poss = Client({"dir": d, "Possessions": {"source": "file", "data_provider": "live"}}).Game(gid).possessions
        tot = defaultdict(float)
        for s in poss.player_stats:
            if SKIP.match(s["stat_key"]): continue
            tot[(s["player_id"], s["team_id"], s["stat_key"])] += s["stat_value"]
        return gid, dict(tot), None
    except Exception as e:
        return gid, {}, f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    folder, season, stype, out = sys.argv[1:5]
    files = sorted(glob.glob(f"{folder}/*.json"))
    season_tot = defaultdict(float); games = defaultdict(set); errs = []
    with Pool(max(2, os.cpu_count() or 2)) as pool:
        for gid, tot, err in pool.imap_unordered(work, files, chunksize=4):
            if err: errs.append((gid, err)); continue
            for (p, t, k), v in tot.items():
                season_tot[(p, t, k)] += v
                if k in ("SecondsPlayedOff", "SecondsPlayedDef") and v > 0: games[(p, t)].add(gid)
    rows = defaultdict(dict)
    for (p, t, k), v in season_tot.items(): rows[(p, t)][k] = v
    W = pd.DataFrame([{"EntityId": p, "TeamId": t, "Season": season, "season_type": stype, "GamesPlayed": len(games[(p, t)]), **v}
                      for (p, t), v in rows.items()]).fillna(0)
    W.to_csv(out, index=False)
    print(f"{season} {stype}: {len(files)} games ({len(errs)} failed), {len(W)} player-team rows")
    for g, e in errs: print(f"::warning::{season} {stype} box score: game {g} left out ({e})")
    if files and len(errs) > 0.05 * len(files): sys.exit("too many games failed to parse")


if __name__ == "__main__":
    main()
