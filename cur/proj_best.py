"""Most accurate preseason projection (proj_lab18.py features: returning stars at full value, healthy form,
top-5 keep their usual minutes): standings-first model, unstretched, blended 40% model / 60% market."""
import json
P = json.load(open("proj_params.json"))
for k in ("bPC", "bTop1", "bAux", "alloc_gamma"): P.pop(k, None)
P.update({"form": "standings-first", "a": -0.2055, "bP": 0.482, "bD": 0.3156, "bU": -1.9627, "bX": 0.1748, "spread": 1.0, "spread_most_accurate": 1.0,
          "w_model": 0.4, "w_model_most_accurate": 0.4, "alloc_top": 5, "alloc_role_cap": [1.15, 2]})
P["star_rule"]["shrink"] = 1.0
P["backtest"]["best"] = {"wins_mae_model": 6.87, "wins_mae_model_x115": 6.82, "on_market_seasons": {"market": 7.10, "blend_40_60": 6.99, "blend_30_70_x115": 7.03, "shipped_priors_50_50": 7.25}, "n_market": 180,
    "spread_sd_wins": {"blend": 9.6, "market": 10.2, "actual": 12.5}}
P["backtest"].pop("priors", None)
json.dump(P, open("proj_params.json", "w"), indent=1); print({k: P[k] for k in ("form", "a", "bP", "bD", "bU", "bX", "spread", "w_model", "alloc_top")})
