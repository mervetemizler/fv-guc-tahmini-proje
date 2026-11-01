# -*- coding: utf-8 -*-
"""Faz 4 ortak altyapı: yükleyici, model sırası/etiket/renk, sabit figür adları, gün/saat yardımcıları."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import matplotlib

    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from src import config  # noqa: E402
from src import evaluate  # noqa: E402
from src import run_all  # noqa: E402
from src import windows  # noqa: E402

config.apply_plot_style()

MODEL_ORDER = ["persistence", "seasonal_persistence", "linreg", "xgboost", "lstm", "cnn_lstm"]
BASELINES = ("persistence", "seasonal_persistence", "linreg", "xgboost")
DL_MODELS = ("lstm", "cnn_lstm")
MODEL_LABELS_TR = {
    "persistence": "Persistence",
    "seasonal_persistence": "Mevsimsel persistence",
    "linreg": "Doğrusal regresyon",
    "xgboost": "XGBoost",
    "lstm": "LSTM",
    "cnn_lstm": "CNN-LSTM",
}
COLORS = {
    "persistence": "#7f7f7f",
    "seasonal_persistence": "#bcbd22",
    "linreg": "#17becf",
    "xgboost": "#2ca02c",
    "lstm": "#1f77b4",
    "cnn_lstm": "#d62728",
}
# Tek doğruluk kaynağı: Faz 5 deck/rapor bu dosya adlarını kullanır.
FIGURES = {
    "kayip": "sonuc_01_kayip_egrileri.png",
    "tahmin": "sonuc_02_tahmin_vs_gercek.png",
    "saat": "sonuc_03_saate_gore_hata.png",
    "karsilastirma": "sonuc_04_model_karsilastirma.png",
    "ablasyon": "sonuc_05_ablasyon.png",
    "ufuk": "sonuc_06_ufuk_egrisi.png",
    "hava": "sonuc_07_hava_kosulu.png",
}


def require_file(path, hint: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{p} bulunamadı. Önce: {hint}")
    return p


def label(model: str) -> str:
    return MODEL_LABELS_TR.get(model, model)


def load_test() -> dict:
    require_file(config.WINDOWS_NPZ["test"], "python -I src/windows.py")
    return windows.load_windows("test")


def load_pred(model: str, seed, y_sun_elev) -> np.ndarray:
    p = require_file(run_all.pred_path(model, seed), "python -I src/run_all.py (veya src/train.py / src/baselines.py)")
    with np.load(p, allow_pickle=False) as z:
        pred = z["y_pred_W"]
    assert pred.ndim == 2 and pred.shape[1] == config.HORIZON, (p.name, pred.shape)
    return evaluate.apply_night_rule(pred, y_sun_elev)


def load_all_preds(w: dict) -> dict:
    out = {}
    for model, seed in run_all.RUNS:
        pred = load_pred(model, seed, w["y_sun_elev"])
        assert pred.shape == w["y"].shape, (model, seed, pred.shape, w["y"].shape)
        out[(model, seed)] = pred
    return out


def bin_start(y_time) -> np.ndarray:
    """Sağ etiketli bin damgası -> bin başlangıcı."""
    return np.asarray(y_time, dtype="datetime64[ns]") - np.timedelta64(15, "m")


def target_day_hour(y_time):
    start = bin_start(y_time)
    day = start.astype("datetime64[D]")
    hour = ((start - day) // np.timedelta64(1, "h")).astype(int)
    return day, hour


def window_day(t0_time) -> np.ndarray:
    return (np.asarray(t0_time, dtype="datetime64[ns]") - np.timedelta64(15, "m")).astype("datetime64[D]")


def save_fig(fig, name: str) -> Path:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIGURES_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=config.FIG_DPI)
    plt.close(fig)
    return path


def main() -> None:
    w = load_test()
    preds = load_all_preds(w)
    for (m, s), p in preds.items():
        print(f"{m} seed={s} shape={p.shape}")
    print("ANALIZ_TAMAM")


if __name__ == "__main__":
    main()
