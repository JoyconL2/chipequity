import sys; sys.argv=[sys.argv[0]]
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
# ---- winning experience, all from seasons BEFORE the one predicted ----
Gall = pd.read_csv(f"{SP}/pomodel/player_game.csv", dtype={"game_id": str})
po = Gall[Gall.stype == "po"].groupby(["p", "season"]).game_id.nunique().to_dict()          # playoff games per player-season
Gr = G.copy(); Gr["tnet"] = [prev_net.get((s, t), np.nan) for s, t in zip(Gr.season, Gr.tid)]
tn = Gr.groupby(["p", "season"]).apply(lambda x: np.average(x.tnet, weights=x["min"]) if x["min"].sum() > 0 else np.nan, include_groups=False).to_dict()
def last3(d, p, s, agg):
    i = SI[s]; vals = [d.get((p, S[j])) for j in range(max(0, i - 3), i)]; vals = [v for v in vals if v is not None and v == v]
    return agg(vals) if vals else np.nan
R["po3"] = [last3(po, p, s, sum) for p, s in zip(R.p, R.season)]; R["po3"] = R.po3.fillna(0)
R["win3"] = [last3(tn, p, s, np.mean) for p, s in zip(R.p, R.season)]
R["c3f"] = R.c3.fillna(R.c2)                       # 3-yr (with playoffs), 2-yr when a 3-yr window is missing

def feats(cep):
    rows = []
    for (s, t), g in R.groupby(["season", "tid"]):
        k = (g[cep].notna() & (g.gp1 >= 5)).values
        raw = np.where(k, g.mpg1.fillna(0).values, UMPG_ALL[s]); m = allocate(raw); sh = m / 48
        c = np.nan_to_num(g[cep].values)
        rows.append({"season": s, "tid": t, "X": (sh * c)[k].sum(), "U": sh[~k].sum(),
                     "PO": (sh * np.minimum(g.po3.values, 60) / 60).sum(),          # playoff experience share of the floor
                     "WIN": (sh * np.nan_to_num(g.win3.values))[~np.isnan(g.win3.values)].sum()})   # minutes-weighted past team net
    F = add_targets(pd.DataFrame(rows)); F = F[F.prev.notna() & (F.season >= "1999-00")].reset_index(drop=True)
    F["proj"] = 0.0; return F
def run(F, cols, label):
    p = loso(F, cols); p = p - p.groupby(F.season).transform("mean"); return score(F, p, label)
print("--- CEPM window, fair comparison (1999-00 on, every source available) ---")
for cep, lab in (("c2", "2-year (with playoffs)"), ("c3f", "3-year (with playoffs)"), ("c3rs", "3-year (regular season only)")):
    F = feats(cep); run(F, ["X", "U", "prev"], lab)
print("--- winning experience on top of the best ---")
for cep in ("c2", "c3f"):
    F = feats(cep)
    run(F, ["X", "U", "prev", "PO"], f"{cep} + playoff experience")
    run(F, ["X", "U", "prev", "WIN"], f"{cep} + experience on winning rosters")
    run(F, ["X", "U", "prev", "PO", "WIN"], f"{cep} + both")
