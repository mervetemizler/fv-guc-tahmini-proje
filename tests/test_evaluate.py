# -*- coding: utf-8 -*-
"""EVAL-01 birim testi: metrikler, gece kuralı, özet.

Not: Buradaki sentetik değerler yalnızca mantık testi içindir.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config, evaluate  # noqa: E402


def test_metrik_elle():
    t = np.array([[0, 100, 200, 300]], float)
    p = np.array([[10, 90, 220, 300]], float)
    m = evaluate.metrics(t, p, np.ones_like(t, bool))
    assert m["n"] == 4
    assert np.isclose(m["MAE_W"], 10.0)
    assert np.isclose(m["RMSE_W"], np.sqrt(150.0))
    assert np.isclose(m["nRMSE"], m["RMSE_W"] / 1000.0)
    assert np.isclose(m["MAE_kW"], 0.01)
    assert np.isclose(m["R2"], 0.988)


def test_gece_kurali():
    p = np.array([[5.0, 50.0, -3.0, 20.0]])
    se = np.array([[-1.0, 0.0, 10.0, 10.0]])
    r = evaluate.apply_night_rule(p, se)
    assert np.allclose(r, [[0, 0, 0, 20]])
    assert np.allclose(evaluate.apply_night_rule(r, se), r)


def test_bos_maske_ve_sabit_hedef():
    t = np.full((2, 3), 5.0)
    p = np.full((2, 3), 6.0)
    m = evaluate.metrics(t, p, np.zeros_like(t, bool))
    assert m["n"] == 0 and all(np.isnan(m[k]) for k in ("MAE_W", "RMSE_W", "R2", "nRMSE"))
    m = evaluate.metrics(t, p, np.ones_like(t, bool))
    assert np.isnan(m["R2"]) and np.isclose(m["MAE_W"], 1.0)


def test_evaluate_satirlari():
    rng = np.random.default_rng(0)
    N, H = 5, config.HORIZON
    t = rng.uniform(0, 500, (N, H))
    p = t + rng.normal(0, 10, (N, H))
    se = np.ones((N, H))
    day = rng.random((N, H)) > 0.3
    rows = evaluate.evaluate(t, p, se, day, "x")
    assert len(rows) == 4
    assert {r["mask"] for r in rows} == {"day", "all"}
    assert {r["scope"] for r in rows} == {"mean16", "h4"}
    for r in rows:
        assert r["capacity_W"] == 1000.0
        if r["scope"] == "h4":
            exp = int(day[:, 3].sum()) if r["mask"] == "day" else N
            assert r["n"] == exp


def test_summarize():
    rows = []
    for s, v in zip((42, 43, 44), (10.0, 12.0, 14.0)):
        rows.append({"model": "a", "seed": s, "mask": "day", "scope": "mean16",
                     **{c: v for c in evaluate.METRIC_COLS}})
    rows.append({"model": "b", "seed": None, "mask": "day", "scope": "mean16",
                 **{c: 3.0 for c in evaluate.METRIC_COLS}})
    s = evaluate.summarize(pd.DataFrame(rows))
    a = s[s.model == "a"].iloc[0]
    b = s[s.model == "b"].iloc[0]
    assert a["n_runs"] == 3 and np.isclose(a["RMSE_W_std"], 2.0) and np.isclose(a["RMSE_W_mean"], 12.0)
    assert b["n_runs"] == 1 and b["RMSE_W_std"] == 0.0


def test_capacity_none():
    old = config.CAPACITY_W
    config.CAPACITY_W = None
    try:
        try:
            evaluate.metrics(np.ones((1, 2)), np.ones((1, 2)), np.ones((1, 2), bool))
        except ValueError:
            pass
        else:
            raise AssertionError("ValueError bekleniyordu")
    finally:
        config.CAPACITY_W = old


if __name__ == "__main__":
    for name in ("test_metrik_elle", "test_gece_kurali", "test_bos_maske_ve_sabit_hedef",
                 "test_evaluate_satirlari", "test_summarize", "test_capacity_none"):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
