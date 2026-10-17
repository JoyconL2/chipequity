"""Series win probability: best-of-7 / best-of-5, home court, symmetry."""
import numpy as np
from scipy.stats import norm
from fit_playoffs import series_pv


def bo(p, need):
    from math import comb
    return sum(comb(need - 1 + k, k) * p ** need * (1 - p) ** k for k in range(need))


def test_even_teams_neutral_floor():
    assert abs(series_pv(np.array([0.0]), np.array(["N"]), np.array([4]))[0] - 0.5) < 1e-9


def test_matches_closed_form():
    m = 12 * norm.ppf(0.6)                              # every game a 60% chance, no home court
    for need in (3, 4):
        got = series_pv(np.array([m]), np.array(["N"]), np.array([need]), hca=0)[0]
        assert abs(got - bo(0.6, need)) < 1e-9
    assert abs(bo(0.6, 4) - 0.7102) < 1e-4


def test_home_court_helps_and_is_symmetric():
    a = series_pv(np.array([0.0]), np.array(["A"]), np.array([4]))[0]
    b = series_pv(np.array([0.0]), np.array(["B"]), np.array([4]))[0]
    assert a > 0.5 and abs(a + b - 1) < 1e-9


def test_monotone_in_margin():
    ps = series_pv(np.linspace(-10, 10, 21), np.array(["N"] * 21), np.array([4] * 21))
    assert np.all(np.diff(ps) > 0)
