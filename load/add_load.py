"""Add average stint length (minutes per check-in, regular season, all teams combined) to data.json as P.stint,
aligned with the P rows (same value on every row of that player-season). Used by Chip Equity's load."""
import json, pandas as pd
D = json.load(open("../site/data.json")); S = D["seasons"]; P = D["P"]
st = pd.read_csv("stint_len.csv"); st["len"] = st.sec / 60 / st.entries.clip(lower=1)
L = {(int(p), s): round(float(l), 2) for p, s, l, sec in zip(st.p, st.season, st.len, st.sec) if sec >= 600}
P["stint"] = [L.get((int(D["ids"][k]), S[s])) for k, s in zip(P["p"], P["s"])]
json.dump(D, open("../site/data.json", "w"), separators=(",", ":"), allow_nan=False)
print("rows with stint length:", sum(v is not None for v in P["stint"]), "of", len(P["stint"]))
