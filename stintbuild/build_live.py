"""Stints from the archived cdn.nba.com live play-by-play (cdnnba_<year>.csv) - used for 2025-26.
usage: python build_live.py <cdnnba csv> <season> <rs|po> <out csv>"""
import sys, os, json, shutil, tempfile, time
from multiprocessing import Pool
import pandas as pd
import build_stints as B
from pbpstats.client import Client

LIST_COLS = {"qualifiers", "personIdsFilter"}
FLOAT_COLS = {"x", "y", "xLegacy", "yLegacy", "shotDistance"}


def conv(k, v):
    if v == "": return None
    if k in LIST_COLS:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        return [int(p) for p in parts] if k == "personIdsFilter" else parts
    if k in FLOAT_COLS:
        try: return float(v)
        except ValueError: return v
    if v.lstrip("-").isdigit(): return int(v)
    if v in ("TRUE", "FALSE"): return v == "TRUE"
    return v


def work(args):
    gid, actions, season, stype, date = args
    d = tempfile.mkdtemp(prefix="live_")
    try:
        os.makedirs(f"{d}/pbp")
        json.dump({"game": {"gameId": gid, "actions": actions}}, open(f"{d}/pbp/live_{gid}.json", "w"))
        H = A = None; ph = pa = 0
        for a in actions:
            sh, sa = a.get("scoreHome") or 0, a.get("scoreAway") or 0
            if a.get("teamId"):
                if sh > ph and H is None: H = a["teamId"]
                if sa > pa and A is None: A = a["teamId"]
            ph, pa = max(ph, sh), max(pa, sa)
        poss = Client({"dir": d, "Possessions": {"source": "file", "data_provider": "live"}}).Game(gid).possessions.items
        rows, hs, as_, sk = B.game_stints(poss, gid, season, stype, date, H, A)
        note = f"score {hs}-{as_} vs {ph}-{pa}" if (hs, as_) != (ph, pa) else ""
        return gid, rows, note, None
    except Exception as e:
        return gid, [], "", f"{type(e).__name__}: {str(e)[:160]}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    src, season, stype, out = sys.argv[1:5]
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    cols = list(df.columns)
    jobs = []
    for g, gdf in df.groupby("gameId", sort=True):
        gid = str(g).zfill(10)
        acts = []
        for row in gdf.itertuples(index=False, name=None):
            a = {k: conv(k, v) for k, v in zip(cols, row) if k != "gameId"}
            acts.append({k: v for k, v in a.items() if v is not None})
        date = ""
        t = gdf.timeActual.iloc[0]
        if t:   # UTC tip-off -> US date (games tip 7pm-10:30pm ET = next-day UTC for late games)
            date = (pd.Timestamp(t) - pd.Timedelta(hours=8)).strftime("%Y-%m-%d")
        jobs.append((gid, acts, season, stype, date))
    t0 = time.time(); allrows, log = [], []; ok = bad = warn = 0
    with Pool(2) as pool:
        for gid, rows, note, err in pool.imap_unordered(work, jobs, chunksize=4):
            if err: bad += 1; log.append(f"{gid}\tFAIL\t{err}"); continue
            ok += 1; allrows += rows
            if note: warn += 1; log.append(f"{gid}\tWARN\t{note}")
    pd.DataFrame(allrows, columns=B.COLS).to_csv(out, index=False)
    open(out.replace(".csv", "_log.txt"), "w").write("\n".join(log))
    print(f"{season} {stype}: {len(jobs)} games, ok {ok}, failed {bad}, score mismatches {warn}, {len(allrows)} stints, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
