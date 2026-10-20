"""Split priors.csv (from box_prior.py) into one file per window size / decade for rapm_engine.py --prior."""
import pandas as pd
P = pd.read_csv("priors.csv")
for w in (2, 3, 4, 5):
    P[P.w == w].drop_duplicates(["window_end", "player"]).to_csv(f"prior_w{w}.csv", index=False)
for end, w, name in (("1999-00", 4, "dec1990"), ("2009-10", 10, "dec2000"), ("2019-20", 10, "dec2010"), (P[P.w >= 6].window_end.max(), int(P[P.w >= 6].sort_values("window_end").w.iloc[-1]) if (P.w >= 6).any() else 6, "dec2020")):
    P[(P.w == w) & (P.window_end == end)].drop_duplicates(["window_end", "player"]).to_csv(f"prior_{name}.csv", index=False)
print(P.groupby("w").size())
