"""Ship the user's priors + market blend (proj_lab17.py): writes the coefficients into proj_params.json."""
import json
P = json.load(open("proj_params.json")); f = json.load(open("prior_fit.json"))
P.update({"form": "priors+market", "a": round(f["a"], 4), "bPC": round(f["pc"], 4), "bD": round(f["dX"], 4), "bU": round(f["U"], 4), "bX": round(f["X"], 4),
          "bTop1": f["b_top1"], "bAux": f["b_auxq"], "w_model": 0.5, "w_model_most_accurate": 0.3, "alloc_top": 5, "alloc_role_cap": [1.15, 2]})
P.pop("alloc_gamma", None)
P["star_rule"]["shrink"] = 1.0
P["backtest"]["priors"] = {"note": "user priors on purpose: last season's net x share of last season's top-8 core that returns; +0.3 net per CEPM point of the best player and +0.15 per point of support quality above league average",
    "wins_mae_model_current": 6.97, "wins_mae_priors": 7.11, "on_market_seasons": {"current_model": 7.78, "priors_model": 7.89, "market": 7.10, "priors_50_50_market": 7.25, "priors_30_70_market": 7.14}, "n_market": 180}
json.dump(P, open("proj_params.json", "w"), indent=1); print({k: P[k] for k in ("form", "a", "bPC", "bD", "bU", "bX", "bTop1", "bAux", "w_model")})
