# -*- coding: utf-8 -*-
"""PREP-04 birim testi: pencereleme, segment sınırı, NaN atma, gece filtresi, resample, scaler.

Not: Buradaki sentetik/deterministik diziler YALNIZCA mantık testi içindir;
model eğitimi gerçek veriyle yapılır.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config, data, windows  # noqa: E402

W, H = config.WINDOW, config.HORIZON


def _times(T, start="2020-01-01 00:15"):
    return pd.date_range(start, periods=T, freq="15min").to_numpy()


def _mk(T, C=3, nan_at=None, day=True, drop_all_night=False):
    A = np.tile(np.arange(T, dtype=float)[:, None], (1, C))
    y = np.arange(T, dtype=float)
    if nan_at is not None:
        A[nan_at, :] = np.nan
        y[nan_at] = np.nan
    is_day = np.full(T, day, dtype=bool)
    sun = np.where(is_day, 10.0, -10.0)
    return windows.make_segment_windows(
        A, y, _times(T), is_day, sun, window=W, horizon=H, drop_all_night=drop_all_night
    )


def test_sekil():
    r = _mk(300)
    assert r["X"].shape == (300 - 111, W, 3), r["X"].shape
    assert r["y"].shape == (189, H), r["y"].shape


def test_hizalama():
    T = 300
    r = _mk(T)
    times = _times(T)
    for i in (0, 10, 188):
        t0 = i + W - 1
        assert r["X"][i, -1, 0] == t0
        for k in range(H):
            assert r["y"][i, k] == t0 + 1 + k
            assert r["y_time"][i, k] == times[t0 + 1 + k]


def test_segment_siniri():
    r1, r2 = _mk(200), _mk(150)
    assert len(r1["X"]) + len(r2["X"]) == (200 - 111) + (150 - 111)
    # Birleştirilmiş tek dizide olsaydı 350-111 pencere olurdu; segment-içi üretim daha azdır
    assert len(r1["X"]) + len(r2["X"]) < 350 - 111


def test_nan_atma():
    T = 400
    base = _mk(T)["X"].shape[0]
    r = _mk(T, nan_at=200)
    assert base - r["X"].shape[0] == 112, base - r["X"].shape[0]
    assert not np.isnan(r["X"]).any() and not np.isnan(r["y"]).any()


def test_gece_filtresi():
    assert _mk(200, day=False, drop_all_night=True)["X"].shape[0] == 0
    assert _mk(200, day=False, drop_all_night=False)["X"].shape[0] == 200 - 111


def test_resample_sizinti():
    idx = pd.date_range("2020-01-01 00:01", periods=30, freq="1min")
    df = pd.DataFrame(
        {
            "ac_power": np.arange(1, 31, dtype=float),
            "poa_irradiance": 100.0,
            "ambient_temp": 5.0,
            "module_temp_1": 6.0,
            "is_day": 1.0,
        },
        index=idx,
    )
    ti = pd.date_range("2020-01-01 00:15", periods=2, freq="15min")
    res = data.resample_15min(df, target_index=ti)
    assert np.isclose(res["ac_power"].iloc[0], 8.0), res["ac_power"].iloc[0]
    assert np.isclose(res["ac_power"].iloc[1], 23.0), res["ac_power"].iloc[1]
    assert res["is_day"].dtype == bool and res["is_day"].all()


def test_resample_min_gecerli_dakika():
    idx = pd.date_range("2020-01-01 00:01", periods=30, freq="1min")
    ac = np.arange(1, 31, dtype=float)
    ac[:14] = np.nan  # ilk bin: 1 geçerli dakika (< MIN_VALID_MINUTES) -> NaN
    ac[15:22] = np.nan  # ikinci bin: 8 geçerli dakika -> geçerli
    df = pd.DataFrame({"ac_power": ac, "poa_irradiance": 100.0, "ambient_temp": 5.0,
                       "module_temp_1": 6.0, "is_day": 1.0}, index=idx)
    ti = pd.date_range("2020-01-01 00:15", periods=2, freq="15min")
    res = data.resample_15min(df, target_index=ti)
    assert np.isnan(res["ac_power"].iloc[0]), res["ac_power"].iloc[0]
    assert res["ac_power"].iloc[1] == res["ac_power"].iloc[1], "8 geçerli dakika yeterli olmalı"


def test_train_only_scaler():
    n = 50
    idx = pd.date_range("2020-01-01 00:15", periods=n, freq="15min")
    grid = pd.DataFrame(
        {c: np.arange(n, dtype=float) for c in config.INPUT_FEATURES}, index=idx
    )
    mask = np.zeros(n, dtype=bool)
    mask[:20] = True
    grid.iloc[20:] = 1e6  # val/test çok farklı değer
    xs, ys = windows.fit_scalers(grid, mask)
    assert np.allclose(xs.mean_, np.arange(20).mean()), xs.mean_
    assert int(np.max(xs.n_samples_seen_)) == 20
    assert np.isclose(ys.mean_[0], np.arange(20).mean())


def _grid_1col(values, start="2020-01-01 00:15"):
    idx = pd.date_range(start, periods=len(values), freq="15min")
    return pd.DataFrame({"ac_power": np.asarray(values, dtype=float)}, index=idx)


def test_fill_kisa_bosluk():
    """2 adımlık boşluk geçmiş değerle dolar; 3 adımlık ve baştaki NaN dolmaz; gelecek değer taşınmaz."""
    nan = np.nan
    g = _grid_1col([nan, 1.0, nan, nan, 4.0, 5.0, nan, nan, nan, 9.0])
    out, st = data.fill_short_gaps(g, max_steps=2)
    v = out["ac_power"].to_numpy()
    assert np.isnan(v[0]), "baştaki NaN doldurulmamalı"
    assert np.isclose(v[2], 1.0) and np.isclose(v[3], 1.0), "2 adım ileri doldurulmalı (geçmiş değer)"
    assert np.isnan(v[6:9]).all(), "3 adımlık boşluk doldurulmamalı"
    assert st["ac_power"]["filled_steps"] == 2, st
    assert st["ac_power"]["remaining_nan"] == 4, st


def test_segment_ay_siniri():
    """Bin başlangıcına göre: ay-sınırı damgası (D 00:00) önceki segmente, D 00:15 sonrakine ait."""
    y2 = config.Y2
    idx = pd.DatetimeIndex(
        [f"{y2}-01-31 23:45", f"{y2}-02-01 00:00", f"{y2}-02-01 00:15"]
    )
    split, seg = windows.assign_segments(idx)
    assert split[0] == "val" and split[1] == "val", split   # Ocak (tek ay) = val
    assert split[2] == "test", split                       # Şubat (çift ay) = test
    assert seg[0] == seg[1] and seg[1] != seg[2], seg
    # Y1 -> Y2 sınırı: Y2-01-01 00:00 damgası hâlâ train'e (Y1 son bini) aittir
    sp, _ = windows.assign_segments(pd.DatetimeIndex([f"{y2}-01-01 00:00", f"{y2}-01-01 00:15"]))
    assert sp[0] == "train" and sp[1] == "val", sp


if __name__ == "__main__":
    for name in (
        "test_sekil",
        "test_hizalama",
        "test_segment_siniri",
        "test_nan_atma",
        "test_gece_filtresi",
        "test_resample_sizinti",
        "test_resample_min_gecerli_dakika",
        "test_train_only_scaler",
        "test_fill_kisa_bosluk",
        "test_segment_ay_siniri",
    ):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
