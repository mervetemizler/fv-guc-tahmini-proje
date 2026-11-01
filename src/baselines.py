# -*- coding: utf-8 -*-
"""Baseline modeller: persistence, mevsimsel persistence, Lineer Regresyon, XGBoost.

Güvenlik notu: joblib yalnızca proje içi, Faz 2'nin ürettiği SCALERS_FILE için yüklenir.
Kanal indeksleri her zaman öznitelik adından bulunur (sabit indeks yok).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402
from src import evaluate  # noqa: E402
from src import windows  # noqa: E402


def _idx(feature_names, name) -> int:
    return list(feature_names).index(name)


def persistence(X, feature_names) -> np.ndarray:
    """Son gözlenen AC güç değerini 16 adım boyunca tekrarla (ölçekli)."""
    ac_i = _idx(feature_names, config.TARGET)
    return np.repeat(X[:, -1, ac_i][:, None], config.HORIZON, axis=1)


def seasonal_persistence(X, feature_names) -> np.ndarray:
    """Dünün aynı saatleri: t0+h-96 = pencere indeksi h-1 (ölçekli)."""
    ac_i = _idx(feature_names, config.TARGET)
    return X[:, 0:config.HORIZON, ac_i]


def to_watts(v_scaled_2d, y_scaler) -> np.ndarray:
    v = np.asarray(v_scaled_2d)
    return y_scaler.inverse_transform(v.reshape(-1, 1)).reshape(v.shape)


def make_tabular_features(X, feature_names):
    """57 tablo özniteliği. Hedef zamanın y_sun_elev değeri öznitelik DEĞİLDİR (Faz 2 D-08)."""
    cols, names = [], []
    chans = (config.TARGET, "poa_irradiance")
    for ch in chans:  # (a) son 8 adım
        i = _idx(feature_names, ch)
        for k in range(8):
            cols.append(X[:, X.shape[1] - 1 - k, i])
            names.append(f"{ch}_lag{k}")
    for ch in chans:  # (b) dün aynı ufuk
        i = _idx(feature_names, ch)
        for h in range(1, config.HORIZON + 1):
            cols.append(X[:, h - 1, i])
            names.append(f"{ch}_dun_h{h}")
    for ch in ("ambient_temp", "module_temp_1"):  # (c)
        i = _idx(feature_names, ch)
        cols.append(X[:, -1, i])
        names.append(f"{ch}_son")
        cols.append(X[:, -4:, i].mean(axis=1))
        names.append(f"{ch}_ort4")
    for ch in ("hour_sin", "hour_cos", "doy_sin", "doy_cos", "sun_elevation"):  # (d)
        cols.append(X[:, -1, _idx(feature_names, ch)])
        names.append(f"{ch}_t0")
    F = np.stack(cols, axis=1).astype(np.float32)
    return F, names


def fit_linreg(Ftr, ytr_scaled):
    from sklearn.linear_model import LinearRegression
    return LinearRegression().fit(Ftr, ytr_scaled)


def fit_xgboost(Ftr, ytr_scaled, Fva, yva_scaled):
    """Döndürür (model, strateji_adı)."""
    import xgboost as xgb
    try:
        m = xgb.XGBRegressor(
            tree_method="hist", multi_strategy="multi_output_tree", n_estimators=500,
            max_depth=6, learning_rate=0.05, subsample=1.0, colsample_bytree=0.8,
            early_stopping_rounds=20, random_state=config.SEED, n_jobs=-1)
        m.fit(Ftr, ytr_scaled, eval_set=[(Fva, yva_scaled)], verbose=False)
        return m, "multi_output_tree"
    except (xgb.core.XGBoostError, TypeError, ValueError) as e:  # yedek: yalnızca multi_output_tree yetenek hatası
        print(f"UYARI: multi_output_tree başarısız ({e}); MultiOutputRegressor yedeği")
        from sklearn.multioutput import MultiOutputRegressor
        m = MultiOutputRegressor(xgb.XGBRegressor(
            tree_method="hist", n_estimators=300, max_depth=6, learning_rate=0.05,
            random_state=config.SEED))
        m.fit(Ftr, ytr_scaled)
        return m, "MultiOutputRegressor"


def save_predictions(name, y_pred_W, y_sun_elev) -> Path:
    config.PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PREDICTIONS_DIR / f"{name}.npz"
    np.savez_compressed(
        path, y_pred_W=evaluate.apply_night_rule(y_pred_W, y_sun_elev).astype(np.float32))
    return path


def main() -> None:
    tr, va, te = (windows.load_windows(s) for s in ("train", "val", "test"))
    sc = joblib.load(config.SCALERS_FILE)
    ys = sc["y"]
    fn = list(te["feature_names"])
    ac_i = _idx(fn, config.TARGET)
    assert np.allclose(sc["x"].mean_[ac_i], ys.mean_[0]) and np.allclose(sc["x"].scale_[ac_i], ys.scale_[0])

    Ftr, names = make_tabular_features(tr["X"], fn)
    Fva, _ = make_tabular_features(va["X"], fn)
    Fte, _ = make_tabular_features(te["X"], fn)
    info = {"tabular_feature_names": names, "n_features": len(names)}

    preds = {
        "persistence": to_watts(persistence(te["X"], fn), ys),
        "seasonal_persistence": to_watts(seasonal_persistence(te["X"], fn), ys),
    }
    t0 = time.time()
    lr = fit_linreg(Ftr, tr["y_scaled"])
    info["linreg"] = {"fit_sec": round(time.time() - t0, 2)}
    preds["linreg"] = to_watts(lr.predict(Fte), ys)

    t0 = time.time()
    xm, strat = fit_xgboost(Ftr, tr["y_scaled"], Fva, va["y_scaled"])
    info["xgboost"] = {
        "strategy": strat,
        "best_iteration": int(getattr(xm, "best_iteration", -1)) if strat == "multi_output_tree" else None,
        "n_estimators": 500 if strat == "multi_output_tree" else 300,
        "max_depth": 6, "learning_rate": 0.05, "fit_sec": round(time.time() - t0, 2)}
    preds["xgboost"] = to_watts(xm.predict(Fte), ys)

    print(f"{'Model':<22}{'RMSE_W gündüz/16-ort':>22}{'RMSE_W gündüz/+1sa':>22}")
    for name, p in preds.items():
        save_predictions(name, p, te["y_sun_elev"])
        rows = evaluate.evaluate(te["y"], p, te["y_sun_elev"], te["y_day"], name)
        g = {(r["mask"], r["scope"]): r["RMSE_W"] for r in rows}
        print(f"{name:<22}{g[('day', 'mean16')]:>22.2f}{g[('day', 'h4')]:>22.2f}")

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.MODELS_DIR / "baselines_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print("BASELINE_TAMAM")


if __name__ == "__main__":
    main()
