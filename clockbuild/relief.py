"""Clock relief for one season from NBA.com live play-by-play (the files update/fetch_season.py downloads), so the
season being played gets the same box-score input the history has.

  1  each game's live actions are rewritten in the older stats.nba.com event layout and every shot is placed in the
     possession with clock_build.py (unchanged), so the buckets are exactly the history's
  2  each shot is matched to the lineup on the floor (the season's stints file), as in clock_team.py
  3  clock relief = his team's share of shots that were late clock / transition / half court with 10+ s left, with him
     on minus with him off (per 100 shots), averaged over his teams; players with fewer than 300 shots on or off are
     left out (0 in the box-score inputs, as in the history)

usage: python clockbuild/relief.py <folder of playbyplay json> <season> <stints csv> <out csv>
out columns: EntityId, Season, o_relief_late, o_relief_early, o_relief_hc_early"""
import glob, json, os, re, subprocess, sys, tempfile
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "stintbuild"))
from live_fix import fix

CLK = re.compile(r"PT(\d+)M([\d.]+)S")
TYPE = {"rebound": 4, "turnover": 5, "foul": 6, "violation": 7, "substitution": 8, "timeout": 9, "jumpball": 10}
FT_LAST = {"1 of 1": 10, "2 of 2": 12, "3 of 3": 15}
BUCKETS = ("late", "early", "hc_early")


def events(gid, acts):
    """live actions -> rows in the stats.nba.com layout clock_build.py reads"""
    rows = []
    for i, a in enumerate(acts):
        m = CLK.match(a.get("clock") or "")
        clock = f"{int(m.group(1))}:{int(float(m.group(2))):02d}" if m else ""
        at, team = a.get("actionType"), a.get("teamId") or None
        pid = a.get("personId") or None
        r = {"GAME_ID": int(gid), "EVENTNUM": i, "PERIOD": a.get("period"), "PCTIMESTRING": clock, "EVENTMSGACTIONTYPE": 0,
             "HOMEDESCRIPTION": "", "VISITORDESCRIPTION": "", "PLAYER1_ID": pid, "PLAYER1_TEAM_ID": team}
        if at == "period" and a.get("subType") == "start": r["EVENTMSGTYPE"] = 12
        elif a.get("isFieldGoal") == 1 or at in ("2pt", "3pt"):
            made = a.get("shotResult") == "Made"
            r["EVENTMSGTYPE"] = 1 if made else 2
            r["HOMEDESCRIPTION"] = ("3PT " if at == "3pt" or "3PT" in (a.get("description") or "").upper() else "") + ("" if made else "MISS")
        elif at == "freethrow":
            r["EVENTMSGTYPE"] = 3; st = a.get("subType") or ""
            r["EVENTMSGACTIONTYPE"] = FT_LAST.get(st, 11)
            r["HOMEDESCRIPTION"] = ("MISS " if a.get("shotResult") != "Made" else "") + ("TECHNICAL" if "technical" in st.lower() or "flagrant" in st.lower() else "")
            if "technical" in st.lower(): r["EVENTMSGACTIONTYPE"] = 16
        elif at in TYPE: r["EVENTMSGTYPE"] = TYPE[at]
        else: continue
        if r["EVENTMSGTYPE"] in (4, 5) and not team: continue
        if r["EVENTMSGTYPE"] in (4,) and not pid: r["PLAYER1_ID"] = team     # team rebound: stats layout puts the team id there
        rows.append(r)
    return rows


def shots(folder, season, tmp):
    rows = []
    for f in sorted(glob.glob(os.path.join(folder, "*.json"))):
        gid = os.path.basename(f).split(".")[0][-10:]
        try: acts, _ = fix(json.load(open(f))["game"]["actions"])
        except Exception as e: print(f"::warning::clock relief: skipped {gid} ({e})"); continue
        rows += events(gid, acts)
    src, sh, out = os.path.join(tmp, "ev.csv"), os.path.join(tmp, "shots.csv"), os.path.join(tmp, "clock.csv")
    pd.DataFrame(rows).to_csv(src, index=False)
    r = subprocess.run([sys.executable, os.path.join(HERE, "clock_build.py"), src, season, out], env=dict(os.environ, SHOTS=sh), capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[-1500:])
    if r.returncode: sys.exit("clock_build failed")
    return pd.read_csv(sh)


def onoff(st, S):
    st = st.copy(); st["g"] = st.game_id.astype(int); S = S.copy(); S["g"] = S.game_id.astype(int)
    st = st.sort_values("start_sec"); out = []
    cols = ["start_sec", "end_sec", "home_team", "away_team", "home_players", "away_players"]
    stg = {k: v for k, v in st.groupby(["g", "period"])}
    for (g, p), x in S.groupby(["g", "period"]):
        y = stg.get((g, p))
        if y is None: continue
        out.append(pd.merge_asof(x.sort_values("left"), y[cols].sort_values("start_sec"), left_on="left", right_on="start_sec", direction="forward"))
    S = pd.concat(out); S = S[S.home_team.notna() & (S.left >= S.end_sec)]
    S["off"] = np.where(S.team_id == S.home_team, S.home_players, S.away_players)
    E = S[["team_id", "bucket", "off"]].assign(pid=S.off.astype(str).str.split("-")).explode("pid"); E["pid"] = E.pid.astype(int)
    on = E.groupby(["pid", "team_id", "bucket"]).size().unstack("bucket", fill_value=0)
    team = S.groupby(["team_id", "bucket"]).size().unstack("bucket", fill_value=0)
    rows = []
    for (pid, tm), r in on.iterrows():
        t = team.loc[tm]; non = r.sum(); noff = t.sum() - non
        if non < 300 or noff < 300: continue
        d = {"pid": pid, "w": 1 / (1 / non + 1 / noff)}
        for b in BUCKETS: d[f"o_relief_{b}"] = (r.get(b, 0) / non - (t.get(b, 0) - r.get(b, 0)) / noff) * 100
        rows.append(d)
    O = pd.DataFrame(rows)
    return O.groupby("pid").apply(lambda g: pd.Series({f"o_relief_{b}": np.average(g[f"o_relief_{b}"], weights=g.w) for b in BUCKETS}), include_groups=False).reset_index(), len(S)


if __name__ == "__main__":
    folder, season, stints, out = sys.argv[1:5]
    with tempfile.TemporaryDirectory() as tmp:
        S = shots(folder, season, tmp)
    A, n = onoff(pd.read_csv(stints, dtype={"game_id": str}), S)
    A = A.rename(columns={"pid": "EntityId"}); A.insert(1, "Season", season)
    A.to_csv(out, index=False)
    print(f"clock relief {season}: {n} shots matched to lineups, {len(A)} players")
