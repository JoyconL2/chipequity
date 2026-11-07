"""Play-type profiles for every player-season (regular season), from play-by-play + shot charts.
Built only from signals that exist in every season since 1996-97 (descriptive tags like 'pullup' are too sparse in
older seasons to trust):
  Transition    shot within 7 s of his team gaining the ball on a defensive rebound or a turnover
  Putback       shot within 3 s of his team's offensive rebound
  Half court, by where the shot came from (shot chart distance) and whether made shots were assisted:
     rim (0-4 ft), mid-range (2-pointers beyond 4 ft), three
     self-created = unassisted share of his makes in that zone (shrunk toward the league rate) x his attempts there
     set up       = the rest (catch-and-shoot, cuts, rolls, lobs)
  Playmaking    assists, split by the shot they created (rim / mid / three / transition)
Output: playtypes.csv  (p, season, category counts: fga, fgm, pts; assists by zone)."""
import sys, re, tarfile, io, numpy as np, pandas as pd
DS = "../nbadata/datasets"
def season_of(y): return f"{y}-{str(y + 1)[2:]}"
def read_tar(name):
    with tarfile.open(f"{DS}/{name}.tar.xz") as t:
        m = [x for x in t.getmembers() if x.name.endswith(".csv")][0]; return pd.read_csv(t.extractfile(m), low_memory=False)
def clock(s, period):
    mm, ss = str(s).split(":")[:2]; rem = int(mm) * 60 + float(ss); return (720 if period <= 4 else 300) - rem
def events_nbastats(y):
    d = read_tar(f"nbastats_{y}"); sd = read_tar(f"shotdetail_{y}")
    dist = {(int(g), int(e)): int(x) for g, e, x in zip(sd.GAME_ID, sd.GAME_EVENT_ID, sd.SHOT_DISTANCE)}
    d = d[d.EVENTMSGTYPE.isin([1, 2, 3, 4, 5])].copy()
    d["desc"] = d.HOMEDESCRIPTION.fillna("") + " " + d.VISITORDESCRIPTION.fillna("")
    out = []
    for r in d.itertuples(index=False):
        g = int(r.GAME_ID); per = int(r.PERIOD); t = clock(r.PCTIMESTRING, per); ty = r.EVENTMSGTYPE
        team = r.PLAYER1_TEAM_ID if pd.notna(r.PLAYER1_TEAM_ID) else r.PLAYER1_ID
        team = int(team) if pd.notna(team) else None
        p1 = int(r.PLAYER1_ID) if pd.notna(r.PLAYER1_ID) else None
        if ty in (1, 2):
            three = "3PT" in r.desc
            ds = dist.get((g, int(r.EVENTNUM)))
            if ds is None:
                m_ = re.search(r"(\d+)'", r.desc); ds = int(m_.group(1)) if m_ else (24 if three else (0 if re.search("Layup|Dunk|Tip", r.desc, re.I) else 12))
            ast = int(r.PLAYER2_ID) if ty == 1 and pd.notna(r.PLAYER2_ID) and r.PLAYER2_TEAM_ID == r.PLAYER1_TEAM_ID else None
            out.append((g, per, t, "fga", team, p1, ty == 1, 3 if three else 2, ds, ast))
        elif ty == 3:
            made = "MISS" not in r.desc.upper(); last = bool(re.search(r"(1 of 1|2 of 2|3 of 3)", r.desc))
            out.append((g, per, t, "ft", team, p1, made, last, None, None))
        elif ty == 4: out.append((g, per, t, "reb", team, p1, None, None, None, None))
        elif ty == 5: out.append((g, per, t, "tov", team, p1, None, None, None, None))
    return out
def events_cdn(y):
    d = read_tar(f"cdnnba_{y}"); out = []
    for r in d.itertuples(index=False):
        a = r.actionType; per = int(r.period)
        c = str(r.clock); m_ = re.match(r"PT(\d+)M([\d.]+)S", c); rem = int(m_.group(1)) * 60 + float(m_.group(2)) if m_ else 0
        t = (720 if per <= 4 else 300) - rem; team = int(r.teamId) if pd.notna(r.teamId) else None; p1 = int(r.personId) if pd.notna(r.personId) and r.personId else None
        g = int(r.gameId)
        if a in ("2pt", "3pt"):
            made = r.shotResult == "Made"; ds = int(r.shotDistance) if pd.notna(r.shotDistance) else (24 if a == "3pt" else 8)
            ast = int(r.assistPersonId) if made and pd.notna(r.assistPersonId) else None
            out.append((g, per, t, "fga", team, p1, made, 3 if a == "3pt" else 2, ds, ast))
        elif a == "freethrow":
            st = str(r.subType); made = r.shotResult == "Made"; last = st in ("1 of 1", "2 of 2", "3 of 3")
            out.append((g, per, t, "ft", team, p1, made, last, None, None))
        elif a == "rebound": out.append((g, per, t, "reb", team, p1, None, None, None, None))
        elif a == "turnover": out.append((g, per, t, "tov", team, p1, None, None, None, None))
    return out
def events_live(folder):
    """the season being played, from the NBA.com live play-by-play files the daily update downloads
    (same format as events_cdn; repaired first by stintbuild/live_fix.py, like the stints and box scores)"""
    import glob, json, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stintbuild"))
    from live_fix import fix
    out = []
    for f in sorted(glob.glob(os.path.join(folder, "*.json"))):
        try: A = json.load(open(f))["game"]["actions"]
        except Exception: continue
        A, _ = fix(A); g = int(os.path.basename(f).split(".")[0][-10:])
        for r in A:
            a = r.get("actionType"); per = int(r.get("period") or 0)
            m_ = re.match(r"PT(\d+)M([\d.]+)S", str(r.get("clock") or "")); rem = int(m_.group(1)) * 60 + float(m_.group(2)) if m_ else 0
            t = (720 if per <= 4 else 300) - rem; team = int(r["teamId"]) if r.get("teamId") else None; p1 = int(r["personId"]) if r.get("personId") else None
            if a in ("2pt", "3pt"):
                made = r.get("shotResult") == "Made"; ds = int(r["shotDistance"]) if r.get("shotDistance") is not None else (24 if a == "3pt" else 8)
                ast = int(r["assistPersonId"]) if made and r.get("assistPersonId") else None
                out.append((g, per, t, "fga", team, p1, made, 3 if a == "3pt" else 2, ds, ast))
            elif a == "freethrow":
                st = str(r.get("subType")); made = r.get("shotResult") == "Made"; last = st in ("1 of 1", "2 of 2", "3 of 3")
                out.append((g, per, t, "ft", team, p1, made, last, None, None))
            elif a == "rebound": out.append((g, per, t, "reb", team, p1, None, None, None, None))
            elif a == "turnover": out.append((g, per, t, "tov", team, p1, None, None, None, None))
    return out
def profile(events, season):
    acc = {}; ast = {}
    def add(p, cat, made, pts):
        a = acc.setdefault((p, cat), [0, 0, 0, 0]); a[0] += 1; a[1] += made; a[2] += pts * made
    last_g = None
    for (g, per, t, kind, team, p, made, x, ds, astp) in events:
        if g != last_g or per != last_per:
            last_g, last_per = g, per; poss, start, stype, last_miss_team, oreb_team, oreb_t = None, t, "period", None, None, -99
        if kind == "fga":
            if team != poss: poss, start, stype = team, t, stype if stype in ("dreb", "tov") else "other"
            if oreb_team == team and t - oreb_t <= 3: cat = "putback"
            elif stype in ("dreb", "tov") and t - start <= 7: cat = "transition"
            else: cat = "rim" if (x == 2 and ds <= 4) else ("mid" if x == 2 else "three")
            if p is not None:
                add(p, cat, bool(made), x)
                if cat in ("rim", "mid", "three") and made:
                    a = acc[(p, cat)]; a[3] += 0 if astp else 1          # unassisted makes
                if made and astp: z = ast.setdefault((astp, cat), 0); ast[(astp, cat)] = z + 1
            if made: poss, start, stype = None, t, "made"; oreb_team = None
            else: last_miss_team = team
        elif kind == "ft":
            if made and x: poss, start, stype = None, t, "made"; oreb_team = None
            elif not made and x: last_miss_team = team
        elif kind == "reb":
            if last_miss_team is not None and team == last_miss_team: oreb_team, oreb_t = team, t
            elif last_miss_team is not None: poss, start, stype = team, t, "dreb"; oreb_team = None
            last_miss_team = None
        elif kind == "tov":
            poss, start, stype = None, t, "tov"; oreb_team = None
            # possession passes to the other team; the next shot by the other team checks 'tov' timing
    rows = {}
    for (p, cat), a in acc.items():
        r = rows.setdefault(p, {"p": p, "season": season})
        r[f"{cat}_fga"] = a[0]; r[f"{cat}_fgm"] = a[1]; r[f"{cat}_pts"] = a[2]
        if cat in ("rim", "mid", "three"): r[f"{cat}_ua"] = a[3]
    for (p, cat), n in ast.items():
        r = rows.setdefault(p, {"p": p, "season": season}); r[f"ast_{cat}"] = n
    return list(rows.values())
if __name__ == "__main__":
    if sys.argv[1:2] == ["--live"]:                   # --live <folder of playbyplay json> <season> <out csv>
        folder, season, out = sys.argv[2:5]; ev = events_live(folder); rows = profile(ev, season)
        pd.DataFrame(rows).fillna(0).to_csv(out, index=False); print(season, len(ev), "events", len(rows), "players"); sys.exit(0)
    years = [int(a) for a in sys.argv[1:]] or list(range(1996, 2026))
    allrows = []
    for y in years:
        ev = events_cdn(y) if y == 2025 else events_nbastats(y)
        rows = profile(ev, season_of(y)); allrows += rows; print(season_of(y), len(ev), "events", len(rows), "players", flush=True)
    pd.DataFrame(allrows).fillna(0).to_csv(f"part_{years[0]}_{years[-1]}.csv", index=False)
