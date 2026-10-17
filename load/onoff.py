"""Raw on/off per player-season (regular season): team net with him on minus team net with him off."""
import glob, numpy as np, pandas as pd
out = []
for f in sorted(glob.glob("../stints/stints_*_rs.csv")):
    d = pd.read_csv(f, dtype={"game_id": str}, usecols=["season", "home_team", "away_team", "home_players", "away_players", "home_poss", "away_poss", "home_pts", "away_pts"])
    parts = []
    for side, opp in (("home", "away"), ("away", "home")):
        x = pd.DataFrame({"team": d[f"{side}_team"], "pl": d[f"{side}_players"].astype(str), "op": d[f"{side}_poss"], "pf": d[f"{side}_pts"], "dp": d[f"{opp}_poss"], "pa": d[f"{opp}_pts"]})
        parts.append(x)
    x = pd.concat(parts, ignore_index=True)
    tot = x.groupby("team")[["op", "pf", "dp", "pa"]].sum()
    e = x.assign(p=x.pl.str.split("-")).explode("p"); e["p"] = e.p.astype(int)
    on = e.groupby(["p", "team"])[["op", "pf", "dp", "pa"]].sum().reset_index()
    t = tot.loc[on.team].values; off = t - on[["op", "pf", "dp", "pa"]].values
    on["on_net"] = 100 * on.pf / on.op - 100 * on.pa / on.dp
    on["off_net"] = np.where(off[:, 0] > 0, 100 * off[:, 1] / np.maximum(off[:, 0], 1) - 100 * off[:, 3] / np.maximum(off[:, 2], 1), np.nan)
    on["onoff"] = on.on_net - on.off_net; on["season"] = d.season.iloc[0]
    out.append(on)
pd.concat(out).to_csv("onoff.csv", index=False); print("done")
