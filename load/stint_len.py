"""Average stint length: minutes a player stays on the floor each time he checks in (regular season).
A stint row = a stretch with no substitutions. A player 'checks in' when he's on the floor in a row but wasn't in the
previous row of the same game for his team (a quarter break doesn't count as a check-in if he was on at the end of the last quarter)."""
import glob, pandas as pd, numpy as np
out = []
for f in sorted(glob.glob("stints/stints_*_rs.csv")):
    d = pd.read_csv(f, dtype={"game_id": str}, usecols=["game_id", "season", "period", "start_sec", "end_sec", "home_team", "away_team", "home_players", "away_players"])
    d = d.sort_values(["game_id", "period", "start_sec"], ascending=[True, True, False]).reset_index(drop=True)
    d["row"] = np.arange(len(d)); d["dur"] = (d.start_sec - d.end_sec).clip(lower=0)
    parts = []
    for side in ("home", "away"):
        x = d[["game_id", "row", "dur", f"{side}_players"]].rename(columns={f"{side}_players": "pl"}); x["side"] = side
        x = x.assign(p=x.pl.str.split("-")).explode("p"); parts.append(x[["game_id", "side", "row", "dur", "p"]])
    x = pd.concat(parts); x["p"] = x.p.astype(int)
    # previous row index for the same game & side
    rows = d[["game_id", "row"]].copy(); rows["prev"] = rows.groupby("game_id").row.shift(1)
    x = x.merge(rows[["row", "prev"]], on="row")
    present = set(zip(x.side, x.row, x.p))
    x["entry"] = [not ((s, pr, p) in present) if pr == pr else True for s, pr, p in zip(x.side, x.prev, x.p)]
    g = x.groupby("p").agg(sec=("dur", "sum"), entries=("entry", "sum")).reset_index()
    g["season"] = d.season.iloc[0]; out.append(g); print(f, len(g), round(float((g.sec / 60 / g.entries.clip(lower=1))[g.sec > 60000].median()), 2), flush=True)
pd.concat(out).to_csv("load/stint_len.csv", index=False)
