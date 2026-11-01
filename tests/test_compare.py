# -*- coding: utf-8 -*-
"""EVAL-07 birim testi: gün-bloklu bootstrap, gün SSE toplamı, karar kuralı (sentetik diziler yalnız test içindir)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from src import compare  # noqa: E402


def test_esit_fark_sifir():
    rng = np.random.default_rng(0)
    sse = np.arange(1.0, 21.0)
    cnt = np.full(20, 10)
    r = compare.bootstrap_diff(sse, sse.copy(), cnt, 200, rng)
    assert r["fark_W"] == 0 and r["ci_low"] == 0 and r["ci_high"] == 0 and not r["anlamli"], r


def test_yarim_sse_anlamli():
    rng = np.random.default_rng(0)
    sse_b = np.arange(10.0, 30.0)
    cnt = np.full(20, 10)
    r = compare.bootstrap_diff(sse_b / 2, sse_b, cnt, 500, rng)
    assert r["fark_W"] < 0 and r["ci_high"] < 0 and r["anlamli"], r


def test_day_sse_sayim():
    rng = np.random.default_rng(1)
    y = rng.random((12, 4))
    p = rng.random((12, 4))
    mask = rng.random((12, 4)) > 0.3
    wday = np.repeat(np.array(["2020-01-01", "2020-01-02", "2020-01-03"], dtype="datetime64[D]"), 4)
    days, sse, cnt = compare.day_sse(y, p, mask, wday)
    assert cnt.sum() == mask.sum() and len(days) == 3
    assert abs(sse.sum() - (((p - y) ** 2) * mask).sum()) < 1e-9


def test_verdict():
    assert compare.verdict(100.0, 100.5, 1.0) == "belirsiz"
    assert compare.verdict(90.0, 100.0, 1.0) == "evet"
    assert compare.verdict(110.0, 100.0, 1.0) == "hayır"

import pandas as pd  # noqa: E402


def _g():
    return pd.DataFrame({"mean": [300.0, 250.0, 200.0, 180.0, 170.0, 175.0],
                         "std": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0]},
                        index=["persistence", "seasonal_persistence", "linreg", "xgboost", "lstm", "cnn_lstm"])


def _ci(anlamli, fark, calls=None):
    def fn(a, b):
        if calls is not None:
            calls.append((a, b))
        return dict(anlamli=anlamli, fark_W=fark, ci_low=-1.5, ci_high=2.5, n_gun=7)
    return fn


def test_make_bootstrap_karar():
    r = compare._make("t", "k", _g(), _ci(False, -10.0))
    assert r["dl_baseline_gecti"] == "belirsiz" and r["karar_olcutu"] == "bootstrap"
    assert r["ci_low"] == -1.5 and r["ci_high"] == 2.5


def test_make_bootstrap_evet_hayir():
    assert compare._make("t", "k", _g(), _ci(True, -3.0))["dl_baseline_gecti"] == "evet"
    assert compare._make("t", "k", _g(), _ci(True, 3.0))["dl_baseline_gecti"] == "hayır"


def test_make_seed_std_fallback():
    r = compare._make("t", "k", _g(), None)
    assert r["karar_olcutu"] == "seed_std"
    assert np.isnan(r["ci_low"]) and np.isnan(r["ci_high"])
    assert r["dl_baseline_gecti"] == compare.verdict(170.0, 180.0, 1.0)


def test_make_seasonal_persistence():
    g = _g()
    g.loc["seasonal_persistence", "mean"] = 100.0
    calls = []
    r = compare._make("t", "k", g, _ci(True, 1.0, calls))
    assert r["en_iyi_baseline"] == "seasonal_persistence"
    assert calls == [("lstm", "seasonal_persistence")], calls


def test_subset_mask_genis_ci():
    rng = np.random.default_rng(0)
    n, d = 400, 40
    wday = np.repeat(np.arange(d), n // d).astype("datetime64[D]")
    y = rng.random((n, 4)) * 100
    pa = y + rng.normal(0, 10, (n, 4))
    pb = y + rng.normal(0, 12, (n, 4))
    w = {"y": y}
    preds = {("persistence", None): pa, ("linreg", None): pb}
    full = np.ones((n, 4), dtype=bool)
    sub = np.zeros((n, 4), dtype=bool)
    sub[wday == wday[0]] = True
    sub[wday == wday[10]] = True
    sub[wday == wday[20]] = True
    r_full = compare.subset_bootstrap("persistence", "linreg", preds, w, full, wday, np.random.default_rng(1))
    r_sub = compare.subset_bootstrap("persistence", "linreg", preds, w, sub, wday, np.random.default_rng(1))
    assert r_sub["n_gun"] == 3 and r_full["n_gun"] == d
    assert (r_sub["ci_high"] - r_sub["ci_low"]) > (r_full["ci_high"] - r_full["ci_low"])


if __name__ == "__main__":
    for name in ("test_esit_fark_sifir", "test_yarim_sse_anlamli", "test_day_sse_sayim", "test_verdict",
                 "test_make_bootstrap_karar", "test_make_bootstrap_evet_hayir", "test_make_seed_std_fallback",
                 "test_make_seasonal_persistence", "test_subset_mask_genis_ci"):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
