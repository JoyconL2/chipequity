"""Build stints from the archived stats.nba.com play-by-play (shufinskiy/nba_data, nbastats_<year>.csv),
parsed offline with the pbpstats library (stats_nba provider, file source).

usage: python build_stints.py <nbastats csv> <season e.g. 2005-06> <rs|po> <out csv> [--limit N]
"""
import sys, os, json, shutil, tempfile, time, math
from multiprocessing import Pool
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pbplib"))
from pbpstats.client import Client
from pbpstats.resources.enhanced_pbp.stats_nba.start_of_period import StatsStartOfPeriod
from pbpstats.resources.enhanced_pbp.start_of_period import InvalidNumberOfStartersException
from pbpstats.resources.enhanced_pbp import Substitution

COLS = ["game_id", "season", "season_type", "game_date", "period", "start_sec", "end_sec",
        "home_team", "away_team", "home_players", "away_players",
        "home_poss", "away_poss", "home_pts", "away_pts", "start_margin"]
STATS = {"filled": 0}


# ---- offline period-starter fallback (the library would call the dead stats.nba.com boxscore) ----
from pbpstats.data_loader.nba_enhanced_pbp_loader import NbaEnhancedPbpLoader
from pbpstats.data_loader.nba_possession_loader import NbaPossessionLoader


def _no_web(self, file_directory=None):
    return self._get_period_starters_from_period_events(file_directory)

StatsStartOfPeriod.get_period_starters = _no_web


def _period_players(sop):
    """players whose first appearance in the period is coming IN on a sub (cannot be starters)"""
    first_in, seen = set(), set()
    ev = sop.next_event
    while ev is not None and ev.period == sop.period:
        if isinstance(ev, Substitution):
            inc, out = ev.incoming_player_id, ev.outgoing_player_id
            if inc not in seen: first_in.add(inc)
            seen.update([inc, out])
        ev = ev.next_event
    return first_in


def _set_period_start_items(self):
    for i in self.start_period_indices:
        sop = self.items[i]
        sop.team_starting_with_ball = sop.get_team_starting_with_ball()
        try:
            sop.period_starters = sop.get_period_starters(file_directory=self.file_directory)
            continue
        except InvalidNumberOfStartersException:
            pass
        found = sop._get_period_starters_from_period_events(self.file_directory, ignore_missing_starters=True)
        prev = self.items[i - 1].current_players if i > 0 else {}
        first_in = _period_players(sop)
        teams = set(found) | set(prev)
        fixed = {}
        for t in teams:
            f = [p for p in found.get(t, []) if p not in first_in]
            pv = list(prev.get(t, []))
            if len(f) > 5:                       # keep those also on the floor at the end of last period first
                f = [p for p in f if p in pv] + [p for p in f if p not in pv]
                f = f[:5]
            for p in pv:
                if len(f) >= 5: break
                if p not in f and p not in first_in: f.append(p)
            if len(f) != 5:
                raise InvalidNumberOfStartersException(f"{sop.game_id} P{sop.period} team {t}: {f}")
            fixed[t] = f
        sop.period_starters = fixed
        STATS["filled"] += 1

NbaEnhancedPbpLoader._set_period_start_items = _set_period_start_items
# a few games have two possessions in a row for one team (pbp ordering quirks): keep the game, don't abort
from pbpstats.data_loader.stats_nba.possessions.loader import StatsNbaPossessionLoader
from pbpstats.data_loader.stats_nba.enhanced_pbp.loader import StatsNbaEnhancedPbpLoader
_orig_reb = StatsNbaEnhancedPbpLoader._check_rebound_event_order
def _tolerant_reb(self, max_retries):
    # the library's last resort here is a web call to the retired data.nba.com feed; keep the game instead
    StatsNbaEnhancedPbpLoader._use_data_nba_event_order = lambda self: (_ for _ in ()).throw(RuntimeError("order"))
    try:
        _orig_reb(self, max_retries)
    except Exception:
        STATS["order"] = STATS.get("order", 0) + 1
StatsNbaEnhancedPbpLoader._check_rebound_event_order = _tolerant_reb
StatsNbaPossessionLoader._check_that_possessions_alternate = lambda self: None


def kind(ev):
    names = {c.__name__ for c in type(ev).__mro__}
    return "fg" if "FieldGoal" in names else "ft" if "FreeThrow" in names else ""


def event_points(ev):
    k = kind(ev)
    try:
        if k == "fg" and ev.is_made: return int(ev.shot_value)
        if k == "ft" and ev.is_made: return 1
    except Exception:
        pass
    return 0


def lineup(ev, team):
    try:
        p = ev.current_players.get(team)
        return "-".join(str(x) for x in sorted(int(i) for i in p)) if p and len(p) == 5 else None
    except Exception:
        return None


def game_stints(poss, gid, season, stype, date, H, A):
    rows, cur = [], None
    hs = as_ = 0; skipped = 0
    for p in poss:
        if not p.events: continue
        off = getattr(p, "offense_team_id", None)
        first = True
        for ev in p.events:
            per = int(ev.period)
            hl, al = lineup(ev, H), lineup(ev, A)
            pts = event_points(ev)
            if hl is None or al is None:
                skipped += 1
                if pts:
                    if ev.team_id == H: hs += pts
                    elif ev.team_id == A: as_ += pts
                continue
            key = (per, hl, al)
            if cur is None or cur["key"] != key:
                t = float(ev.seconds_remaining)
                if cur is not None:
                    cur["end_sec"] = 0.0 if cur["period"] != per else t
                    rows.append(cur)
                if cur is None or cur["period"] != per:
                    t = float(720 if per <= 4 else 300)
                cur = dict(key=key, game_id=gid, season=season, season_type=stype, game_date=date, period=per,
                           start_sec=t, end_sec=0.0, home_team=H, away_team=A, home_players=hl, away_players=al,
                           home_poss=0, away_poss=0, home_pts=0, away_pts=0, start_margin=hs - as_)
            if first:
                if off == H: cur["home_poss"] += 1
                elif off == A: cur["away_poss"] += 1
                first = False
            if pts:
                if ev.team_id == H: cur["home_pts"] += pts; hs += pts
                elif ev.team_id == A: cur["away_pts"] += pts; as_ += pts
    if cur is not None:
        cur["end_sec"] = 0.0; rows.append(cur)
    for r in rows: r.pop("key")
    return rows, hs, as_, skipped


def clean(v):
    if v is None: return None
    if isinstance(v, float):
        if math.isnan(v): return None
        if v.is_integer(): return int(v)
    return v


def add_period_markers(headers, rows):
    """Old games (1990s) sometimes lack 'start/end of period' rows; the parser needs them."""
    ti, pi, ci, ni = headers.index("EVENTMSGTYPE"), headers.index("PERIOD"), headers.index("PCTIMESTRING"), headers.index("EVENTNUM")
    gi = headers.index("GAME_ID")
    def marker(r, typ, clock):
        m = [None] * len(headers)
        m[gi] = r[gi]
        for k in ("EVENTMSGACTIONTYPE", "PERSON1TYPE", "PERSON2TYPE", "PERSON3TYPE", "PLAYER1_ID", "PLAYER2_ID", "PLAYER3_ID", "VIDEO_AVAILABLE_FLAG"):
            m[headers.index(k)] = 0
        m[ti], m[pi], m[ci], m[ni] = typ, r[pi], clock, r[ni]
        return m
    out = []
    for i, r in enumerate(rows):
        if i == 0 or r[pi] != rows[i - 1][pi]:
            if i > 0 and rows[i - 1][ti] != 13: out.append(marker(rows[i - 1], 13, "0:00"))
            if r[ti] != 12: out.append(marker(r, 12, "12:00" if r[pi] <= 4 else "5:00"))
        out.append(r)
    if rows and rows[-1][ti] != 13: out.append(marker(rows[-1], 13, "0:00"))
    return out


EMPTY_SHOTS = {"resultSets": [{"name": "Shot_Chart_Detail", "headers": ["GAME_EVENT_ID"], "rowSet": []}]}


def work(args):
    gid, headers, rowset, season, stype, date = args
    d = tempfile.mkdtemp(prefix="pbp_")
    try:
        rowset = add_period_markers(headers, rowset)
        os.makedirs(f"{d}/pbp"); os.makedirs(f"{d}/game_details")
        json.dump({"resultSets": [{"name": "PlayByPlay", "headers": headers, "rowSet": rowset}]}, open(f"{d}/pbp/stats_{gid}.json", "w"))
        for side in ("home", "away"):
            json.dump(EMPTY_SHOTS, open(f"{d}/game_details/stats_{side}_shots_{gid}.json", "w"))
        # home/away from description columns
        hi, vi, ti = headers.index("HOMEDESCRIPTION"), headers.index("VISITORDESCRIPTION"), headers.index("PLAYER1_TEAM_ID")
        H = A = None
        for r in rowset:
            if r[ti]:
                if r[hi] and not r[vi] and H is None: H = int(r[ti])
                if r[vi] and not r[hi] and A is None: A = int(r[ti])
            if H and A: break
        # final score from SCORE ("away - home")
        si = headers.index("SCORE"); final = None
        for r in rowset:
            if r[si] and " - " in str(r[si]): final = r[si]
        fa, fh = (int(x) for x in final.split(" - ")) if final else (None, None)
        filled0 = STATS["filled"]
        def parse():
            c = Client({"dir": d, "Possessions": {"source": "file", "data_provider": "stats_nba"}})
            return c.Game(gid).possessions.items
        try:
            poss = parse()
        except Exception as e:
            if "EventOrderError" not in type(e).__name__: raise
            # retry without rebounds that don't follow a missed shot (bad ordering in old feeds)
            hi2, vi2, ni2 = headers.index("HOMEDESCRIPTION"), headers.index("VISITORDESCRIPTION"), headers.index("NEUTRALDESCRIPTION")
            keep, last = [], None
            for r in rowset:
                t = r[headers.index("EVENTMSGTYPE")]
                if t == 4:
                    desc = " ".join(str(x) for x in (r[hi2], r[vi2]) if x)
                    if last not in ("miss",): continue
                if t == 2: last = "miss"
                elif t == 3:
                    desc = " ".join(str(x) for x in (r[hi2], r[vi2]) if x)
                    last = "miss" if "MISS" in desc.upper() else "make"
                elif t in (1, 5, 6, 7, 10, 12, 13): last = "other"
                elif t == 4: last = "reb"
                keep.append(r)
            json.dump({"resultSets": [{"name": "PlayByPlay", "headers": headers, "rowSet": keep}]}, open(f"{d}/pbp/stats_{gid}.json", "w"))
            poss = parse()
        rows, hs, as_, skipped = game_stints(poss, gid, season, stype, date, H, A)
        note = ""
        if (hs, as_) != (fh, fa): note = f"score {hs}-{as_} vs {fh}-{fa}"
        return gid, rows, note, STATS["filled"] - filled0, skipped, None
    except Exception as e:
        return gid, [], "", 0, 0, f"{type(e).__name__}: {str(e)[:160]}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    src, season, stype, out = sys.argv[1:5]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    dates = {}
    if "--dates" in sys.argv:
        dates = json.load(open(sys.argv[sys.argv.index("--dates") + 1]))
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    headers = list(df.columns)
    num = {"GAME_ID", "EVENTNUM", "EVENTMSGTYPE", "EVENTMSGACTIONTYPE", "PERIOD", "PERSON1TYPE", "PERSON2TYPE", "PERSON3TYPE",
           "PLAYER1_ID", "PLAYER2_ID", "PLAYER3_ID", "PLAYER1_TEAM_ID", "PLAYER2_TEAM_ID", "PLAYER3_TEAM_ID", "VIDEO_AVAILABLE_FLAG"}
    for c in headers:
        if c in num:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["GAME_ID"] = df.GAME_ID.astype("Int64")
    jobs = []
    for g, gdf in df.groupby("GAME_ID", sort=True):
        gid = str(int(g)).zfill(10)
        pass
        rowset = [[clean(v) if not isinstance(v, str) else (v if v != "" else None) for v in row] for row in gdf.itertuples(index=False, name=None)]
        gi = headers.index("GAME_ID")
        for r in rowset: r[gi] = gid
        jobs.append((gid, headers, rowset, season, stype, dates.get(gid, "")))
        if limit and len(jobs) >= limit: break
    del df
    t0 = time.time(); ok = bad = warn = filled = 0; allrows = []; log = []
    with Pool(2) as pool:
        for gid, rows, note, fl, sk, err in pool.imap_unordered(work, jobs, chunksize=4):
            if err: bad += 1; log.append(f"{gid}\tFAIL\t{err}"); continue
            ok += 1; filled += fl; allrows += rows
            if note: warn += 1; log.append(f"{gid}\tWARN\t{note}")
    pd.DataFrame(allrows, columns=COLS).to_csv(out, index=False)
    open(out.replace(".csv", "_log.txt"), "w").write("\n".join(log))
    print(f"{season} {stype}: {len(jobs)} games, ok {ok}, failed {bad}, score mismatches {warn}, starter fills {filled}, "
          f"{len(allrows)} stints, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
