"""
Basketball Done Right - STEPS 1 & 2: download every game's play-by-play and turn it into stints.

A stint = a stretch where the same 10 players are on the floor. For each one we record possessions,
points for each side, the time it started/ended and the score when it started. That is exactly the
input the RAPM engine (rapm_engine.py) needs.

Run on YOUR PC (NBA.com blocks cloud servers like Colab):
    pip install pbpstats pandas requests
    python get_stints.py --test              # 3 games, checks the numbers add up (1 minute)
    python get_stints.py                     # every season 2000-01 -> 2025-26, regular season + playoffs

Options
    --from 2000-01 --to 2025-26    season range (play-by-play exists from 1996-97)
    --types rs,po                  rs = regular season, po = playoffs
    --workers 3                    games downloaded at once (lower it if you get blocked)
    --out stints                   output folder

Safe to stop any time (Ctrl+C) and run again: finished games are skipped.
Output: stints/stints_<season>_<rs|po>.csv, plus done_games.txt and failed_games.txt.
"""
import argparse, csv, os, sys, time, random, threading, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from pbpstats.client import Client
except ImportError:
    sys.exit("pbpstats isn't installed. Run:  pip install pbpstats pandas requests")
import requests

COLS = ["game_id", "season", "season_type", "game_date", "period", "start_sec", "end_sec",
        "home_team", "away_team", "home_players", "away_players",
        "home_poss", "away_poss", "home_pts", "away_pts", "start_margin"]
PROVIDERS = ["live", "stats_nba", "data_nba"]       # tried in this order; the one that works is remembered
STYPE = {"rs": "Regular Season", "po": "Playoffs"}


def seasons_between(a, b):
    y0, y1 = int(a[:4]), int(b[:4])
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(y0, y1 + 1)]


# ---------------- game lists (home team + date for every game) ----------------
def game_list(season, stype):
    """Try pbpstats.com first (one request, has home team + date), then the pbpstats library."""
    try:
        r = requests.get("https://api.pbpstats.com/get-games/nba",
                         params={"Season": season, "SeasonType": STYPE[stype]}, timeout=30,
                         headers={"User-Agent": "Mozilla/5.0"})
        res = r.json().get("results", [])
        if res:
            return [dict(game_id=str(g["GameId"]).zfill(10), date=str(g.get("Date", ""))[:10],
                         home=int(g["HomeTeamId"]), away=int(g["AwayTeamId"]),
                         home_pts=g.get("HomePoints"), away_pts=g.get("AwayPoints")) for g in res]
    except Exception as e:
        print(f"  pbpstats.com game list failed ({type(e).__name__}); trying NBA.com")
    for prov in ["stats_nba", "data_nba", "live"]:
        try:
            c = Client({"Games": {"source": "web", "data_provider": prov}})
            items = c.Season("nba", season, STYPE[stype]).games.final_games
            out = []
            for g in items:
                out.append(dict(game_id=str(g["game_id"]).zfill(10), date=str(g.get("date", ""))[:10],
                                home=int(g.get("home_team_id")), away=int(g.get("visitor_team_id") or g.get("away_team_id")),
                                home_pts=None, away_pts=None))
            if out:
                return out
        except Exception as e:
            print(f"  NBA.com game list via {prov} failed ({type(e).__name__})")
    return []


# ---------------- one game -> stints ----------------
def kind(ev):
    names = {c.__name__ for c in type(ev).__mro__}
    if "FieldGoal" in names: return "fg"
    if "FreeThrow" in names: return "ft"
    return ""


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
        p = ev.current_players.get(team) or ev.current_players.get(str(team))
        return "-".join(str(x) for x in sorted(int(i) for i in p)) if p and len(p) == 5 else None
    except Exception:
        return None


_provider_ok = {"p": None}
_plock = threading.Lock()


def load_possessions(gid):
    order = PROVIDERS[:]
    if _provider_ok["p"]:
        order.remove(_provider_ok["p"]); order.insert(0, _provider_ok["p"])
    last = None
    for prov in order:
        for attempt in range(3):
            try:
                c = Client({"Possessions": {"source": "web", "data_provider": prov}})
                items = c.Game(gid).possessions.items
                if items:
                    with _plock: _provider_ok["p"] = prov
                    return items
                break
            except Exception as e:
                last = e
                msg = str(e).lower()
                if any(w in msg for w in ["timed out", "timeout", "429", "connection", "reset", "503", "502"]):
                    time.sleep(3 * (attempt + 1) + random.random() * 2)   # network hiccup: back off, retry
                    continue
                break                                                     # data problem: try next provider
    raise RuntimeError(f"no provider worked: {type(last).__name__}: {str(last)[:200]}")


def game_stints(g, season, stype):
    poss = load_possessions(g["game_id"])
    H, A = g["home"], g["away"]
    rows, cur = [], None
    hs = as_ = 0                                   # running score
    skipped = 0
    for p in poss:
        evs = p.events
        if not evs: continue
        off = getattr(p, "offense_team_id", None)
        first = True
        for ev in evs:
            per = int(ev.period)
            hl, al = lineup(ev, H), lineup(ev, A)
            if hl is None or al is None:
                skipped += 1
                pts = event_points(ev)
                if pts: hs, as_ = (hs + pts, as_) if ev.team_id == H else (hs, as_ + pts)
                continue
            key = (per, hl, al)
            if cur is None or cur["key"] != key:
                plen = 720 if per <= 4 else 300
                t = float(ev.seconds_remaining)
                if cur is not None:
                    cur["end_sec"] = 0.0 if cur["period"] != per else t
                    rows.append(cur)
                if cur is None or cur["period"] != per:
                    t = float(plen)
                cur = dict(key=key, game_id=g["game_id"], season=season, season_type=stype, game_date=g["date"],
                           period=per, start_sec=t, end_sec=0.0, home_team=H, away_team=A,
                           home_players=hl, away_players=al, home_poss=0, away_poss=0,
                           home_pts=0, away_pts=0, start_margin=hs - as_)
            if first:                                # credit the possession to the 10 on the floor when it began
                if off == H: cur["home_poss"] += 1
                elif off == A: cur["away_poss"] += 1
                first = False
            pts = event_points(ev)
            if pts:
                if ev.team_id == H: cur["home_pts"] += pts; hs += pts
                elif ev.team_id == A: cur["away_pts"] += pts; as_ += pts
    if cur is not None:
        cur["end_sec"] = 0.0; rows.append(cur)
    for r in rows: r.pop("key")
    check = ""
    if g.get("home_pts") is not None and (hs, as_) != (int(g["home_pts"]), int(g["away_pts"])):
        check = f"score mismatch: parsed {hs}-{as_}, actual {g['home_pts']}-{g['away_pts']}"
    return rows, check, skipped


# ---------------- main loop ----------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="2000-01")
    ap.add_argument("--to", default="2025-26")
    ap.add_argument("--types", default="rs,po")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default="stints")
    ap.add_argument("--test", action="store_true")
    a, _ = ap.parse_known_args(argv)   # ignores Colab's own '-f kernel.json' argument
    os.makedirs(a.out, exist_ok=True)
    done_path, fail_path = os.path.join(a.out, "done_games.txt"), os.path.join(a.out, "failed_games.txt")
    done = set(open(done_path).read().split()) if os.path.exists(done_path) else set()
    lock = threading.Lock()

    if a.test:
        for season in ["2023-24", "2015-16", "2003-04"]:
            gl = game_list(season, "rs")
            if not gl: print(season, "no game list"); continue
            g = gl[len(gl) // 2]
            t0 = time.time()
            try:
                rows, check, skipped = game_stints(g, season, "rs")
            except Exception as e:
                print(f"{season} {g['game_id']}: FAILED {e}"); continue
            hp = sum(r["home_poss"] for r in rows); apo = sum(r["away_poss"] for r in rows)
            print(f"\n{season} game {g['game_id']} ({time.time()-t0:.1f}s, provider {_provider_ok['p']}): "
                  f"{len(rows)} stints, possessions {hp}/{apo}, points {sum(r['home_pts'] for r in rows)}-"
                  f"{sum(r['away_pts'] for r in rows)}, actual {g['home_pts']}-{g['away_pts']}  {check or 'OK'}"
                  + (f"  ({skipped} events with an incomplete lineup)" if skipped else ""))
            for r in rows[:3]: print("  ", {k: r[k] for k in COLS[4:]})
        print("\nIf the points match, run without --test to download everything.")
        return

    types = [t.strip() for t in a.types.split(",")]
    for season in seasons_between(a.frm, a.to):
        for st in types:
            gl = game_list(season, st)
            todo = [g for g in gl if g["game_id"] not in done]
            print(f"\n{season} {STYPE[st]}: {len(gl)} games, {len(todo)} to do")
            if not todo: continue
            path = os.path.join(a.out, f"stints_{season}_{st}.csv")
            new = not os.path.exists(path)
            f = open(path, "a", newline="", encoding="utf-8"); w = csv.DictWriter(f, fieldnames=COLS)
            if new: w.writeheader()
            n_ok = n_bad = 0; t0 = time.time()

            def work(g):
                time.sleep(random.random() * 0.8)          # be gentle with NBA.com
                return g, game_stints(g, season, st)

            with ThreadPoolExecutor(max_workers=a.workers) as ex:
                futs = {ex.submit(work, g): g for g in todo}
                for i, fu in enumerate(as_completed(futs), 1):
                    try:
                        g, (rows, check, skipped) = fu.result()
                        with lock:
                            w.writerows(rows); f.flush()
                            open(done_path, "a").write(g["game_id"] + "\n")
                            if check: open(fail_path, "a").write(f"{g['game_id']}\tWARN {check}\n")
                        n_ok += 1
                    except KeyboardInterrupt:
                        raise
                    except Exception as e:
                        n_bad += 1
                        with lock: open(fail_path, "a").write(f"{futs[fu]['game_id']}\t{type(e).__name__}: {str(e)[:200]}\n")
                    if i % 25 == 0 or i == len(todo):
                        rate = i / (time.time() - t0)
                        print(f"  {i}/{len(todo)}  ok {n_ok}  failed {n_bad}  ~{(len(todo)-i)/max(rate,1e-6)/60:.0f} min left in this season")
            f.close()
    print("\nAll done. Send me the stints folder (zip it), or run:  python rapm_engine.py stints/*.csv --window 3 --out rapm_results.csv")


def run(*args):
    """Colab / Jupyter:  run("--test")   or   run("--out", "/content/drive/MyDrive/stints")"""
    try:
        main(list(args))
    except KeyboardInterrupt:
        print("\nStopped. Run the same command again to pick up where you left off.")


if __name__ == "__main__":
    if "ipykernel" in sys.modules:      # pasted into a notebook cell: don't start a full download by accident
        print('Loaded. Next cell:  run("--test")   then   run("--out", "/content/drive/MyDrive/stints")')
    else:
        run(*sys.argv[1:])
