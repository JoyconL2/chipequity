exec(open("proj_lab13.py").read().split('if __name__ == "__main__":')[0])
# core continuity: of last season's top-5 / top-8 minute players, the minute share that is back
def core_cont(n):
    out = []
    for s, t, roster in zip(F13.season, F13.tid, [set(R[(R.season == s) & (R.tid == t)].p) for s, t in zip(F13.season, F13.tid)]):
        last = team_last.get((S[SI[s] - 1], t), {}); top = sorted(last.items(), key=lambda x: -x[1])[:n]; tot = sum(v for _, v in top) or 1
        out.append(sum(v for p, v in top if p in roster) / tot)
    return out
F13["core5"] = core_cont(5); F13["core8"] = core_cont(8)
for c in ("cont", "core5", "core8"):
    for g in (1, 2):
        F13[f"pc_{c}_{g}"] = F13.prev * F13[c] ** g
        F13[f"dx_{c}_{g}"] = F13.dX * F13[c] ** g
        run5([f"pc_{c}_{g}", "U", "X"], f"prev x {c}^{g} + roster")
        run5([f"pc_{c}_{g}", "dX", "U", "X"], f"prev x {c}^{g} + change + roster")
F13["prev_nc"] = F13.prev * (1 - F13.core8)
run5(["prev", "prev_nc", "dX", "U", "X"], "prev + prev x (1-core8) + change + roster")
F13["star_aux"] = F13.top1 * F13.auxq
run5(["pc_core8_1", "dX", "U", "X", "star_aux"], "core8 + star x support")
F13.to_pickle("F14.pkl")
