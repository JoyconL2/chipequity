"""Regular-season team context from NBA.com play-by-play, for every season:
  SRS (Simple Rating System): average margin adjusted for strength of schedule, solved over every game
  defensive TS% allowed: opponents' points / (2 x (FGA + 0.44 FTA)) in games against the team
Output: team_context.csv (season, team_id, games, mov, sos, srs, ts_allowed)"""
import tarfile
import numpy as np, pandas as pd

ROOT = "../nbadata/datasets"


def nbastats_games(year):
    with tarfile.open(f"{ROOT}/nbastats_{year}.tar.xz") as t:
        df = pd.read_csv(t.extractfile(t.getmembers()[0]), dtype=str, keep_default_na=False,
                         usecols=["GAME_ID", "EVENTMSGTYPE", "HOMEDESCRIPTION", "VISITORDESCRIPTION", "PLAYER1_TEAM_ID", "SCORE"])
    df["typ"] = pd.to_numeric(df.EVENTMSGTYPE, errors="coerce")
    df["team"] = pd.to_numeric(df.PLAYER1_TEAM_ID, errors="coerce")
    out = []
    for g, x in df.groupby("GAME_ID", sort=True):
        h = x[(x.HOMEDESCRIPTION != "") & (x.VISITORDESCRIPTION == "") & x.team.notna()].team
        v = x[(x.VISITORDESCRIPTION != "") & (x.HOMEDESCRIPTION == "") & x.team.notna()].team
        sc = x[x.SCORE.str.contains(" - ")].SCORE
        if h.empty or v.empty or sc.empty: continue
        H, V = int(h.mode().iloc[0]), int(v.mode().iloc[0])
        ap, hp = (int(s) for s in sc.iloc[-1].split(" - "))
        fga = x[x.typ.isin([1, 2])].groupby("team").size(); fta = x[x.typ == 3].groupby("team").size()
        out.append((g, H, V, hp, ap, fga.get(H, 0), fta.get(H, 0), fga.get(V, 0), fta.get(V, 0)))
    return pd.DataFrame(out, columns=["gid", "home", "away", "hp", "ap", "h_fga", "h_fta", "a_fga", "a_fta"])


def cdn_games():
    with tarfile.open(f"{ROOT}/cdnnba_2025.tar.xz") as t:
        df = pd.read_csv(t.extractfile(t.getmembers()[0]), dtype=str, keep_default_na=False,
                         usecols=["gameId", "actionType", "teamId", "scoreHome", "scoreAway", "orderNumber"])
    df["o"] = pd.to_numeric(df.orderNumber); df["sh"] = pd.to_numeric(df.scoreHome, errors="coerce"); df["sa"] = pd.to_numeric(df.scoreAway, errors="coerce")
    df["team"] = pd.to_numeric(df.teamId, errors="coerce")
    out = []
    for g, x in df.sort_values("o").groupby("gameId", sort=True):
        H = A = None; ph = pa = 0
        for tm, h, a in zip(x.team, x.sh.fillna(0), x.sa.fillna(0)):
            if tm == tm and h > ph and H is None: H = int(tm)
            if tm == tm and a > pa and A is None: A = int(tm)
            ph, pa = max(ph, h), max(pa, a)
        if not (H and A): continue
        fga = x[x.actionType.isin(["2pt", "3pt"])].groupby("team").size(); fta = x[x.actionType == "freethrow"].groupby("team").size()
        out.append((g, H, A, int(ph), int(pa), fga.get(H, 0), fga.get(H, 0) * 0 + fta.get(H, 0), fga.get(A, 0), fta.get(A, 0)))
    return pd.DataFrame(out, columns=["gid", "home", "away", "hp", "ap", "h_fga", "h_fta", "a_fga", "a_fta"])


def srs(G):
    teams = sorted(set(G.home) | set(G.away)); ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    # least squares: margin(home - away) = r_home - r_away, with ratings summing to zero (no home-court term, like the usual SRS)
    A = np.zeros((len(G) + 1, n)); y = np.zeros(len(G) + 1)
    for k, (h, a, hp, ap) in enumerate(zip(G.home, G.away, G.hp, G.ap)):
        A[k, ix[h]] = 1; A[k, ix[a]] = -1; y[k] = hp - ap
    A[-1, :] = 1
    r = np.linalg.lstsq(A, y, rcond=None)[0]
    mov = {t: np.mean([(hp - ap) if h == t else (ap - hp) for h, a, hp, ap in zip(G.home, G.away, G.hp, G.ap) if t in (h, a)]) for t in teams}
    return {t: (r[ix[t]], mov[t]) for t in teams}


if __name__ == "__main__":
    rows = []
    for y in range(1996, 2026):
        season = f"{y}-{str(y + 1)[-2:]}"
        G = cdn_games() if y == 2025 else nbastats_games(y)
        G = G[G.gid.astype(str).str.lstrip("0").str.startswith("2")]          # regular season only
        for c in ("home", "away"): G[c] = G[c].replace({1610612740: 1610612766} if y < 2002 else {})
        R = srs(G)
        for t, (rating, mov) in R.items():
            vs_h = G[G.home == t]; vs_a = G[G.away == t]
            opp_pts = vs_h.ap.sum() + vs_a.hp.sum()
            opp_fga = vs_h.a_fga.sum() + vs_a.h_fga.sum(); opp_fta = vs_h.a_fta.sum() + vs_a.h_fta.sum()
            rows.append((season, t, len(vs_h) + len(vs_a), round(mov, 2), round(rating - mov, 2), round(rating, 2),
                         round(opp_pts / (2 * (opp_fga + 0.44 * opp_fta)), 4)))
        print(season, len(G), "games")
    out = pd.DataFrame(rows, columns=["season", "team_id", "games", "mov", "sos", "srs", "ts_allowed"])
    out.to_csv("team_context.csv", index=False)
    print(out.sort_values("srs", ascending=False).head(8).to_string(index=False))
