"""Per team-season features for the playoff model, all known BEFORE the series starts.
 - cepm_roster : sum of 3-yr CEPM (window ending that regular season) x share of floor time, full regular season
 - cepm_late   : same, but floor time from the last 15 regular-season games (who's actually playing / healthy)
 - cepm_po     : for rounds 2+: floor time from this team's earlier playoff rounds (known before the series)
 - net_late    : net rating over the last 20 regular-season games
Writes team_feats.csv and player_game.parquet-ish csv."""
import glob
import numpy as np, pandas as pd

CEPM = pd.read_csv("../cepm/cepm3_rs.csv")
cv = {(int(p), s): r for p, s, r in zip(CEPM.player, CEPM.window_end, CEPM.rapm)}
REPL = -2.0   # players without a CEPM window (rookies / tiny minutes)

rows = []
for f in sorted(glob.glob("../stints/stints_*_rs.csv")) + sorted(glob.glob("../stints/stints_*_po.csv")):
    d = pd.read_csv(f, dtype={"game_id": str})
    d["secs"] = (d.start_sec - d.end_sec).clip(lower=0)
    for side, opp in (("home", "away"), ("away", "home")):
        x = d[["game_id", "season", "season_type", "game_date", f"{side}_team", f"{side}_players", "secs", f"{side}_pts", f"{opp}_pts", f"{side}_poss", f"{opp}_poss"]].copy()
        x.columns = ["game_id", "season", "stype", "date", "team", "players", "secs", "pf", "pa", "po", "pd"]
        rows.append(x)
S = pd.concat(rows, ignore_index=True)
print("stint-sides", len(S))

# team game results
G = S.groupby(["season", "stype", "team", "game_id", "date"], as_index=False)[["pf", "pa", "po", "pd"]].sum()
G = G.sort_values(["season", "stype", "team", "date", "game_id"])
# player seconds per game
P = S.assign(p=S.players.str.split("-")).explode("p")[["season", "stype", "team", "game_id", "date", "p", "secs"]]
P = P.groupby(["season", "stype", "team", "game_id", "date", "p"], as_index=False).secs.sum()
P.to_csv("player_game.csv", index=False)


def roster_value(pp, season):
    tot = pp.secs.sum()
    if tot <= 0: return np.nan
    v = np.array([cv.get((int(p), season), REPL) for p in pp.p])
    return float(5 * (v * pp.secs.values).sum() / tot)


out = []
for (season, team), g in G[G.stype == "rs"].groupby(["season", "team"]):
    pr = P[(P.season == season) & (P.stype == "rs") & (P.team == team)]
    games = g.sort_values("date").game_id.tolist()
    late = set(games[-15:])
    last20 = g[g.game_id.isin(games[-20:])]
    out.append(dict(season=season, team=team,
                    cepm_roster=roster_value(pr.groupby("p", as_index=False).secs.sum(), season),
                    cepm_late=roster_value(pr[pr.game_id.isin(late)].groupby("p", as_index=False).secs.sum(), season),
                    net_late=(last20.pf.sum() / last20.po.sum() - last20.pa.sum() / last20.pd.sum()) * 100))
TF = pd.DataFrame(out)
TF.to_csv("team_feats.csv", index=False)
print(TF.describe().round(2))
