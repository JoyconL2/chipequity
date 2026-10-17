"""The in-browser playoff model loads and its backtest runs on the base site data."""
import json, os, shutil, subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_model_backtest_runs():
    js = """
    const {buildModel} = require('./site/model.js'); const D = require('./site/data_2000.json');
    const M = buildModel(D); const r = M.backtest({wTop:0, wAv:0});
    console.log(JSON.stringify({n:r.n, acc:r.acc, ll:r.logloss, seasons:D.seasons.length}));"""
    out = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["n"] == 390 and r["seasons"] == 26
    assert 0.68 < r["acc"] < 0.80          # team strength alone picks ~72% of series
    assert r["ll"] < 0.6
