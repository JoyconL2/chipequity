"""Share of competitive minutes: for each player-season (regular season), seconds he played outside garbage time
divided by his team's non-garbage seconds in the games he played. Garbage time = the CEPM definition (4th quarter,
big lead for the time left, 2 or fewer starters on the floor)."""
import sys, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
df = pd.read_pickle(__import__("os").environ.get("STINTS_PKL", "../rapm_out/stints_all.pkl")); df = df[df.season_type == "rs"].copy()
df["csecs"] = df.secs * (~garbage_time(df))
rows = []
for side in ("home", "away"):
    x = df[["game_id", "season", f"{side}_team", f"{side}_players", "secs", "csecs"]].rename(columns={f"{side}_team": "team", f"{side}_players": "pl"})
    rows.append(x)
x = pd.concat(rows, ignore_index=True)
team = x.groupby(["season", "team", "game_id"])[["secs", "csecs"]].sum().reset_index().rename(columns={"secs": "all", "csecs": "comp"})
e = x.assign(p=x.pl.str.split("-")).explode("p"); e["p"] = e.p.astype(int)
pg = e.groupby(["season", "team", "game_id", "p"])[["secs", "csecs"]].sum().reset_index().rename(columns={"secs": "sec", "csecs": "comp"})
pg = pg.merge(team.rename(columns={"all": "t_all", "comp": "t_comp"}), on=["season", "team", "game_id"])
out = pg.groupby(["p", "season"])[["sec", "comp", "t_all", "t_comp"]].sum().reset_index()
out["share_all"] = out.sec / out.t_all; out["share_comp"] = out.comp / out.t_comp
out.to_csv("comp_share.csv", index=False); print(len(out))
