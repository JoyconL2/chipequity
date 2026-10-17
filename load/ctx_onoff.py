"""Star-controlled on/off. For each player, his team's net with him ON vs OFF is compared only inside the same
star context: the same set of the team's other needle-movers on the floor (none / A / B / A+B ...).
Needle-movers = the team's top 3 by 1-year CEPM that season (1,000+ possessions), plus anyone at +3 or better.
Each context's difference is weighted by the harmonic mean of its on and off possessions, so a context
needs real minutes both ways to count. Output per player-season: the weighted difference and its total weight."""
import glob, json, numpy as np, pandas as pd
C1 = pd.read_csv("../cepm/disp1.csv"); cep = {(int(p), s): (r, n) for p, s, r, n in zip(C1.player, C1.window_end, C1.rapm, C1.poss)}
out = []
for f in sorted(glob.glob("../stints/stints_*_rs.csv")):
    d = pd.read_csv(f, dtype={"game_id": str}, usecols=["season", "home_team", "away_team", "home_players", "away_players", "home_poss", "away_poss", "home_pts", "away_pts"])
    season = d.season.iloc[0]; parts = []
    for side, opp in (("home", "away"), ("away", "home")):
        parts.append(pd.DataFrame({"team": d[f"{side}_team"], "pl": d[f"{side}_players"].astype(str).str.split("-").apply(lambda x: frozenset(map(int, x))),
                                   "op": d[f"{side}_poss"], "pf": d[f"{side}_pts"], "dp": d[f"{opp}_poss"], "pa": d[f"{opp}_pts"]}))
    x = pd.concat(parts, ignore_index=True); x = x[(x.op > 0) | (x.dp > 0)]
    for team, g in x.groupby("team"):
        on = {}
        for pl, op in zip(g.pl, g.op):
            for p in pl: on[p] = on.get(p, 0) + op
        rated = [p for p in on if (p, season) in cep and cep[(p, season)][1] >= 1000]
        top3 = sorted(rated, key=lambda p: -cep[(p, season)][0])[:3]
        stars = set(top3) | {p for p in rated if cep[(p, season)][0] >= 3}
        pls = list(g.pl); op = g.op.values; pf = g.pf.values; dp = g.dp.values; pa = g.pa.values
        for p, poss in on.items():
            if poss < 300: continue
            others = stars - {p}
            ctx = [frozenset(s & others) for s in pls]; inp = np.array([p in s for s in pls])
            df = pd.DataFrame({"ctx": ctx, "on": inp.astype(int), "op": op, "pf": pf, "dp": dp, "pa": pa}).groupby(["ctx", "on"])[["op", "pf", "dp", "pa"]].sum()
            dd = {k: v for k, v in zip(df.index, df.itertuples(index=False))}
            num = W = 0.0
            for c in {k[0] for k in dd}:
                if (c, 1) not in dd or (c, 0) not in dd: continue
                a, b = dd[(c, 1)], dd[(c, 0)]
                if min(a.op, a.dp, b.op, b.dp) <= 0: continue
                dlt = (100 * a.pf / a.op - 100 * a.pa / a.dp) - (100 * b.pf / b.op - 100 * b.pa / b.dp)
                n1, n2 = (a.op + a.dp) / 2, (b.op + b.dp) / 2; w = 2 * n1 * n2 / (n1 + n2)
                num += w * dlt; W += w
            out.append(dict(season=season, team=team, player=p, poss=poss, ctx_onoff=num / W if W else np.nan, weight=W, n_stars=len(others)))
    print(season, len(out), flush=True)
pd.DataFrame(out).to_csv("ctx_onoff.csv", index=False)
