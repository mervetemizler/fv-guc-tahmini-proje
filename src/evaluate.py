# -*- coding: utf-8 -*-
"""Tek doğruluk kaynağı: tüm modeller için ortak değerlendirme (EVAL-01).

Girdiler W cinsindendir. Önce gece kuralı (y_sun_elev <= 0 -> 0) ve negatif kırpma
uygulanır, sonra MAE, RMSE, R2, nRMSE (payda config.CAPACITY_W) hesaplanır.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402

METRIC_COLS = ["MAE_W", "RMSE_W", "R2", "nRMSE", "MAE_kW", "RMSE_kW"]


def apply_night_rule(y_pred_W, y_sun_elev) -> np.ndarray:
    """Güneş ufkun altındaysa tahmin 0; negatifler 0'a kırpılır (idempotent)."""
    p = np.where(np.asarray(y_sun_elev) <= 0, 0.0, np.asarray(y_pred_W, dtype=np.float64))
    return np.clip(p, 0.0, None).astype(np.float64)


def metrics(y_true, y_pred, mask) -> dict:
    """Maskeli (pencere, ufuk) hücrelerini tek havuzda ölç."""
    if config.CAPACITY_W is None:
        raise ValueError("CAPACITY_W tanımsız; nRMSE paydası yok")
    mask = np.asarray(mask, dtype=bool)
    n = int(mask.sum())
    nan = float("nan")
    out = dict(n=n, MAE_W=nan, RMSE_W=nan, R2=nan, nRMSE=nan, MAE_kW=nan, RMSE_kW=nan,
               capacity_W=float(config.CAPACITY_W))
    if n == 0:
        return out
    t = np.asarray(y_true, dtype=np.float64)[mask]
    p = np.asarray(y_pred, dtype=np.float64)[mask]
    err = p - t
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    ss_tot = float(np.sum((t - t.mean()) ** 2))
    r2 = float(1.0 - np.sum(err ** 2) / ss_tot) if ss_tot > 0 else nan
    out.update(MAE_W=mae, RMSE_W=rmse, R2=r2, nRMSE=rmse / config.CAPACITY_W,
               MAE_kW=mae / 1000.0, RMSE_kW=rmse / 1000.0)
    return out


def _masks(y_day):
    y_day = np.asarray(y_day).astype(bool)
    return {"day": y_day, "all": np.ones_like(y_day, dtype=bool)}


def _scopes(shape):
    h4 = np.zeros(shape, dtype=bool)
    h4[:, config.MAIN_HORIZON_STEPS - 1] = True
    return {"mean16": np.ones(shape, dtype=bool), "h4": h4}


def evaluate(y_true_W, y_pred_W, y_sun_elev, y_day, model, seed=None) -> list[dict]:
    y_true_W = np.asarray(y_true_W)
    assert y_true_W.ndim == 2 and y_true_W.shape[1] == config.HORIZON, y_true_W.shape
    assert np.asarray(y_pred_W).shape == y_true_W.shape
    pred = apply_night_rule(y_pred_W, y_sun_elev)
    scopes = _scopes(y_true_W.shape)
    rows = []
    for mname, m in _masks(y_day).items():
        for sname, s in scopes.items():
            rows.append({"model": model, "seed": seed, "mask": mname, "scope": sname,
                         **metrics(y_true_W, pred, m & s)})
    return rows


def per_horizon(y_true_W, y_pred_W, y_sun_elev, y_day, model, seed=None, mask="day") -> list[dict]:
    pred = apply_night_rule(y_pred_W, y_sun_elev)
    base = _masks(y_day)[mask]
    rows = []
    for h in range(config.HORIZON):
        m = np.zeros_like(base)
        m[:, h] = base[:, h]
        rows.append({"model": model, "seed": seed, "mask": mask, "horizon_step": h + 1,
                     "horizon_min": 15 * (h + 1), **metrics(y_true_W, pred, m)})
    return rows


def season_metrics(y_true_W, y_pred_W, y_sun_elev, y_day, season, model, seed=None) -> list[dict]:
    season = np.asarray(season)
    pred = apply_night_rule(y_pred_W, y_sun_elev)
    y_day = np.asarray(y_day).astype(bool)
    rows = []
    for s in range(4):
        sel = season == s
        rows.append({"model": model, "seed": seed, "mask": "day", "scope": "mean16",
                     "season": s, "season_name": config.SEASON_NAMES[s],
                     **metrics(np.asarray(y_true_W)[sel], pred[sel], y_day[sel])})
    return rows


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["model", "mask", "scope"], sort=False)
    parts = {"n_runs": g.size()}
    for c in METRIC_COLS:
        parts[c + "_mean"] = g[c].mean()
        parts[c + "_std"] = g[c].std(ddof=1)
    out = pd.DataFrame(parts).reset_index()
    for c in METRIC_COLS:
        out[c + "_std"] = np.where(out["n_runs"] == 1, 0.0, out[c + "_std"])
    return out


def main() -> None:
    with np.load(config.WINDOWS_NPZ["test"], allow_pickle=False) as z:
        d = {k: z[k] for k in z.files}
    rows = evaluate(d["y"], d["y"], d["y_sun_elev"], d["y_day"], "oracle")
    r = [x for x in rows if x["mask"] == "day" and x["scope"] == "mean16"][0]
    print(f"Duman kontrolü (oracle) gündüz/16-ort RMSE_W = {r['RMSE_W']:.4f}")
    print("EVALUATE_TAMAM")


if __name__ == "__main__":
    main()
