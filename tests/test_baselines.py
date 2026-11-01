# -*- coding: utf-8 -*-
"""Baseline birim testi: persistence, mevsimsel indeks, tablo öznitelikleri.

Not: Buradaki sentetik diziler YALNIZCA mantık testi içindir.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from src import baselines, config  # noqa: E402

FN = np.array(config.INPUT_FEATURES)
AC = list(FN).index(config.TARGET)


def _X(n=3):
    return np.random.default_rng(0).normal(size=(n, config.WINDOW, len(FN))).astype(np.float32)


def test_seasonal_indeks():
    X = _X()
    X[:, :, AC] = np.arange(config.WINDOW, dtype=np.float32)[None, :]
    s = baselines.seasonal_persistence(X, FN)
    assert s.shape == (3, 16)
    assert np.allclose(s[0], np.arange(16))


def test_persistence():
    X = _X()
    X[:, -1, AC] = 7
    p = baselines.persistence(X, FN)
    assert p.shape == (3, 16) and np.all(p == 7)


def test_tabular_sekil():
    X = _X()
    F, names = baselines.make_tabular_features(X, FN)
    assert F.shape == (3, 57) and len(names) == 57 and len(set(names)) == 57
    assert np.allclose(F[:, names.index("ac_power_lag0")], X[:, -1, AC])
    assert np.allclose(F[:, names.index("ac_power_dun_h1")], X[:, 0, AC])


def test_kanal_adla():
    X = _X()
    perm = np.random.default_rng(1).permutation(len(FN))
    F1, n1 = baselines.make_tabular_features(X, FN)
    F2, n2 = baselines.make_tabular_features(X[:, :, perm], FN[perm])
    assert n1 == n2 and np.allclose(F1, F2)


if __name__ == "__main__":
    for name in ("test_seasonal_indeks", "test_persistence", "test_tabular_sekil", "test_kanal_adla"):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
