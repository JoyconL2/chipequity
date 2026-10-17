"""Does a recency-weighted CEPM (last season counts 1, the one before 0.5, then 0.25) predict team results better?"""
import sys, pandas as pd
SWAP = dict(a.split("=") for a in sys.argv[1:])
_rc = pd.read_csv
def rc(f, *a, **k):
    for x, y in SWAP.items():
        if str(f).endswith("/" + x): f = str(f)[:-len(x)] + y
    return _rc(f, *a, **k)
pd.read_csv = rc; sys.argv = sys.argv[:1]
exec(open("proj_lab12.py").read().split('def run4(')[0])
def run4(cols, label):
    p = loso(F, cols); p = p - p.groupby(F.season).transform("mean"); score(F, p, label)
run4(["prev", "dX", "U", "X"], f"standings-first, CEPM {SWAP or 'flat 3-yr'}")
run4(["X", "U"], f"roster only, CEPM {SWAP or 'flat 3-yr'}")
