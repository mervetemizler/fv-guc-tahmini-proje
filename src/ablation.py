# -*- coding: utf-8 -*-
"""EVAL-04: kümülatif öznitelik ablasyonu (yalnız güç -> +zaman -> +ışınım -> +sıcaklıklar).

D_tam grubu yeniden eğitilmez; Faz 3 all_metrics.csv satırları kullanılır.
train.save_run ASLA çağrılmaz (Faz 3 çıktılarının üzerine yazılmasın).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import joblib  # noqa: E402
import torch  # noqa: E402

from src import baselines, config, evaluate, train, windows  # noqa: E402

GROUPS = {
    "A_guc": ["ac_power"],
    "B_zaman": ["ac_power"] + list(config.TIME_FEATURES),
    "C_isinim": ["ac_power"] + list(config.TIME_FEATURES) + ["poa_irradiance"],
    "D_tam": list(config.INPUT_FEATURES),
}
GROUP_ORDER = ["A_guc", "B_zaman", "C_isinim", "D_tam"]
GROUP_LABELS_TR = {
    "A_guc": "Yalnız güç",
    "B_zaman": "+ zaman",
    "C_isinim": "+ ışınım",
    "D_tam": "+ sıcaklıklar (tam)",
}
RETRAIN_GROUPS = GROUP_ORDER[:3]
DL_MODELS = ("lstm", "cnn_lstm")
TAB_MODELS = ("linreg", "xgboost")
ABL_PRED_DIR = config.PREDICTIONS_DIR / "ablation"
ABL_MODEL_DIR = config.MODELS_DIR / "ablation"
COLS = ["grup", "model", "seed", "n_in", "kaynak", "mask", "scope", "n",
        "MAE_W", "RMSE_W", "R2", "nRMSE"]
KEY_COLS = ["grup", "model", "seed", "mask", "scope"]
# evaluate.evaluate bir kosu icin mask (day/all) x scope (mean16/h4) = 2 x 2 satir uretir
MASKS = ("day", "all")
SCOPES = ("mean16", "h4")
ROWS_PER_RUN = len(MASKS) * len(SCOPES)
EXPECTED_ABL_ROWS = len(RETRAIN_GROUPS) * (len(TAB_MODELS) + len(DL_MODELS) * len(config.SEEDS)) * ROWS_PER_RUN
EXPECTED_FAZ3_ROWS = (len(TAB_MODELS) + len(DL_MODELS) * len(config.SEEDS)) * ROWS_PER_RUN
EXPECTED_TOTAL_ROWS = EXPECTED_ABL_ROWS + EXPECTED_FAZ3_ROWS  # 96 + 32 = 128


def feature_idx(grup: str, feature_names) -> list[int]:
    fn = [str(x) for x in feature_names]
    return [fn.index(c) for c in GROUPS[grup]]


def tabular_mask(names, grup: str) -> np.ndarray:
    k = GROUP_ORDER.index(grup)
    out = []
    for n in names:
        n = str(n)
        if n.startswith("ac_power_"):
            ok = True
        elif n.endswith("_t0"):
            ok = k >= 1
        elif n.startswith("poa_irradiance_"):
            ok = k >= 2
        elif n.startswith("ambient_temp_") or n.startswith("module_temp_1_"):
            ok = k >= 3
        else:
            ok = False
        out.append(ok)
    return np.array(out, dtype=bool)


def _tag(rows, grup, n_in, kaynak):
    for r in rows:
        r.update(grup=grup, n_in=n_in, kaynak=kaynak)
    return rows


def run_dl(model, grup, seed, te, y_scaler) -> list[dict]:
    idx = feature_idx(grup, te["feature_names"])
    m, h = train.train_one(model, seed, feature_idx=idx)
    X_te = torch.from_numpy(te["X"][:, :, idx]).float().to(next(m.parameters()).device)
    assert X_te.shape[-1] == len(idx)
    p = train.predict_scaled(m, X_te)
    p_w = y_scaler.inverse_transform(p.reshape(-1, 1)).reshape(p.shape)
    p_w = evaluate.apply_night_rule(p_w, te["y_sun_elev"])
    np.savez_compressed(ABL_PRED_DIR / f"{model}_{grup}_seed{seed}.npz",
                        y_pred_W=p_w.astype(np.float32))
    with open(ABL_MODEL_DIR / f"{model}_{grup}_seed{seed}_history.json", "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)
    print(f"EGITIM_TAMAM {model} {grup} seed{seed} best_epoch={h['best_epoch']} "
          f"sure={h['total_sec']:.0f}s", flush=True)
    rows = evaluate.evaluate(te["y"], p_w, te["y_sun_elev"], te["y_day"], model, seed)
    return _tag(rows, grup, len(idx), "ablasyon")


def run_tabular(grup, tr, va, te, y_scaler) -> list[dict]:
    fn = list(te["feature_names"])
    Ftr, names = baselines.make_tabular_features(tr["X"], fn)
    Fva, _ = baselines.make_tabular_features(va["X"], fn)
    Fte, _ = baselines.make_tabular_features(te["X"], fn)
    msk = tabular_mask(names, grup)
    Ftr, Fva, Fte = Ftr[:, msk], Fva[:, msk], Fte[:, msk]
    rows = []
    for name in TAB_MODELS:
        if name == "linreg":
            m = baselines.fit_linreg(Ftr, tr["y_scaled"])
        else:
            m, _strat = baselines.fit_xgboost(Ftr, tr["y_scaled"], Fva, va["y_scaled"])
        p_w = baselines.to_watts(m.predict(Fte), y_scaler)
        p_w = evaluate.apply_night_rule(p_w, te["y_sun_elev"])
        np.savez_compressed(ABL_PRED_DIR / f"{name}_{grup}.npz", y_pred_W=p_w.astype(np.float32))
        r = evaluate.evaluate(te["y"], p_w, te["y_sun_elev"], te["y_day"], name, None)
        rows += _tag(r, grup, int(msk.sum()), "ablasyon")
        print(f"TABLO_TAMAM {name} {grup} n_in={int(msk.sum())}", flush=True)
    return rows


def faz3_rows() -> pd.DataFrame:
    df = pd.read_csv(config.METRICS_DIR / "all_metrics.csv")
    df = df[df["model"].isin(DL_MODELS + TAB_MODELS)].copy()
    df["grup"] = "D_tam"
    df["n_in"] = np.where(df["model"].isin(DL_MODELS), 9, 57)
    df["kaynak"] = "faz3"
    return df


def _key(df: pd.DataFrame) -> pd.Series:
    """(grup, model, seed, mask, scope) anahtari; seed NaN -> '-' (tablo modelleri)."""
    parts = df[KEY_COLS].copy()
    parts["seed"] = parts["seed"].map(lambda v: "-" if pd.isna(v) else str(int(v)))
    return parts.astype(str).agg("|".join, axis=1)


def merge_rows(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Kismi (--only) kosuyu mevcut CSV ile upsert eder (D-02, CR-02).

    old_df'den yalniz kaynak == 'ablasyon' satirlari tutulur (faz3 main'de ayrica eklenir);
    new_df ile ayni anahtara sahip eski satirlar dusurulur; kalanlar + new_df dondurulur.
    """
    old = old_df[old_df["kaynak"] == "ablasyon"]
    keep = old[~_key(old).isin(set(_key(new_df)))] if len(old) else old
    out = pd.concat([keep, new_df], ignore_index=True)
    return out[COLS]


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["grup", "model", "mask", "scope"], sort=False)
    parts = {"n_runs": g["RMSE_W"].size()}
    for c, short in (("RMSE_W", "RMSE_W"), ("nRMSE", "nRMSE"), ("MAE_W", "MAE_W")):
        parts[f"{short}_mean"] = g[c].mean()
        s = g[c].std(ddof=1)
        parts[f"{short}_std"] = s.fillna(0.0)
    out = pd.DataFrame(parts).reset_index()
    out["grup_etiket"] = out["grup"].map(GROUP_LABELS_TR)
    out["_o"] = out["grup"].map(GROUP_ORDER.index)
    out = out.sort_values(["model", "mask", "scope", "_o"], kind="stable")
    out["katki_W"] = out.groupby(["model", "mask", "scope"], sort=False)["RMSE_W_mean"].diff()
    out = out.drop(columns="_o")
    cols = ["grup", "grup_etiket", "model", "mask", "scope", "n_runs", "RMSE_W_mean",
            "RMSE_W_std", "nRMSE_mean", "nRMSE_std", "MAE_W_mean", "MAE_W_std", "katki_W"]
    return out[cols].reset_index(drop=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--only", choices=["dl", "tab", "all"], default="all")
    a = ap.parse_args(argv)

    te = windows.load_windows("test")
    if a.smoke:
        idx = feature_idx("A_guc", te["feature_names"])
        m, _ = train.train_one("lstm", config.SEED, max_epochs=2, feature_idx=idx)
        X_te = torch.from_numpy(te["X"][:64][:, :, idx]).float().to(next(m.parameters()).device)
        assert X_te.shape[-1] == 1
        p = train.predict_scaled(m, X_te)
        assert p.shape == (64, config.HORIZON), p.shape
        print("SMOKE_TAMAM")
        return

    tr, va = windows.load_windows("train"), windows.load_windows("val")
    y_scaler = joblib.load(config.SCALERS_FILE)["y"]
    ABL_PRED_DIR.mkdir(parents=True, exist_ok=True)
    ABL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if a.only in ("tab", "all"):
        for g in RETRAIN_GROUPS:
            rows += run_tabular(g, tr, va, te, y_scaler)
    if a.only in ("dl", "all"):
        for g in RETRAIN_GROUPS:
            for mdl in DL_MODELS:
                for s in config.SEEDS:
                    rows += run_dl(mdl, g, s, te, y_scaler)
    new = pd.DataFrame(rows)
    out_csv = config.METRICS_DIR / "ablation_metrics.csv"
    if a.only != "all" and out_csv.exists():
        new = merge_rows(pd.read_csv(out_csv), new)
    f3 = faz3_rows()
    n_abl = int((new["kaynak"] == "ablasyon").sum())
    if a.only == "all" or out_csv.exists():
        if n_abl != EXPECTED_ABL_ROWS or len(f3) != EXPECTED_FAZ3_ROWS:
            raise SystemExit(
                f"Ablasyon tamlik hatası: ablasyon {n_abl}/{EXPECTED_ABL_ROWS}, "
                f"faz3 {len(f3)}/{EXPECTED_FAZ3_ROWS}; CSV yazılmadı.")
    df = pd.concat([new, f3], ignore_index=True)
    df["grup"] = pd.Categorical(df["grup"], GROUP_ORDER, ordered=True)
    df = df.sort_values("grup", kind="stable")
    df["grup"] = df["grup"].astype(str)
    df = df[COLS]
    config.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8")
    summ = summarize(df)
    summ.to_csv(config.METRICS_DIR / "ablation_summary.csv", index=False, encoding="utf-8")
    piv = summ[(summ["mask"] == "day") & (summ["scope"] == "mean16")].pivot(
        index="grup", columns="model", values="RMSE_W_mean").reindex(GROUP_ORDER)
    print(piv.round(1).to_string())
    print("ABLASYON_TAMAM")


if __name__ == "__main__":
    main()
