"""How clock usage shapes offense, at the team and lineup level.
Every shot (shots_<season>.csv.gz, from clock_build.py with SHOTS=) is matched to the lineup stint it came in, so we know
the five offensive players on the floor.
  team    : per team-season, offense (points per 100 possessions, vs league) against the share of its shots that were
            transition / half court with 10+ s left / 7-10 s / late clock (6 s or less) / putbacks
  on/off  : per player-season, his team's clock profile and points per shot with him on vs off the floor
usage: python clock_team.py <season> ...   -> /home/claude/clockteam/{team,onoff}_<season>.csv"""
import sys, os, lzma, numpy as np, pandas as pd
R = "/home/claude/basketball-done-right"; OUT = "/home/claude/clockteam"; os.makedirs(OUT, exist_ok=True)
BK = ["early", "hc_early", "hc_mid", "late", "putback", "other"]
def stints_file(s):
    for f in (f"{R}/base/stints_hist/stints_{s}_rs.csv.xz", f"{R}/base/stints/stints_{s}_rs.csv.xz", f"/tmp/claude-0/-home-claude/d45461d2-6819-5ccf-a7df-ceffda37ed81/scratchpad/stints_{s}_rs.csv"):
        if os.path.exists(f): return f
for s in sys.argv[1:]:
    f = stints_file(s); sh = f"/home/claude/shots/shots_{s}.csv.gz"
    if not f or not os.path.exists(sh): print(s, "missing", f, sh); continue
    st = pd.read_csv(lzma.open(f) if f.endswith(".xz") else f, dtype={"game_id": str}); st["g"] = st.game_id.astype(int)
    S = pd.read_csv(sh); S["g"] = S.game_id.astype(int)
    # attach each shot to its stint: same game and period, the stint that started at or after the shot's clock time with the smallest start
    st = st.sort_values("start_sec"); S = S.sort_values("left"); out = []
    for (g, p), x in S.groupby(["g", "period"]):
        y = st[(st.g == g) & (st.period == p)]
        if y.empty: continue
        m = pd.merge_asof(x.sort_values("left"), y[["start_sec", "end_sec", "home_team", "away_team", "home_players", "away_players", "home_poss", "away_poss", "home_pts", "away_pts"]].sort_values("start_sec"),
                          left_on="left", right_on="start_sec", direction="forward")
        out.append(m)
    S = pd.concat(out); S = S[S.home_team.notna() & (S.left >= S.end_sec)]
    S["off"] = np.where(S.team_id == S.home_team, S.home_players, S.away_players)
    print(f"{s}: {len(S)} shots matched to lineups")
    # team-season offense and clock profile (offense from all stints, garbage time included like the box score)
    T = pd.concat([st.rename(columns={"home_team": "team_id", "home_pts": "pts", "home_poss": "poss"})[["team_id", "pts", "poss"]],
                   st.rename(columns={"away_team": "team_id", "away_pts": "pts", "away_poss": "poss"})[["team_id", "pts", "poss"]]]).groupby("team_id").sum()
    T["ortg"] = T.pts / T.poss * 100
    prof = S.pivot_table(index="team_id", columns="bucket", values="pts", aggfunc="count", fill_value=0)
    eff = S.pivot_table(index="team_id", columns="bucket", values="pts", aggfunc="mean")
    T = T.join(prof.add_prefix("n_")).join(eff.add_prefix("ppa_")); T["season"] = s; T.to_csv(f"{OUT}/team_{s}.csv")
    # on/off: explode the five offensive players
    E = S[["team_id", "bucket", "pts", "off"]].assign(pid=S.off.str.split("-")).explode("pid"); E["pid"] = E.pid.astype(int)
    on = E.groupby(["pid", "team_id", "bucket"]).pts.agg(["count", "sum"]).unstack("bucket", fill_value=0)
    team = S.groupby(["team_id", "bucket"]).pts.agg(["count", "sum"]).unstack("bucket", fill_value=0)
    rows = []
    for (pid, tm), r in on.iterrows():
        t = team.loc[tm]; non = r["count"].sum(); noff = t["count"].sum() - non
        if non < 300 or noff < 300: continue
        d = {"pid": pid, "team_id": tm, "season": s, "shots_on": non, "shots_off": noff}
        for b in BK:
            c_on, c_off = r["count"].get(b, 0), t["count"].get(b, 0) - r["count"].get(b, 0)
            p_on, p_off = r["sum"].get(b, 0), t["sum"].get(b, 0) - r["sum"].get(b, 0)
            d[f"share_on_{b}"], d[f"share_off_{b}"] = c_on / non, c_off / noff
            d[f"ppa_on_{b}"], d[f"ppa_off_{b}"] = (p_on / c_on if c_on else np.nan), (p_off / c_off if c_off else np.nan)
        d["ppa_on"], d["ppa_off"] = r["sum"].sum() / non, (t["sum"].sum() - r["sum"].sum()) / noff
        rows.append(d)
    pd.DataFrame(rows).to_csv(f"{OUT}/onoff_{s}.csv", index=False)
