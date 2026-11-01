# -*- coding: utf-8 -*-
"""EVAL-06: test günlerini POA tabanlı açıklık indeksine (KT) göre Açık/Parçalı/Kapalı etiketler
ve tüm modellerin sınıf bazında hatasını ölçer.

KT = Σ POA_gün / Σ açık-gök zarfı_gün. Zarf: her gün-içi 15 dk adımı için ±15 günlük kayan MAKSİMUM POA.
Not (sızıntı yok): zarf test dönemini de görür ama yalnızca gün ETİKETLEMEK içindir; model girdisi değildir.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import analysis  # noqa: E402
from src import config  # noqa: E402
from src import data  # noqa: E402
from src import evaluate  # noqa: E402

# Eşikler (A-02): test metriğine bakarak AYARLANMAZ.
KT_CLEAR = 0.75
KT_OVERCAST = 0.40
ENVELOPE_HALF_DAYS = 15
ENVELOPE_MIN_PERIODS = 10
CLASS_NAMES_TR = {0: "Kapalı", 1: "Parçalı", 2: "Açık"}
CLASS_ORDER = [2, 1, 0]


def classify(kt: float) -> int:
    if kt is None or not np.isfinite(kt):
        return -1
    if kt >= KT_CLEAR:
        return 2
    if kt < KT_OVERCAST:
        return 0
    return 1


def _pivot(grid: pd.DataFrame, values: pd.Series) -> pd.DataFrame:
    start = grid.index - pd.Timedelta(config.FREQ)
    day = start.normalize()
    slot = ((start - day) // pd.Timedelta(config.FREQ)).astype(int)
    df = pd.DataFrame({"day": np.asarray(day), "slot": np.asarray(slot), "v": values.to_numpy()})
    pv = df.pivot(index="day", columns="slot", values="v")
    full = pd.date_range(pv.index.min(), pv.index.max(), freq="D")
    return pv.reindex(full)


def daily_clearness(grid: pd.DataFrame) -> pd.DataFrame:
    poa = grid["poa_irradiance"].clip(lower=0)
    pv = _pivot(grid, poa)
    env = pv.rolling(2 * ENVELOPE_HALF_DAYS + 1, center=True, min_periods=ENVELOPE_MIN_PERIODS).max()
    env = env.where(pv.notna())
    poa_wh = pv.sum(axis=1) * 0.25
    env_wh = env.sum(axis=1) * 0.25
    kt = (poa_wh / env_wh.where(env_wh > 0)).astype(float)

    et = 1361.0 * np.clip(np.sin(np.radians(grid["sun_elevation"])), 0, None)
    et_pv = _pivot(grid, et).where(pv.notna())
    et_wh = et_pv.sum(axis=1) * 0.25
    kt_et = (poa_wh / et_wh.where(et_wh > 0)).astype(float)

    sinif = kt.map(lambda v: classify(v))
    out = pd.DataFrame({
        "poa_Wh_m2": poa_wh,
        "zarf_Wh_m2": env_wh,
        "KT": kt,
        "kt_et": kt_et,
        "sinif": sinif.astype(int),
    })
    out["sinif_ad"] = out["sinif"].map(lambda k: CLASS_NAMES_TR.get(k, "Yok"))
    out.index.name = "gun"
    return out


def cell_class(y_time, days_df: pd.DataFrame) -> np.ndarray:
    day, _ = analysis.target_day_hour(y_time)
    s = days_df["sinif"].reindex(pd.DatetimeIndex(day.ravel()))
    arr = s.fillna(-1).to_numpy().astype(np.int8)
    return arr.reshape(day.shape)


def weather_metrics(w: dict, preds: dict, cls: np.ndarray) -> pd.DataFrame:
    h4 = np.zeros(w["y"].shape, dtype=bool)
    h4[:, config.MAIN_HORIZON_STEPS - 1] = True
    scopes = {"mean16": np.ones_like(h4), "h4": h4}
    day, _ = analysis.target_day_hour(w["y_time"])
    rows = []
    for (model, seed), pred in preds.items():
        for k in (0, 1, 2):
            for sc, sm in scopes.items():
                mask = w["y_day"] & (cls == k) & sm
                r = evaluate.metrics(w["y"], pred, mask)
                r.update(model=model, seed=seed, sinif=k, sinif_ad=CLASS_NAMES_TR[k], scope=sc,
                         n_gun=int(len(np.unique(day[mask]))) if mask.any() else 0)
                rows.append(r)
    df = pd.DataFrame(rows)
    base = df[df["model"] == "persistence"].set_index(["sinif", "scope"])["RMSE_W"]
    ref = pd.Series([base[(a, b)] for a, b in zip(df["sinif"], df["scope"])], index=df.index)
    df["skill"] = 1.0 - df["RMSE_W"] / ref
    return df[["model", "seed", "sinif", "sinif_ad", "scope", "n_gun", "n", "MAE_W", "RMSE_W", "R2", "nRMSE", "skill"]]


def main() -> None:
    analysis.require_file(config.GRID_PARQUET, "python -I src/data.py")
    grid = data.load_grid()
    days = daily_clearness(grid)
    w = analysis.load_test()
    cls = cell_class(w["y_time"], days)
    assert int(((cls == -1) & w["y_day"]).sum()) == 0, "sınıfsız gündüz hücresi var"

    tday, _ = analysis.target_day_hour(w["y_time"])
    test_days = pd.DatetimeIndex(np.unique(tday[w["y_day"]]))
    days["test_gunu"] = days.index.isin(test_days)
    config.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    days.to_csv(config.METRICS_DIR / "weather_days.csv", index_label="gun", encoding="utf-8")

    preds = analysis.load_all_preds(w)
    wm = weather_metrics(w, preds, cls)
    wm.to_csv(config.METRICS_DIR / "weather_metrics.csv", index=False, encoding="utf-8")

    td = days[days["test_gunu"]]
    print(f"Test günü sayısı: {len(td)}")
    for k in CLASS_ORDER:
        sub = td[td["sinif"] == k]
        med = sub["KT"].median() if len(sub) else float("nan")
        print(f"  {CLASS_NAMES_TR[k]}: n_gun={len(sub)} KT_medyan={med:.3f}")
        if k == 0 and len(sub) < 15:
            print(f"UYARI: Kapalı sınıf az günlü (n_gun={len(sub)})")
    print("KT - kt_et Spearman (tüm günler):")
    print(days[["KT", "kt_et"]].corr(method="spearman").round(3))
    print("Gündüz mean16 nRMSE (sınıf x model, seed ortalaması):")
    sub = wm[wm["scope"] == "mean16"]
    pv = sub.groupby(["sinif_ad", "model"])["nRMSE"].mean().unstack("model")
    print(pv[[m for m in analysis.MODEL_ORDER if m in pv.columns]].round(4))
    print("HAVA_TAMAM")


if __name__ == "__main__":
    main()
