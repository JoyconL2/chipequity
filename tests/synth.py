"""Fake stints with known player values, for testing the RAPM engine."""
import numpy as np, pandas as pd


def make_stints(n_games=400, n_teams=6, per_team=9, seed=0, season="2020-21"):
    rng = np.random.default_rng(seed)
    players = {t: [1000 + t * 100 + i for i in range(per_team)] for t in range(n_teams)}
    o = {p: rng.normal(0, 3) for t in players for p in players[t]}
    d = {p: rng.normal(0, 2) for t in players for p in players[t]}
    rows = []
    for g in range(n_games):
        h, a = rng.choice(n_teams, 2, replace=False)
        margin = 0
        for k in range(12):                                   # 12 stints of 4 minutes
            hp = sorted(rng.choice(players[h], 5, replace=False)); ap = sorted(rng.choice(players[a], 5, replace=False))
            poss = 8
            hr = 110 + sum(o[p] for p in hp) - sum(d[p] for p in ap) + 1.5   # 1.5 = home court
            ar = 110 + sum(o[p] for p in ap) - sum(d[p] for p in hp)
            hpts = rng.poisson(max(hr, 1) * poss / 100); apts = rng.poisson(max(ar, 1) * poss / 100)
            per = k // 3 + 1; start = 720 - (k % 3) * 240
            rows.append(dict(game_id=f"00{g:08d}", season=season, game_date=f"2021-01-{1 + g % 28:02d}", period=per,
                             start_sec=start, end_sec=start - 240, home_team=h, away_team=a,
                             home_players="-".join(map(str, hp)), away_players="-".join(map(str, ap)),
                             home_poss=poss, away_poss=poss, home_pts=hpts, away_pts=apts, start_margin=margin))
            margin += hpts - apts
    truth = pd.DataFrame({"player": list(o), "o": list(o.values()), "d": [d[p] for p in o]})
    return pd.DataFrame(rows), truth
