# -*- coding: utf-8 -*-
"""Tüm modelleri (4 baseline + 6 DL koşusu) aynı evaluate() ile ölçer (EVAL-01/02).

Kullanım: python -m src.run_all [--partial]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402
from src import evaluate  # noqa: E402
from src import windows  # noqa: E402

RUNS = [("persistence", None), ("seasonal_persistence", None), ("linreg", None), ("xgboost", None)] + [
    (m, s) for m in ("lstm", "cnn_lstm") for s in config.SEEDS
]

METRIC_ORDER = ["n", "MAE_W", "RMSE_W", "R2", "nRMSE", "MAE_kW", "RMSE_kW", "capacity_W"]


def pred_path(model: str, seed) -> Path:
    name = f"{model}.npz" if seed is None else f"{model}_seed{seed}.npz"
    return config.PREDICTIONS_DIR / name


def collect(partial: bool = False) -> dict[str, pd.DataFrame]:
    w = windows.load_windows("test")
    y, elev, day, season = w["y"], w["y_sun_elev"], w["y_day"], w["season"]
    all_rows, season_rows, horizon_rows = [], [], []
    for model, seed in RUNS:
        p = pred_path(model, seed)
        if not p.exists():
            if partial:
                print(f"UYARI: {p.name} yok, atlandı")
                continue
            raise FileNotFoundError(p)
        with np.load(p, allow_pickle=False) as z:
            pred = z["y_pred_W"]
        assert pred.shape == y.shape, (p.name, pred.shape, y.shape)
        all_rows += evaluate.evaluate(y, pred, elev, day, model, seed)
        season_rows += evaluate.season_metrics(y, pred, elev, day, season, model, seed)
        for mask in ("day", "all"):
            horizon_rows += evaluate.per_horizon(y, pred, elev, day, model, seed, mask=mask)
    all_df = pd.DataFrame(all_rows)[["model", "seed", "mask", "scope"] + METRIC_ORDER]
    season_df = pd.DataFrame(season_rows)[
        ["model", "seed", "season_name", "n", "MAE_W", "RMSE_W", "R2", "nRMSE"]]
    horizon_df = pd.DataFrame(horizon_rows)[
        ["model", "seed", "mask", "horizon_step", "horizon_min", "n", "MAE_W", "RMSE_W", "R2", "nRMSE"]]
    summary = evaluate.summarize(all_df)
    summary_cols = ["model", "mask", "scope", "n_runs"] + [
        f"{c}_{s}" for c in evaluate.METRIC_COLS for s in ("mean", "std")]
    return {"all_metrics": all_df, "summary": summary[summary_cols],
            "season_metrics": season_df, "horizon_metrics": horizon_df}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--partial", action="store_true")
    args = ap.parse_args()
    out = collect(partial=args.partial)
    config.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        df.to_csv(config.METRICS_DIR / f"{name}.csv", index=False, encoding="utf-8")
        print(f"{name}.csv: {len(df)} satır")
    s = out["summary"]
    print(f"Birincil metrik gündüz-yalnız RMSE (W); nRMSE paydası = {config.CAPACITY_W:.0f} W")
    for scope in ("mean16", "h4"):
        print(f"\n[gündüz / {scope}]")
        d = s[(s["mask"] == "day") & (s["scope"] == scope)]
        for _, r in d.iterrows():
            print(f"  {r['model']:<22} RMSE_W = {r['RMSE_W_mean']:.1f} ± {r['RMSE_W_std']:.1f}  (n_runs={r['n_runs']})")
    print("METRIK_TAMAM")


if __name__ == "__main__":
    main()
