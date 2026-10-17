"""Replace every Basketball-Reference-sourced field in the site data with values computed from NBA.com
play-by-play (and pbpstats.com team totals for league averages):
  - team win-loss records (regular season and playoffs)          <- final scores of every game
  - playoff series (round, winner, loser, games won)              <- every playoff game
  - league averages per team-game (2000-01 on)                    <- pbpstats.com team season totals
The 2025-26 playoffs come from NBA.com's live play-by-play files for every game (the archive stops May 10, 2026);
SUPPLEMENT_2026 is only a fallback if those files are missing.
usage: python rebuild_no_bbref.py   (reads/writes data.json in this folder, prints a comparison)"""
import json, sys, tarfile
import numpy as np, pandas as pd

D = json.load(open("data.json"))
S = D["seasons"]; tid = D["teamIds"]; abbrs = D["abbrs"]
T = D["T"]
row_of = {(a, s, t): i for i, (a, s, t) in enumerate(zip(T["a"], T["s"], T["t"]))}
a_by_tid_season = {}
for a, s, t in zip(T["a"], T["s"], T["t"]):
    a_by_tid_season[(tid[a], s)] = a
HORNETS_OLD, HORNETS_NEW = 1610612766, 1610612740


def norm_team(t, season_idx):
    """old feeds mix the two Hornets franchise ids; map to whichever the site uses that season"""
    if (t, season_idx) in a_by_tid_season: return t
    other = {HORNETS_OLD: HORNETS_NEW, HORNETS_NEW: HORNETS_OLD}.get(t)
    return other if (other, season_idx) in a_by_tid_season else t


def games_nbastats(year, po):
    p = "po_" if po else ""
    with tarfile.open(f"../nbadata/datasets/nbastats_{p}{year}.tar.xz") as t:
        df = pd.read_csv(t.extractfile(t.getmembers()[0]), dtype=str, keep_default_na=False,
                         usecols=["GAME_ID", "HOMEDESCRIPTION", "VISITORDESCRIPTION", "PLAYER1_TEAM_ID", "SCORE"])
    out = []
    for g, x in df.groupby("GAME_ID", sort=True):
        if po and not str(int(g)).startswith("4"): continue            # skip play-in games
        h = x[(x.HOMEDESCRIPTION != "") & (x.VISITORDESCRIPTION == "") & (x.PLAYER1_TEAM_ID != "")].PLAYER1_TEAM_ID
        v = x[(x.VISITORDESCRIPTION != "") & (x.HOMEDESCRIPTION == "") & (x.PLAYER1_TEAM_ID != "")].PLAYER1_TEAM_ID
        sc = x[x.SCORE.str.contains(" - ")].SCORE
        if h.empty or v.empty or sc.empty: continue
        ap, hp = (int(s) for s in sc.iloc[-1].split(" - "))
        out.append((int(g), int(h.mode().iloc[0]), int(v.mode().iloc[0]), hp, ap))
    return pd.DataFrame(out, columns=["gid", "home", "away", "hp", "ap"])


def games_from_stints(season, stype):
    """final scores from our own stint files (built from NBA.com play-by-play)"""
    st = pd.read_csv(f"../stints/stints_{season}_{stype}.csv", dtype={"game_id": str})
    g = st.groupby("game_id").agg(home=("home_team", "first"), away=("away_team", "first"), hp=("home_pts", "sum"), ap=("away_pts", "sum")).reset_index()
    return pd.DataFrame({"gid": g.game_id.astype(int), "home": g.home, "away": g.away, "hp": g.hp, "ap": g.ap})


def games_cdn(po):
    p = "po_" if po else ""
    with tarfile.open(f"../nbadata/datasets/cdnnba_{p}2025.tar.xz") as t:
        df = pd.read_csv(t.extractfile(t.getmembers()[0]), dtype=str, keep_default_na=False,
                         usecols=["gameId", "teamId", "scoreHome", "scoreAway", "orderNumber"])
    out = []
    for g, x in df.groupby("gameId", sort=True):
        if po and not g.lstrip("0").startswith("4"): continue
        x = x.assign(o=pd.to_numeric(x.orderNumber), h=pd.to_numeric(x.scoreHome, errors="coerce"), a=pd.to_numeric(x.scoreAway, errors="coerce")).sort_values("o")
        H = A = None; ph = pa = 0
        for tm, h, a in zip(x.teamId, x.h.fillna(0), x.a.fillna(0)):
            if tm and h > ph and H is None: H = int(tm)
            if tm and a > pa and A is None: A = int(tm)
            ph, pa = max(ph, h), max(pa, a)
        if H and A: out.append((int(g), H, A, int(ph), int(pa)))
    return pd.DataFrame(out, columns=["gid", "home", "away", "hp", "ap"])


# remaining 2025-26 playoff games after the archive ends (May 10, 2026): winner, loser, extra wins, extra losses
# source: public game results (NBA.com recaps / team season pages), cross-checked against the series lengths
SUPPLEMENT_2026 = {   # (team A, team B): final series wins (A, B)
    ("SAS", "MIN"): (4, 2), ("OKC", "LAL"): (4, 0), ("NYK", "PHI"): (4, 0), ("CLE", "DET"): (4, 3),
    ("SAS", "OKC"): (4, 3), ("NYK", "CLE"): (4, 0), ("NYK", "SAS"): (4, 1)}


# three 2019-20 bubble games are missing from the play-by-play archive; final standings from public results
RECORD_FIX = {("2019-20", "TOR"): (53, 19), ("2019-20", "LAC"): (49, 23), ("2019-20", "IND"): (45, 28),
              ("2019-20", "OKC"): (44, 28), ("2019-20", "MIA"): (44, 29), ("2019-20", "DEN"): (46, 27)}


def series_from_games(G, si):
    G = G.copy(); G["pair"] = [tuple(sorted((h, a))) for h, a in zip(G.home, G.away)]
    G["winner"] = np.where(G.hp > G.ap, G.home, G.away)
    first = G.groupby("pair").gid.min().sort_values()
    runs, out = {}, []
    for pair, g0 in first.items():
        c = G[G.pair == pair].winner.value_counts()
        w = int(c.index[0]); l = pair[0] if pair[1] == w else pair[1]
        rnd = max(runs.get(w, 0), runs.get(l, 0)) + 1; runs[w] = runs[l] = rnd
        out.append([si, rnd, w, l, int(c.iloc[0]), int(c.iloc[1]) if len(c) > 1 else 0])
    return out


def wl(G, team):
    m = G[(G.home == team) | (G.away == team)]
    won = ((m.home == team) & (m.hp > m.ap)) | ((m.away == team) & (m.ap > m.hp))
    return int(won.sum()), int(len(m) - won.sum())


if __name__ == "__main__":
    old_series = {(r[0], r[2], r[3]): r for r in D["series"]}
    old_wl = {(a, s, t): (w, l) for a, s, t, w, l in zip(T["a"], T["s"], T["t"], T["w"], T["l"])}
    new_series, diffs_wl, n_wl = [], [], 0
    for si, season in enumerate(S):
        y = int(season[:4])
        Grs = games_cdn(False) if y == 2025 else games_nbastats(y, False)
        # 2025-26 playoffs: every game from NBA.com's live play-by-play (playbyplay_<id>.json), via our stints
        Gpo = games_from_stints(season, "po") if y == 2025 else games_nbastats(y, True)
        for G in (Grs, Gpo):
            G["home"] = [norm_team(t, si) for t in G.home]; G["away"] = [norm_team(t, si) for t in G.away]
        for t_, G in ((0, Grs), (1, Gpo)):
            for i, (a, s, tt) in enumerate(zip(T["a"], T["s"], T["t"])):
                if s != si or tt != t_: continue
                w, l = wl(G, tid[a])
                if t_ == 1 and w + l == 0: continue
                if old_wl.get((a, s, tt), (None, None))[0] not in (None, w) and t_ == 0: diffs_wl.append((season, abbrs[a], old_wl[(a, s, tt)], (w, l)))
                if t_ == 0 and (season, abbrs[a]) in RECORD_FIX: w, l = RECORD_FIX[(season, abbrs[a])]
                T["w"][i], T["l"][i] = w, l; n_wl += 1
        ser = series_from_games(Gpo, si)
        if y == 2025 and len(ser) < 15:   # only if some 2025-26 series are still missing from the play-by-play
            by = {(abbrs[a_by_tid_season[(r[2], si)]], abbrs[a_by_tid_season[(r[3], si)]]): r for r in ser}
            for (A, B), (wa, wb) in SUPPLEMENT_2026.items():
                ta, tb = tid[abbrs.index(A) if A != "CHA" else abbrs.index("CHA")], tid[abbrs.index(B)]
                r = by.get((A, B)) or by.get((B, A))
                if r is None:
                    rnd = 3 if (A, B) in (("SAS", "OKC"), ("NYK", "CLE")) else 4 if (A, B) == ("NYK", "SAS") else 2
                    ser.append([si, rnd, ta, tb, wa, wb])
                else:
                    r[2], r[3], r[4], r[5] = ta, tb, wa, wb
        for r in ser:
            r[2] = a_by_tid_season.get((r[2], si)); r[3] = a_by_tid_season.get((r[3], si))
            if r[2] is not None and r[3] is not None: new_series.append(r)
        print(season, "rs games", len(Grs), "| po games", len(Gpo), "| series", len(ser))
    # compare with the old (Basketball-Reference) series list
    new_keys = {(r[0], r[2], r[3]): r for r in new_series}
    missing = [k for k in old_series if k not in new_keys]; extra = [k for k in new_keys if k not in old_series]
    score_diff = [(S[k[0]], abbrs[k[1]], abbrs[k[2]], old_series[k][1:], new_keys[k][1:]) for k in old_series if k in new_keys and old_series[k][1:] != new_keys[k][1:]]
    print(f"\nseries: old {len(old_series)} new {len(new_series)} | missing {len(missing)} extra {len(extra)} | different {len(score_diff)}")
    for x in score_diff[:10]: print("  ", x)
    for k in missing[:10]: print("  missing", S[k[0]], abbrs[k[1]], abbrs[k[2]])
    for k in extra[:10]: print("  extra", S[k[0]], abbrs[k[1]], abbrs[k[2]])
    print(f"regular-season records changed: {len(diffs_wl)}"); [print("  ", x) for x in diffs_wl[:15]]
    D["series"] = sorted(new_series, key=lambda r: (r[0], r[1]))
    # league averages from pbpstats.com team totals (2000-01 on); 1996-97..1999-00 already come from play-by-play
    tt = pd.read_csv("../zip2/pbpstats_data/Team_all_seasons.csv", low_memory=False)
    tt = tt[tt.SeasonType == "Regular Season"]
    for si, season in enumerate(S):
        x = tt[tt.Season == season]
        if x.empty: continue
        tg = float(x.GamesPlayed.sum()); f = lambda c: float(x[c].fillna(0).sum())
        fgm, fga = f("FG2M") + f("FG3M"), f("FG2A") + f("FG3A"); ftm, fta = f("FtPoints"), f("FTA")
        tov = f("Turnovers"); pts = f("Points"); poss = (f("OffPoss") + f("DefPoss")) / 2
        r = {"G": int(tg / 2), "MP": round(5 * f("SecondsPlayed") / 60 / tg, 1), "FG": fgm / tg, "FGA": fga / tg, "3P": f("FG3M") / tg, "3PA": f("FG3A") / tg,
             "FT": ftm / tg, "FTA": fta / tg, "ORB": f("OffRebounds") / tg, "DRB": f("DefRebounds") / tg, "TRB": (f("OffRebounds") + f("DefRebounds")) / tg,
             "AST": f("Assists") / tg, "STL": f("Steals") / tg, "BLK": f("Blocks") / tg, "TOV": tov / tg, "PF": f("Fouls") / tg, "PTS": pts / tg,
             "FG%": fgm / fga, "3P%": f("FG3M") / f("FG3A"), "FT%": ftm / fta, "Pace": poss / (f("SecondsPlayed") / 2880),
             "eFG%": (fgm + 0.5 * f("FG3M")) / fga, "TOV%": 100 * tov / (fga + 0.44 * fta + tov), "TS%": pts / (2 * (fga + 0.44 * fta)), "Season": season}
        old = D["league"][si]
        D["league"][si] = {k: (round(v, 4) if isinstance(v, float) and k.endswith("%") and k != "TOV%" else round(v, 1) if isinstance(v, float) else v) for k, v in r.items()}
        if si in (4, 15, 29): print(season, "league PTS/TS%/Pace old", old.get("PTS"), old.get("TS%"), old.get("Pace"), "-> new", D["league"][si]["PTS"], D["league"][si]["TS%"], D["league"][si]["Pace"])
    json.dump(D, open("data.json", "w"), separators=(",", ":"), allow_nan=False)
    print("saved data.json")
