"""Every regular-season game since 1996-97 (NBA.com play-by-play), in order: season, gid, home, away, hp, ap."""
import sys; sys.path.insert(0, "../site")
import os; os.chdir("../site")
import pandas as pd, team_games as TG
out = []
for y in range(1996, 2026):
    season = f"{y}-{str(y + 1)[-2:]}"
    G = TG.cdn_games() if y == 2025 else TG.nbastats_games(y)
    G = G[G.gid.astype(str).str.lstrip("0").str.startswith("2")].copy()
    for c in ("home", "away"): G[c] = G[c].replace({1610612740: 1610612766} if y < 2002 else {})
    G["season"] = season; out.append(G[["season", "gid", "home", "away", "hp", "ap"]]); print(season, len(G), flush=True)
pd.concat(out).to_csv("../cur/games.csv", index=False)
