"""Defensive play types for the site (data.json dpt and dmu).

dpt (every season since 1996-97, play-by-play): per player-season and season type, his defensive possessions and
  blocks by shot zone (rim / mid-range / three) and how many his team recovered, steals split into interceptions
  (bad-pass steals) and strips (lost-ball steals), charges drawn, shooting fouls, all fouls, defensive rebounds.
  Sources: boxraw/ (pbpstats parser on the play-by-play, 1996-97..1999-00) and pbpstats.com season totals (2000-01 on).

dmu (2017-18 on, NBA.com matchup tracking): per defender-season and season type, summed over every matchup:
  partial possessions guarded, points allowed, shots allowed (FG and 3PT, made / attempted), the shots his men
  would be expected to make at their own season percentages, the usage of the players he guarded, possessions on
  each team's top option (highest usage, 20+ mpg), on guards / forwards / centers (NBA.com listed position),
  switches onto him, shooting fouls, turnovers forced and blocks in his matchups.

usage: python def_build.py <scratch root> [data.json]"""
import glob, json, os, sys, tarfile
from collections import defaultdict
import numpy as np, pandas as pd

ROOT = sys.argv[1]; DJ = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "site", "data.json")
D = json.load(open(DJ)); S = D["seasons"]; SI = {s: i for i, s in enumerate(S)}; kOf = {int(p): k for k, p in enumerate(D["ids"])}

# ---------------- dpt: defensive events ----------------
EV = ["pos", "blk_rim", "blk_mid", "blk_3", "blk_rec", "stl_int", "stl_strip", "charges", "sfouls", "fouls", "dreb"]
acc = defaultdict(lambda: np.zeros(len(EV)))
def g(r, c): v = r.get(c, 0); return 0.0 if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
# 1996-97..1999-00 from the play-by-play rebuild (raw pbpstats keys)
Z = pd.read_csv(os.path.join(ROOT, "zip2", "pbpstats_data", "Player_all_seasons.csv"), low_memory=False)
ZS = set(Z.Season)
for f in sorted(glob.glob(os.path.join(ROOT, "boxraw", "box_*_*.csv"))):
    season, st = os.path.basename(f)[4:-4].rsplit("_", 1)
    if season in ZS: continue                                  # pbpstats.com has this season: don't count it twice
    W = pd.read_csv(f).fillna(0)
    for r in W.to_dict("records"):
        if not (0 < r["EntityId"] < 1610612700): continue
        dreb = sum(v for c, v in r.items() if c.endswith("DefRebounds") and isinstance(v, (int, float)))
        fouls = sum(v for c, v in r.items() if c.endswith("Fouls") and not c.endswith("Drawn") and "Technical" not in c and isinstance(v, (int, float)))
        acc[(int(r["EntityId"]), season, int(st == "po"))] += [g(r, "DefPoss"), g(r, "BlockedAtRim"), g(r, "BlockedShortMidRange") + g(r, "BlockedLongMidRange"),
            g(r, "BlockedArc3") + g(r, "BlockedCorner3"), sum(g(r, f"Blocked{z}Recovered") for z in ("AtRim", "ShortMidRange", "LongMidRange", "Arc3", "Corner3")),
            g(r, "BadPassSteals"), g(r, "LostBallSteals"), g(r, "Charge Fouls Drawn"), g(r, "Shooting Fouls"), fouls, dreb]
# 2000-01 on from pbpstats.com
for c in ["DefPoss", "BlockedAtRim", "BlockedShortMidRange", "BlockedLongMidRange", "BlockedArc3", "BlockedCorner3", "RecoveredBlocks", "BadPassSteals", "LostBallSteals", "Charge Fouls Drawn", "ShootingFouls", "Fouls", "DefRebounds"]:
    Z[c] = pd.to_numeric(Z[c], errors="coerce").fillna(0)
for _, r in Z.iterrows():
    acc[(int(r.EntityId), r.Season, int(r.SeasonType == "Playoffs"))] += [r.DefPoss, r.BlockedAtRim, r.BlockedShortMidRange + r.BlockedLongMidRange, r.BlockedArc3 + r.BlockedCorner3,
        r.RecoveredBlocks, r.BadPassSteals, r.LostBallSteals, r["Charge Fouls Drawn"], r.ShootingFouls, r.Fouls, r.DefRebounds]
dpt = []
for (pid, season, t), v in acc.items():
    k = kOf.get(pid); si = SI.get(season)
    if k is None or si is None or v[0] < 100: continue
    dpt.append([k, si, t] + [int(round(x)) for x in v])
D["dpt"] = {"cols": ["k", "s", "t"] + EV, "rows": dpt}
print("dpt rows", len(dpt))

# ---------------- dmu: matchups (2017-18 on) ----------------
P = pd.DataFrame(D["P"]); P["pid"] = [int(D["ids"][k]) for k in P.p]; P["season"] = [S[s] for s in P.s]
P["up"] = P.usg * P.pos
rs = P[P.t == 0].groupby(["pid", "season"]).agg(fg2m=("fg2m", "sum"), fg3m=("fg3m", "sum"), fg2a=("fg2a", "sum"), fg3a=("fg3a", "sum"))
u = P[P.t == 0].groupby(["pid", "season"]).agg(up=("up", "sum"), pos=("pos", "sum"))
rs["usg"] = (u.up / u.pos.clip(lower=1)).reindex(rs.index)
rs["fgp"] = (rs.fg2m + rs.fg3m) / (rs.fg2a + rs.fg3a).clip(lower=1); rs["tpp"] = rs.fg3m / rs.fg3a.clip(lower=1)
FGP = rs.fgp.to_dict(); TPP = rs.tpp.to_dict(); USG = rs.usg.to_dict()
# each team's top option: highest usage with 20+ minutes per game (team of most minutes), per season
pt_ = P[P.t == 0].copy(); pt_["mpg"] = pt_.sec / 60 / pt_.gp.clip(lower=1); pt_["tid"] = [int(D["teamIds"][a]) for a in pt_.tm]
TOP = {}
for (season, tid), g_ in pt_[(pt_.mpg >= 20) & (pt_.gp >= 20)].groupby(["season", "tid"]):
    TOP[(season, tid)] = int(g_.sort_values("usg", ascending=False).pid.iloc[0])
MU = ["mposs", "pts", "fgm", "fga", "fg3m", "fg3a", "xfgm", "xfga", "x3m", "x3a", "usgw", "uposs", "top", "g", "f", "c", "switch", "sfouls", "tov", "blk"]
dmu = []
for f in sorted(glob.glob(os.path.join(ROOT, "nbadata", "datasets", "matchups_*.tar.xz"))):
    base = os.path.basename(f)[9:-7]; po = base.startswith("po_"); y = int(base[3:] if po else base); season = f"{y}-{str(y + 1)[-2:]}"
    if season not in SI: continue
    with tarfile.open(f) as t:
        M = pd.read_csv(t.extractfile(t.getmembers()[0]), usecols=["person_id", "team_id", "position", "matchups_person_id", "partial_possessions", "player_points",
            "matchup_field_goals_made", "matchup_field_goals_attempted", "matchup_three_pointers_made", "matchup_three_pointers_attempted", "switches_on", "shooting_fouls", "matchup_turnovers", "matchup_blocks"])
    M = M[M.partial_possessions > 0]
    pos_of = M.dropna(subset=["position"]).groupby("person_id").position.agg(lambda x: x.value_counts().index[0]).to_dict()   # listed position (starts)
    M["xfgm"] = M.matchup_field_goals_attempted * M.person_id.map(lambda p: FGP.get((p, season), np.nan))
    M["x3m"] = M.matchup_three_pointers_attempted * M.person_id.map(lambda p: TPP.get((p, season), np.nan))
    M["xfga"] = M.matchup_field_goals_attempted.where(M.xfgm.notna(), 0); M["x3a"] = M.matchup_three_pointers_attempted.where(M.x3m.notna(), 0)
    M["usgw"] = M.partial_possessions * M.person_id.map(lambda p: USG.get((p, season), np.nan)); M["uposs"] = M.partial_possessions.where(M.usgw.notna(), 0)
    M["top"] = M.partial_possessions * [int(TOP.get((season, tid)) == p) for p, tid in zip(M.person_id, M.team_id)]
    pp = M.person_id.map(lambda p: pos_of.get(p, ""))
    for L in "GFC": M[L.lower()] = M.partial_possessions * (pp.str[0] == L)
    agg = M.groupby("matchups_person_id").agg(mposs=("partial_possessions", "sum"), pts=("player_points", "sum"), fgm=("matchup_field_goals_made", "sum"), fga=("matchup_field_goals_attempted", "sum"),
        fg3m=("matchup_three_pointers_made", "sum"), fg3a=("matchup_three_pointers_attempted", "sum"), xfgm=("xfgm", "sum"), xfga=("xfga", "sum"), x3m=("x3m", "sum"), x3a=("x3a", "sum"), usgw=("usgw", "sum"), uposs=("uposs", "sum"), top=("top", "sum"),
        g=("g", "sum"), f=("f", "sum"), c=("c", "sum"), switch=("switches_on", "sum"), sfouls=("shooting_fouls", "sum"), tov=("matchup_turnovers", "sum"), blk=("matchup_blocks", "sum"))
    n = 0
    for pid, r in agg.iterrows():
        k = kOf.get(int(pid))
        if k is None or r.mposs < (40 if po else 200): continue
        dmu.append([k, SI[season], int(po)] + [round(float(r[c]), 1) for c in MU]); n += 1
    print(season, "po" if po else "rs", "defenders", n)
D["dmu"] = {"cols": ["k", "s", "t"] + MU, "rows": dmu}
json.dump(D, open(DJ, "w"), separators=(",", ":"), allow_nan=False)
print("dmu rows", len(dmu))
