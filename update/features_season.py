"""Box-score features (mymodel/features.py) for the season being played, from its play-by-play box totals, appended
to the frozen history in mymodel/features_rs.csv. Every feature is relative to that season's own league average,
so one season can be built on its own (the same way 1996-97..1999-00 were, mymodel/make_src96.py).

usage: python update/features_season.py <box_<season>_rs.csv> <season> <features_rs.csv (updated in place)> [relief csv]"""
import os, sys, subprocess, tempfile, json
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stintbuild"))
from derive_box import derive

box, season, feat = sys.argv[1:4]
W = pd.read_csv(box).fillna(0); W = W[(W.EntityId > 0) & (W.EntityId < 1610612700)]
D = derive(W)
D["SeasonType"] = "Regular Season"; D["Name"] = D.EntityId.astype(str); D["TeamAbbreviation"] = ""
D["OnOffRtg"] = (D.PlusMinus + D.OpponentPoints) / D.OffPoss.clip(lower=1) * 100
D["OnDefRtg"] = D.OpponentPoints / D.DefPoss.clip(lower=1) * 100
T = D.groupby(["Season", "SeasonType", "TeamId"], as_index=False)[["Points", "FG2A", "FG3A", "FTA", "OffPoss", "DefPoss"]].sum()
T[["OffPoss", "DefPoss"]] /= 5
with tempfile.TemporaryDirectory() as d:
    src = d + "/src/"; os.makedirs(src)
    # features.py also builds a playoff table; a copy labeled "Playoffs" keeps it happy (that output is thrown away)
    pd.concat([D, D.assign(SeasonType="Playoffs")]).to_csv(src + "Player_all_seasons.csv", index=False)
    pd.concat([T, T.assign(SeasonType="Playoffs")]).to_csv(src + "Team_all_seasons.csv", index=False)
    subprocess.run([sys.executable, os.path.join(ROOT, "mymodel", "features.py"), src], cwd=d, check=True, stdout=subprocess.DEVNULL)
    new = pd.read_csv(d + "/features_rs.csv")
old = pd.read_csv(feat)
# assists: rim assists plus a quarter of the credit for the rest (mostly mid-range); threes on their own
new["o_ast_rim_mid"] = new.o_ast_rim + 0.25 * (new.o_ast - new.o_ast_rim - new.o_ast_three)
# clock relief (clockbuild/relief.py); players under 300 shots on or off the floor get 0, as in the history
RELIEF = ["o_relief_late", "o_relief_early", "o_relief_hc_early"]
if len(sys.argv) > 4 and os.path.exists(sys.argv[4]):
    R = pd.read_csv(sys.argv[4])[["EntityId"] + RELIEF]
    new = new.merge(R, on="EntityId", how="left")
for c in RELIEF: new[c] = new[c].fillna(0) if c in new else 0.0
new = new[old.columns.intersection(new.columns)]
out = pd.concat([old[old.Season != season], new], ignore_index=True)
out.to_csv(feat, index=False)
print(f"features {season}: {len(new)} player-team rows (history {len(old[old.Season != season])})")
