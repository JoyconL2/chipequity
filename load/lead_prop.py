"""Proportional lead credit. In every stint (garbage time out), the team's margin is shared among the five players on the
floor in proportion to max(0, strength)^gamma, strength = 3-year rating + k x (involvement / league - 1), where
involvement = (shots + 0.44 FT + turnovers + assists) per possession on the floor, so playmakers count, not only scorers.
gamma = 1 is fully proportional; larger gamma concentrates credit on the best player (very large = the old all-to-one rule).
Writes, per config tag:  margin_attr_od_<tag>.csv, po_lead_<tag>.csv, tm_sums_<tag>.csv  (same columns the tests read)."""
import sys, json, numpy as np, pandas as pd
sys.argv = ["x"]; src = open("../rapm_engine.py").read(); exec(src[:src.index("def main(")])
CONFIGS = {"g1k0": (1, 0), "g1k2": (1, 2), "g2k0": (2, 0), "g2k2": (2, 2), "g4k2": (4, 2)}
d1 = pd.read_csv("../cepm/disp1.csv"); d3 = pd.read_csv("../cepm/disp3.csv")
m1 = {(int(p), s): r for p, s, r in zip(d1.player, d1.window_end, d1.rapm)}
R3 = {(int(p), s): (r, o, d) for p, s, r, o, d in zip(d3.player, d3.window_end, d3.rapm, d3.o_rapm, d3.d_rapm)}
BASE = {k: (R3[k][0] if k in R3 else v) for k, v in m1.items()}
D = json.load(open("../site/data.json")); S = D["seasons"]; ids = [int(x) for x in D["ids"]]
P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "pos", "fg2a", "fg3a", "fta", "tov", "ast")}); P = P[P.t == 0]
P["inv"] = P.fg2a + P.fg3a + 0.44 * P.fta + P.tov + P.ast
lg = (P.groupby("s").inv.sum() / P.groupby("s").pos.sum()).to_dict(); g = P.groupby(["p", "s"])[["inv", "pos"]].sum()
INV = {(ids[k], S[s]): min(2.0, max(0.5, (r.inv / r.pos) / lg[s])) for (k, s), r in g.iterrows() if r.pos > 0}
df = pd.read_pickle("../rapm_out/stints_all.pkl"); gt = garbage_time(df).values; df = df[~gt]
rs = df[df.season_type == "rs"]
LG, TS = {}, {}
for season, d in rs.groupby("season"):
    LG[season] = 100 * (d.home_pts.sum() + d.away_pts.sum()) / (d.home_poss.sum() + d.away_poss.sum())
    for side, opp in (("home", "away"), ("away", "home")):
        q = d.groupby(f"{side}_team")[[f"{side}_pts", f"{opp}_pts", f"{side}_poss", f"{opp}_poss"]].sum()
        for t, r in q.iterrows():
            a = TS.setdefault((season, t), [0, 0, 0, 0]); a[0] += r.iloc[0]; a[1] += r.iloc[1]; a[2] += r.iloc[2]; a[3] += r.iloc[3]
TSR = {k: (100 * a[0] / a[2] - LG[k[0]], LG[k[0]] - 100 * a[1] / a[3]) for k, a in TS.items()}
acc = {tag: {} for tag in CONFIGS}       # (p, season, stype) -> [n, pf, pa, tmo*n, tmd*n, oppD*n, oppO*n]
for (stype, season), d in df.groupby(["season_type", "season"]):
    for side, opp in (("home", "away"), ("away", "home")):
        pl = np.array([[int(x) for x in s.split("-")] for s in d[f"{side}_players"].values])
        poss = ((d[f"{side}_poss"] + d[f"{opp}_poss"]) / 2).values; pf = d[f"{side}_pts"].values; pa = d[f"{opp}_pts"].values
        ok = (poss > 0) & (pl.shape[1] == 5) if pl.ndim == 2 else None
        pl, poss, pf, pa = pl[ok], poss[ok], pf[ok], pa[ok]; ot = d[f"{opp}_team"].values[ok]
        base = np.vectorize(lambda p: BASE.get((p, season), -1.0))(pl); inv = np.vectorize(lambda p: INV.get((p, season), 1.0))(pl)
        to = np.vectorize(lambda p: R3.get((p, season), (0, 0, 0))[1])(pl); td = np.vectorize(lambda p: R3.get((p, season), (0, 0, 0))[2])(pl)
        tmo = to.sum(1, keepdims=True) - to; tmd = td.sum(1, keepdims=True) - td          # each player's four teammates
        od = np.array([TSR.get((season, t), (0, 0))[1] for t in ot]) if stype == "po" else np.zeros(len(ot))
        oo = np.array([TSR.get((season, t), (0, 0))[0] for t in ot]) if stype == "po" else np.zeros(len(ot))
        for tag, (gam, k) in CONFIGS.items():
            st = np.maximum(base + k * (inv - 1), 0) ** gam; tot = st.sum(1, keepdims=True)
            sh = np.where(tot > 0, st / np.where(tot > 0, tot, 1), 0.2)
            w = sh * poss[:, None]
            cols = np.stack([w, sh * pf[:, None], sh * pa[:, None], w * tmo, w * tmd, w * od[:, None], w * oo[:, None]], -1)  # (n,5,7)
            flat_p = pl.ravel(); flat = cols.reshape(-1, 7)
            dfa = pd.DataFrame(flat, columns=list("abcdefg")); dfa["p"] = flat_p; sums = dfa.groupby("p").sum()
            A = acc[tag]
            for p, r in zip(sums.index, sums.values):
                key = (int(p), season, stype); A[key] = A.get(key, 0) + r
    print(stype, season, flush=True)
PO0 = pd.read_csv("po_lead_r3.csv")[["p", "season", "po_share", "po_sec", "po_tsec"]]
for tag, A in acc.items():
    rows_rs, rows_po, rows_tm = [], [], []
    for (p, s, t), r in A.items():
        n = r[0]
        if n <= 0: continue
        lgv = LG[s]; off = 100 * r[1] / n - lgv; de = lgv - 100 * r[2] / n
        rows_tm.append(dict(p=p, season=s, stype=t, n=n, tmo=r[3] / n, tmd=r[4] / n))
        if t == "rs": rows_rs.append(dict(p=p, season=s, lead_poss=n, lead=off + de, lead_off=off, lead_def=de))
        else: rows_po.append(dict(p=p, season=s, n=n, off=off, de=de, lead=off + de, off_t=off + r[5] / n, de_t=de + r[6] / n))
    pd.DataFrame(rows_rs).to_csv(f"margin_attr_od_{tag}.csv", index=False); pd.DataFrame(rows_tm).to_csv(f"tm_sums_{tag}.csv", index=False)
    po = PO0.merge(pd.DataFrame(rows_po), on=["p", "season"], how="left").fillna({"n": 0, "off": 0, "de": 0, "lead": 0, "off_t": 0, "de_t": 0})
    po["lead_t"] = po.off_t + po.de_t; po.to_csv(f"po_lead_{tag}.csv", index=False)
    print(tag, len(rows_rs), len(rows_po))
