"""Build pbpstats.com-style season files that also cover 1996-97..1999-00.
Combines the box totals rebuilt from play-by-play (boxraw/, from stintbuild/run_box.sh) with the pbpstats.com
season totals for 2000-01 on (zip2/pbpstats_data/). Output: src96/Player_all_seasons.csv, Team_all_seasons.csv,
names_pre2000.json.  Then run:  cd mymodel && python features.py ../src96/"""
import glob, json, sys, tarfile
import numpy as np, pandas as pd
sys.path.insert(0, "stintbuild")
from derive_box import derive

names = {}
for Y in (1996, 1997, 1998, 1999):
    with tarfile.open(f"nbadata/datasets/nbastats_{Y}.tar.xz") as t:
        df = pd.read_csv(t.extractfile(t.getmembers()[0]), usecols=["PLAYER1_ID", "PLAYER1_NAME", "PLAYER2_ID", "PLAYER2_NAME"], dtype=str, keep_default_na=False)
    for a, b in (("PLAYER1_ID", "PLAYER1_NAME"), ("PLAYER2_ID", "PLAYER2_NAME")):
        for i, n in zip(df[a], df[b]):
            if i and n and i.isdigit(): names[int(i)] = n
names.setdefault(775, "Melvin Booker")
old = pd.read_csv("zip2/pbpstats_data/Player_all_seasons.csv", low_memory=False)
told = pd.read_csv("zip2/pbpstats_data/Team_all_seasons.csv", low_memory=False)
abbr = told.drop_duplicates("TeamId").set_index("TeamId").TeamAbbreviation.to_dict() if "TeamAbbreviation" in told else {}
pl, tm = [], []
for f in sorted(glob.glob("boxraw/box_199*_*.csv")):
    D = derive(pd.read_csv(f))
    D["SeasonType"] = np.where(D.season_type == "rs", "Regular Season", "Playoffs")
    D["Name"] = D.EntityId.map(names).fillna(D.EntityId.astype(str))
    D["TeamAbbreviation"] = D.TeamId.map(abbr)
    D["OnOffRtg"] = (D.PlusMinus + D.OpponentPoints) / D.OffPoss.clip(lower=1) * 100
    D["OnDefRtg"] = D.OpponentPoints / D.DefPoss.clip(lower=1) * 100
    pl.append(D)
    T = D.groupby(["Season", "SeasonType", "TeamId"], as_index=False)[["Points", "FG2A", "FG3A", "FTA", "OffPoss", "DefPoss"]].sum()
    T[["OffPoss", "DefPoss"]] /= 5; tm.append(T)
P = pd.concat(pl); T = pd.concat(tm)
import os; os.makedirs("src96", exist_ok=True)
cols = [c for c in old.columns if c in P.columns]
pd.concat([P[cols], old[cols]]).to_csv("src96/Player_all_seasons.csv", index=False)
tc = ["Season", "SeasonType", "TeamId", "Points", "FG2A", "FG3A", "FTA", "OffPoss", "DefPoss"]
pd.concat([T[tc], told[tc]]).to_csv("src96/Team_all_seasons.csv", index=False)
json.dump({str(k): v for k, v in names.items()}, open("src96/names_pre2000.json", "w"))
print("player rows", len(P), "| team rows", len(T))
