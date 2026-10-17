"""The LeBron test for everyone: each player's team net with him on and his co-star OFF, against the co-star on
and him OFF (regular season). Co-star = the teammate with the best 1-year CEPM that season (1,500+ possessions)."""
import glob, json, numpy as np, pandas as pd
D = json.load(open("../site/data.json")); ids = [int(x) for x in D["ids"]]; nm = {p: D["names"][k] for k, p in enumerate(ids)}
C1 = pd.read_csv("../cepm/disp1.csv"); C1 = C1[C1.poss >= 1500]; cep = {(int(p), s): r for p, s, r in zip(C1.player, C1.window_end, C1.rapm)}
out = []
for f in sorted(glob.glob("../stints/stints_*_rs.csv")):
    d = pd.read_csv(f, dtype={"game_id": str}, usecols=["season", "home_team", "away_team", "home_players", "away_players", "home_poss", "away_poss", "home_pts", "away_pts"])
    season = d.season.iloc[0]; parts = []
    for side, opp in (("home", "away"), ("away", "home")):
        parts.append(pd.DataFrame({"team": d[f"{side}_team"], "pl": d[f"{side}_players"].astype(str).str.split("-").apply(lambda x: frozenset(map(int, x))), "op": d[f"{side}_poss"], "pf": d[f"{side}_pts"], "dp": d[f"{opp}_poss"], "pa": d[f"{opp}_pts"]}))
    x = pd.concat(parts, ignore_index=True)
    for team, g in x.groupby("team"):
        on = {}
        for pl, op in zip(g.pl, g.op):
            for p in pl: on[p] = on.get(p, 0) + op
        stars = sorted([p for p, v in on.items() if (p, season) in cep and v >= 1500], key=lambda p: -cep[(p, season)])
        if len(stars) < 2: continue
        for a in stars[:3]:
            b = next(s for s in stars if s != a)                     # his best teammate
            ina = g.pl.apply(lambda s: a in s).values; inb = g.pl.apply(lambda s: b in s).values
            def net(mask): gg = g[mask]; return (100 * gg.pf.sum() / gg.op.sum() - 100 * gg.pa.sum() / gg.dp.sum(), int(gg.op.sum())) if gg.op.sum() > 0 else (np.nan, 0)
            (n_ab, p_ab), (n_a, p_a), (n_b, p_b), (n_0, p_0) = net(ina & inb), net(ina & ~inb), net(~ina & inb), net(~ina & ~inb)
            out.append(dict(season=season, team=team, player=a, name=nm.get(a, a), costar=nm.get(b, b), cepm1=cep[(a, season)], cepm1_costar=cep[(b, season)],
                            both=n_ab, solo=n_a, costar_solo=n_b, neither=n_0, poss_both=p_ab, poss_solo=p_a, poss_costar_solo=p_b, poss_neither=p_0))
R = pd.DataFrame(out); R["edge"] = R.solo - R.costar_solo; R.to_csv("costar.csv", index=False); print(len(R), "player-seasons")
