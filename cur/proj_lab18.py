"""Returning stars at full value (no 50% discount) + star-protecting minutes (minutes ~ raw^1.5, nobody above 40
or much past his usual role). Rebuild the features, refit the priors model, compare."""
import sys
src13 = open("proj_lab13.py").read().split('if __name__ == "__main__":')[0]
src13 = src13.replace("c = np.where(star, c * 0.5, c)", "c = np.where(star, c * SHRINK, c)")
src13 = src13.replace("m = allocate(np.where(k, mins, u))", "m = ALLOC(np.where(k, mins, u).astype(float))")
SHRINK = float(sys.argv[1]); GAM = float(sys.argv[2]); sys.argv = sys.argv[:1]
import numpy as np
def ALLOC(raw, cap=40.0):
    if GAM < 1:                                   # top-N keep their usual minutes, the rest share what's left
        n = int(round(GAM * 10)); o = np.argsort(-raw); m = np.zeros_like(raw); top = o[:n]; rest = o[n:]
        m[top] = np.minimum(raw[top], cap); left = 240 - m[top].sum()
        if left < 0: m[top] *= 240 / m[top].sum(); left = 0
        if len(rest): m[rest] = raw[rest] / raw[rest].sum() * left if raw[rest].sum() > 0 else left / len(rest)
        m[rest] = np.minimum(m[rest], raw[rest] * 1.15 + 2)            # bench can't balloon on a thin roster
        if m.sum() < 240 - 1e-6: m = m * 240 / m.sum()
        return np.minimum(m, cap)
    w = np.power(np.maximum(raw, 0.01), GAM); lim = np.minimum(cap, raw * 1.15 + 2); m = w / w.sum() * 240
    for _ in range(30):
        over = m > lim + 1e-9
        if not over.any(): break
        m = np.where(over, lim, m); free = m < lim - 1e-9
        rest = 240 - m[~free].sum(); m[free] = w[free] / w[free].sum() * rest
    return m
exec(src13)
src14 = open("proj_lab14.py").read().split("# core continuity")[1].split("for c in")[0]
exec("#" + src14)
F13.to_pickle(f"F18_{SHRINK}_{GAM}.pkl"); print("saved")
