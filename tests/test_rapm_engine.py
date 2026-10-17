"""The ridge engine should recover known player values from fake stints."""
import subprocess, sys, os
import numpy as np, pandas as pd
import rapm_engine as E
from synth import make_stints

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_recovers_known_values(tmp_path):
    st, truth = make_stints()
    f = tmp_path / "stints.csv"; st.to_csv(f, index=False)
    out = tmp_path / "out.csv"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "rapm_engine.py"), str(f), "--window", "1", "--min-poss", "50",
                        "--lam", "50", "--out", str(out)], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    res = pd.read_csv(out).merge(truth, on="player")
    assert len(res) == len(truth)
    assert np.corrcoef(res.rapm, res.o + res.d)[0, 1] > 0.85      # total impact
    assert np.corrcoef(res.o_rapm, res.o)[0, 1] > 0.8              # offense
    assert np.corrcoef(res.d_rapm, res.d)[0, 1] > 0.6              # defense (noisier)


def test_ridge_shrinks_toward_prior():
    rng = np.random.default_rng(1)
    import scipy.sparse as sp
    X = sp.csr_matrix(rng.normal(size=(40, 3))); y = rng.normal(size=40); w = np.ones(40)
    prior = np.array([5.0, -5.0, 2.0])
    b_huge = E.ridge(X, y, w, 1e9, n_players=3, prior=prior)
    assert np.allclose(b_huge, prior, atol=1e-3)                  # infinite penalty -> exactly the prior
    b_zero = E.ridge(X, y, w, 1e9, n_players=3)
    assert np.allclose(b_zero, 0, atol=1e-3)                      # no prior -> shrink to zero


def test_garbage_time_filter():
    df = pd.DataFrame({"period": [4, 4, 2, 4], "start_sec": [200, 200, 200, 700], "start_margin": [25, 25, 40, 5], "starters_on": [1, 6, 1, 1]})
    assert E.garbage_time(df).tolist() == [True, False, False, False]   # needs 4th quarter, big lead, mostly bench
