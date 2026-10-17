import sys; sys.argv=[sys.argv[0]]
exec(open("proj_lab.py").read().split('if __name__ == "__main__":')[0])
# extra player inputs
R["c2_3"] = R[["c2", "c3rs"]].mean(axis=1, skipna=False)
prev_team = {}
for (s, t), plist in opening.items(): pass
# who played for the SAME team last season (continuity)
G_team_season = G.groupby(["season", "tid"]).p.apply(set).to_dict()
def feats(cep="c2", minutes="mpg", exp_split=False, min_gp=5):
    F = add_targets(team_features(R, cep_col=cep, minutes=minutes, umpg=UMPG_ALL, exp_split=exp_split, min_gp=min_gp))
    cont = []
    for s, t in zip(F.season, F.tid):
        sp = S[SI[s] - 1]; last = G_team_season.get((sp, t), set()); g = R[(R.season == s) & (R.tid == t)]
        m = g.mpg1.fillna(0).values; same = np.array([p in last for p in g.p])
        cont.append(m[same].sum() / max(m.sum(), 1e-9))
    F["cont"] = cont; F["prev_x_cont"] = F.prev * F.cont
    return F[F.prev.notna()].reset_index(drop=True)
res = []
F = feats("c2"); res.append(score(F, loso(F, ["X", "U", "prev"]), "R2-0 best so far: c2 + prev"))
res.append(score(F, loso(F, ["X", "U", "prev", "prev_x_cont"]), "R2-1 + last season's net x roster continuity"))
F2 = feats("c2_3"); res.append(score(F2, loso(F2, ["X", "U", "prev", "prev_x_cont"]), "R2-2 CEPM = avg of 2-yr and 3-yr(rs)"))
F3 = feats("c2", exp_split=True); res.append(score(F3, loso(F3, ["Xy", "Xp", "Xv", "U", "prev", "prev_x_cont"]), "R2-3 c2 split by experience + continuity"))
F4 = feats("c2", min_gp=1); res.append(score(F4, loso(F4, ["X", "U", "prev", "prev_x_cont"]), "R2-4 use CEPM even with <5 games last season"))
F5 = feats("c2", minutes="blend2"); res.append(score(F5, loso(F5, ["X", "U", "prev", "prev_x_cont"]), "R2-5 minutes blended over 2 seasons"))
json.dump(res, open("proj_lab_round2.json", "w"), indent=1)
