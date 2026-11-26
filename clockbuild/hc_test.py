"""Is early-clock half-court efficiency more sustainable and more playoff-proof than transition or late-clock creation?
Per player-season and shot bucket: points per shot above that season's league average for the bucket.
  1 sustainability  year-to-year correlation of each bucket (players with 100+ shots in that bucket both years),
                    put on a common 200-shot footing (Spearman-Brown) so bigger buckets don't win just by volume
  2 playoff-proof   regular-season bucket efficiency vs the same player's playoff efficiency (all shots, and half court)
  3 diet            does a regular-season shot diet heavy in transition / late clock mean a bigger playoff drop?"""
import glob, numpy as np, pandas as pd
B = ["early", "hc_early", "hc_mid", "late", "putback"]; LAB = {"early": "transition (first 7 s)", "hc_early": "half court, 10+ s left", "hc_mid": "half court, 7-10 s left", "late": "late clock, 6 s or less", "putback": "putbacks", "all": "all shots", "hc": "all half court"}
def load(pat):
    C = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(pat))]).groupby(["player_id", "season"], as_index=False).sum(numeric_only=True)
    C["hc_fga"] = C.hc_early_fga + C.hc_mid_fga + C.late_fga; C["hc_pts"] = C.hc_early_pts + C.hc_mid_pts + C.late_pts
    C["all_fga"] = C.fga; C["all_pts"] = C.pts
    for b in B + ["hc", "all"]:
        lg = C.groupby("season")[[f"{b}_fga", f"{b}_pts"]].sum(); r = (lg[f"{b}_pts"] / lg[f"{b}_fga"]).rename(f"lg_{b}")
        C = C.join(r, on="season"); C[f"eff_{b}"] = C[f"{b}_pts"] / C[f"{b}_fga"].replace(0, np.nan) - C[f"lg_{b}"]
    return C
RS, PO = load("/home/claude/clockout2/clock_*.csv"), load("/home/claude/clockout_po/clock_*_po.csv")
wcorr = lambda x, y, w: np.cov(x, y, aweights=w)[0, 1] / np.sqrt(np.cov(x, x, aweights=w)[0, 1] * np.cov(y, y, aweights=w)[0, 1])
def at200(r, n):                       # Spearman-Brown: correlation per shot, then at 200 shots
    r1 = r / (n - (n - 1) * r); return 200 * r1 / (1 + 199 * r1)
print(f"{RS.season.nunique()} regular seasons, {PO.season.nunique()} postseasons\n")
print("1  SUSTAINABLE: does this season's efficiency in the bucket repeat next season?")
RS["y"] = RS.season.str[:4].astype(int); nxt = RS.assign(y=RS.y - 1)
M = RS.merge(nxt, on=["player_id", "y"], suffixes=("", "_n"))
for b in B + ["hc", "all"]:
    m = M[(M[f"{b}_fga"] >= 100) & (M[f"{b}_fga_n"] >= 100)]; n = 2 / (1 / m[f"{b}_fga"] + 1 / m[f"{b}_fga_n"]); w = n
    r = wcorr(m[f"eff_{b}"], m[f"eff_{b}_n"], w)
    print(f"   {LAB[b]:26s} r {r:.2f} at a typical {np.median(n):4.0f} shots  ->  {at200(r, np.median(n)):.2f} at 200 shots   ({len(m)} player pairs)")
print("\n2  PLAYOFF-PROOF: regular-season efficiency in the bucket vs his playoff efficiency that year")
J = RS.merge(PO, on=["player_id", "season"], suffixes=("", "_po"))
for tgt in ("all", "hc"):
    print(f"   predicting playoff {LAB[tgt]}:")
    for b in B + ["hc", "all"]:
        m = J[(J[f"{b}_fga"] >= 100) & (J[f"{tgt}_fga_po"] >= 75)]; r = wcorr(m[f"eff_{b}"], m[f"eff_{tgt}_po"], m[f"{tgt}_fga_po"])
        print(f"      {LAB[b]:26s} r {r:.2f} with {np.median(m[f'{b}_fga']):4.0f} shots  ->  {at200(r, np.median(m[f'{b}_fga'])):.2f} at 200   ({len(m)})")
print("\n3  DIET: regular-season shot mix vs the change in efficiency from regular season to playoffs (all shots)")
m = J[(J.all_fga >= 400) & (J.all_fga_po >= 100)].copy(); m["drop"] = m.eff_all_po - m.eff_all
for b in ("early", "late", "hc_early", "putback"):
    m[f"share_{b}"] = m[f"{b}_fga"] / m.placed_fga
    q = pd.qcut(m[f"share_{b}"], 4, labels=["lowest", "2nd", "3rd", "highest"])
    g = m.groupby(q, observed=True).apply(lambda x: np.average(x["drop"], weights=x.all_fga_po), include_groups=False)
    print(f"   share of shots that are {LAB[b]:26s} quarters low->high, playoff change in pts/shot: " + "  ".join(f"{v:+.3f}" for v in g.values))
