# -*- coding: utf-8 -*-
"""Sızıntısız bölme, train-only ölçekleme ve segment-içi kayan pencereler (PREP-03/04).

NOT (güvenlik, T-02-04): joblib yalnızca bu projenin kendi ürettiği SCALERS_FILE için
yüklenmelidir; npz dosyaları allow_pickle=False ile okunur.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from sklearn.preprocessing import StandardScaler

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402
from src import data  # noqa: E402

_STEP = pd.Timedelta(config.FREQ)


def season_of(months: np.ndarray) -> np.ndarray:
    """Ay numarasından mevsim kodu (0 Kış, 1 İlkbahar, 2 Yaz, 3 Sonbahar)."""
    return np.array([config.SEASON_BY_MONTH[int(m)] for m in months], dtype=np.int8)


def assign_segments(index: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Her ızgara adımına bin başlangıcına göre split adı ve global segment_id atar."""
    bin_start = index - _STEP
    split = np.full(len(index), "", dtype=object)
    seg = np.full(len(index), -1, dtype=np.int64)
    count = np.zeros(len(index), dtype=int)
    sid = 0
    for name in ("train", "val", "test"):
        for start, end in config.SPLITS[name]:
            m = (bin_start >= pd.Timestamp(start)) & (bin_start < pd.Timestamp(end))
            m = np.asarray(m)
            split[m] = name
            seg[m] = sid
            count += m.astype(int)
            sid += 1
    assert (count > 0).all(), "Bölmeye atanmamış ızgara adımı var"
    assert (count == 1).all(), "Bir adım birden fazla segmente düşüyor"
    return split.astype(str), seg


def fit_scalers(grid: pd.DataFrame, train_mask: np.ndarray) -> tuple[StandardScaler, StandardScaler]:
    """Girdi (9 kanal) ve hedef için AYRI scaler; yalnızca train ızgara satırlarına fit."""
    x_scaler = StandardScaler().fit(grid.loc[train_mask, config.INPUT_FEATURES].to_numpy(float))
    y_scaler = StandardScaler().fit(grid.loc[train_mask, [config.TARGET]].to_numpy(float))
    return x_scaler, y_scaler


def make_segment_windows(
    A: np.ndarray,
    y_src: np.ndarray,
    times: np.ndarray,
    is_day: np.ndarray,
    sun_elev: np.ndarray,
    window: int = config.WINDOW,
    horizon: int = config.HORIZON,
    drop_all_night: bool = False,
) -> dict:
    """Tek bir segment içinde kayan pencereler. NaN içeren pencereler atılır."""
    T, C = A.shape
    empty = {
        "X": np.empty((0, window, C), np.float32),
        "y": np.empty((0, horizon), np.float32),
        "y_time": np.empty((0, horizon), "datetime64[ns]"),
        "t0_time": np.empty((0,), "datetime64[ns]"),
        "y_day": np.empty((0, horizon), bool),
        "y_sun_elev": np.empty((0, horizon), np.float32),
        "y_night": np.empty((0, horizon), bool),
        "n_candidates": 0,
        "n_dropped_nan": 0,
        "n_dropped_night": 0,
    }
    if T < window + horizon:
        return empty
    N = T - window - horizon + 1
    row_nan = np.isnan(A).any(axis=1)
    y_nan = np.isnan(y_src)
    bad_x = sliding_window_view(row_nan, window)[:N].any(axis=1)
    bad_y = sliding_window_view(y_nan[window:], horizon).any(axis=1)
    nan_bad = bad_x | bad_y
    y_day_all = sliding_window_view(np.asarray(is_day, bool)[window:], horizon)
    night_bad = ~y_day_all.any(axis=1) if drop_all_night else np.zeros(N, bool)
    keep = ~nan_bad & ~night_bad
    idx = np.nonzero(keep)[0]
    Xv = sliding_window_view(A, window, axis=0)[:N]  # (N, C, window)
    X = np.ascontiguousarray(Xv[idx].transpose(0, 2, 1), dtype=np.float32)
    yv = sliding_window_view(y_src[window:], horizon)
    y = np.ascontiguousarray(yv[idx], dtype=np.float32)
    ytv = sliding_window_view(times[window:], horizon)
    y_time = np.ascontiguousarray(ytv[idx])
    t0_time = np.ascontiguousarray(times[window - 1 : window - 1 + N][idx])
    y_day = np.ascontiguousarray(y_day_all[idx])
    sev = np.ascontiguousarray(sliding_window_view(sun_elev[window:], horizon)[idx], dtype=np.float32)
    return {
        "X": X,
        "y": y,
        "y_time": y_time,
        "t0_time": t0_time,
        "y_day": y_day,
        "y_sun_elev": sev,
        "y_night": sev <= 0,
        "n_candidates": int(N),
        "n_dropped_nan": int(nan_bad.sum()),
        "n_dropped_night": int((night_bad & ~nan_bad).sum()),
    }


_ARRAY_KEYS = ("X", "y", "y_time", "t0_time", "y_day", "y_sun_elev", "y_night")


def check_split_integrity(wins: dict, n_train_rows: int, x_scaler) -> None:
    """D-03 sızıntı assert'leri."""
    tr, va, te = wins["train"], wins["val"], wins["test"]
    assert te["y_time"].min() > tr["y_time"].max(), "Test hedefleri train'den sonra başlamıyor"
    assert va["y_time"].min() > tr["y_time"].max(), "Val hedefleri train'den sonra başlamıyor"
    inter = set(va["y_time"].ravel().tolist()) & set(te["y_time"].ravel().tolist())
    assert not inter, f"Val ve test hedef zamanları kesişiyor ({len(inter)} adım)"
    for name, w in wins.items():
        first_in = pd.DatetimeIndex(w["t0_time"] - (config.WINDOW - 1) * _STEP.to_timedelta64())
        last_y = pd.DatetimeIndex(w["y_time"][:, -1])
        _, s_first = assign_segments(first_in)
        _, s_last = assign_segments(last_y)
        assert (s_first == w["segment_id"]).all() and (s_last == w["segment_id"]).all(), (
            f"{name}: pencere segment sınırını aşıyor"
        )
        assert not np.isnan(w["X"]).any(), f"{name}: X içinde NaN var"
        assert not np.isnan(w["y"]).any(), f"{name}: y içinde NaN var"
    for name in ("train", "val"):
        assert wins[name]["y_day"].any(axis=1).all(), f"{name}: tamamı-gece pencere kalmış"
    seen = int(np.max(x_scaler.n_samples_seen_))
    assert seen == n_train_rows, f"Scaler train dışı satır görmüş: {seen} != {n_train_rows}"


def build_all_windows(grid: pd.DataFrame | None = None, save: bool = True) -> dict:
    """Izgaradan split başına pencere sözlüklerini üretir (isteğe bağlı kaydeder)."""
    if grid is None:
        grid = data.load_grid()
    split, seg = assign_segments(grid.index)
    train_mask = split == "train"
    x_scaler, y_scaler = fit_scalers(grid, train_mask)
    A_all = x_scaler.transform(grid[config.INPUT_FEATURES].to_numpy(float))
    y_all = grid[config.TARGET].to_numpy(float)
    times_all = grid.index.to_numpy()
    is_day_all = grid["is_day"].to_numpy(bool)
    sun_all = grid["sun_elevation"].to_numpy(float)

    wins: dict = {}
    summary: dict = {}
    for name in ("train", "val", "test"):
        parts = []
        seg_counts = {}
        dn = dd = 0
        for sid in np.unique(seg[split == name]):
            m = seg == sid
            r = make_segment_windows(
                A_all[m], y_all[m], times_all[m], is_day_all[m], sun_all[m],
                drop_all_night=name in config.DROP_ALL_NIGHT_SPLITS,
            )
            n = len(r["X"])
            r["segment_id"] = np.full(n, sid, dtype=np.int16)
            seg_counts[int(sid)] = n
            dn += r["n_dropped_nan"]
            dd += r["n_dropped_night"]
            parts.append(r)
        out = {k: np.concatenate([p[k] for p in parts]) for k in (*_ARRAY_KEYS, "segment_id")}
        bin_month = pd.DatetimeIndex(out["y_time"][:, 0] - _STEP.to_timedelta64()).month
        out["season"] = season_of(np.asarray(bin_month))
        N = len(out["X"])
        out["y_scaled"] = (
            y_scaler.transform(out["y"].reshape(-1, 1)).reshape(N, config.HORIZON).astype(np.float32)
        )
        out["feature_names"] = np.array(config.INPUT_FEATURES)
        wins[name] = out
        summary[name] = {
            "n_windows": int(N),
            "per_segment": seg_counts,
            "dropped_nan": int(dn),
            "dropped_all_night": int(dd),
            "all_night_windows_kept": int((~out["y_day"].any(axis=1)).sum()),
        }
    n_train_rows = int(train_mask.sum())
    check_split_integrity(wins, n_train_rows, x_scaler)
    summary["test"]["season_counts"] = {
        config.SEASON_NAMES[int(s)]: int((wins["test"]["season"] == s).sum()) for s in range(4)
    }
    summary["n_train_rows"] = n_train_rows
    if save:
        config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        for name, w in wins.items():
            np.savez(config.WINDOWS_NPZ[name], **w)
        joblib.dump(
            {"x": x_scaler, "y": y_scaler, "features": list(config.INPUT_FEATURES),
             "n_train_rows": n_train_rows},
            config.SCALERS_FILE,
        )
        with open(config.WINDOWS_SUMMARY, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    return wins


def load_windows(split: str) -> dict:
    """Kaydedilmiş pencereleri okur (allow_pickle=False)."""
    with np.load(config.WINDOWS_NPZ[split], allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def main() -> None:
    wins = build_all_windows()
    for name, w in wins.items():
        print(f"{name}: X{w['X'].shape} y{w['y'].shape}")
    print("PENCERE_TAMAM")


if __name__ == "__main__":
    main()
