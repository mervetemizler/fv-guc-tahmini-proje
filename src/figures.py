# -*- coding: utf-8 -*-
"""Faz 4 sonuç figürleri (sonuc_01..07). Yeniden eğitim yok; kayıtlı CSV/JSON/npz okunur."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import matplotlib

    matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from src import analysis  # noqa: E402
from src import ablation  # noqa: E402
from src import config  # noqa: E402
from src import evaluate  # noqa: E402
from src import weather  # noqa: E402

config.apply_plot_style()

MO = analysis.MODEL_ORDER
SEED_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c"]


def _read(name: str, hint: str) -> pd.DataFrame:
    return pd.read_csv(analysis.require_file(config.METRICS_DIR / name, hint))


def _fig(key: str, fig) -> Path:
    return analysis.save_fig(fig, analysis.FIGURES[key])


# ---------------------------------------------------------------- sonuc_01
def plot_loss() -> Path:
    files = sorted(config.MODELS_DIR.glob("*_seed*_history.json"))
    if not files:
        raise FileNotFoundError("Geçmiş JSON yok. Önce: python -I src/run_all.py")
    hist = {}
    for f in files:
        h = json.loads(f.read_text(encoding="utf-8"))
        hist.setdefault(h["model"], []).append(h)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, model in zip(axes, analysis.DL_MODELS):
        for i, h in enumerate(sorted(hist.get(model, []), key=lambda d: d["seed"])):
            c = SEED_COLORS[i % len(SEED_COLORS)]
            ep = [e["epoch"] for e in h["epochs"]]
            tr = [e["train_loss"] for e in h["epochs"]]
            va = [e["val_loss"] for e in h["epochs"]]
            ax.plot(ep, va, color=c, label=f"seed {h['seed']} doğrulama")
            ax.plot(ep, tr, color=c, ls="--", alpha=0.7, label=f"seed {h['seed']} eğitim")
            if h["best_epoch"] in ep:
                ax.plot(h["best_epoch"], va[ep.index(h["best_epoch"])], "o", color=c, ms=7,
                        mec="black")
        ax.set_title(analysis.label(model))
        ax.set_xlabel("Epoch")
    axes[0].set_ylabel("MSE (ölçekli)")
    axes[1].legend(fontsize=7, ncol=2)
    fig.suptitle("Eğitim ve doğrulama kaybı (3 seed)")
    return _fig("kayip", fig)


# ---------------------------------------------------------------- sonuc_04
def plot_comparison() -> Path:
    s = _read("summary.csv", "python -I src/run_all.py")
    s = s[s["mask"] == "day"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, scope, title in zip(axes, ("mean16", "h4"), ("Ortalama (16 ufuk)", "+1 saat")):
        d = s[s["scope"] == scope].set_index("model").reindex(MO)
        x = np.arange(len(MO))
        multi = (d["n_runs"] > 1).to_numpy()
        for i, m in enumerate(MO):
            ax.bar(i, d.loc[m, "RMSE_W_mean"], color=analysis.COLORS[m],
                   yerr=d.loc[m, "RMSE_W_std"] if multi[i] else None, capsize=4)
            ax.text(i, d.loc[m, "RMSE_W_mean"] * 1.01 + (d.loc[m, "RMSE_W_std"] if multi[i] else 0),
                    f"{d.loc[m, 'RMSE_W_mean']:.1f} W\n%{d.loc[m, 'nRMSE_mean'] * 100:.1f}",
                    ha="center", va="bottom", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels([analysis.label(m).replace(" ", "\n") for m in MO], fontsize=8)
        ax.set_title(title)
        ax.set_ylim(0, float(d["RMSE_W_mean"].max()) * 1.35)
    axes[0].set_ylabel("RMSE (W, gündüz)")
    fig.suptitle("Model karşılaştırması (test, gündüz)")
    fig.text(0.5, 0.0, "Baseline'lar tek koşu; DL 3 seed ortalaması ± std", ha="center", fontsize=8)
    return _fig("karsilastirma", fig)


# ---------------------------------------------------------------- sonuc_05
def plot_ablation() -> Path:
    a = _read("ablation_summary.csv", "python -I src/ablation.py")
    a = a[(a["mask"] == "day") & (a["scope"] == "mean16")]
    s = _read("summary.csv", "python -I src/run_all.py")
    pers = s[(s["model"] == "persistence") & (s["mask"] == "day") & (s["scope"] == "mean16")]["RMSE_W_mean"].iloc[0]
    models = ["lstm", "cnn_lstm", "linreg", "xgboost"]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    wd = 0.2
    x = np.arange(len(ablation.GROUP_ORDER))
    for j, m in enumerate(models):
        d = a[a["model"] == m].set_index("grup").reindex(ablation.GROUP_ORDER)
        multi = (d["n_runs"] > 1).all()
        ax.bar(x + (j - 1.5) * wd, d["RMSE_W_mean"], wd, color=analysis.COLORS[m],
               label=analysis.label(m), yerr=d["RMSE_W_std"] if multi else None, capsize=3)
    ax.axhline(pers, color="gray", ls="--", label="Persistence")
    ax.set_xticks(x)
    ax.set_xticklabels([ablation.GROUP_LABELS_TR[g] for g in ablation.GROUP_ORDER])
    ax.set_ylabel("RMSE (W, gündüz)")
    ax.set_ylim(100, pers * 1.05)
    ax.set_title("Öznitelik ablasyonu: gündüz RMSE (16 ufuk ort.)")
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 0.85))
    ax.set_xlabel("Y ekseni 100 W'tan başlar. DL: 3 seed ± std; LinReg/XGBoost tek koşu.", fontsize=8)
    return _fig("ablasyon", fig)


# ---------------------------------------------------------------- sonuc_06
def plot_horizon() -> Path:
    h = _read("horizon_metrics.csv", "python -I src/run_all.py")
    h = h[h["mask"] == "day"]
    g = h.groupby(["model", "horizon_min"]).agg(
        RMSE_W=("RMSE_W", "mean"), RMSE_W_std=("RMSE_W", "std"),
        nRMSE=("nRMSE", "mean"), nRMSE_std=("nRMSE", "std")).reset_index()
    tab = None
    for m in MO:
        d = g[g["model"] == m].sort_values("horizon_min").set_index("horizon_min")
        t = d[["RMSE_W", "nRMSE"]].rename(columns=lambda c: f"{m}_{c}")
        tab = t if tab is None else tab.join(t)
    tab.reset_index().to_csv(config.METRICS_DIR / "ufuk_tablosu.csv", index=False, encoding="utf-8")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for m in MO:
        d = g[g["model"] == m].sort_values("horizon_min")
        for ax, col, k in ((axes[0], "RMSE_W", 1), (axes[1], "nRMSE", 100)):
            y = d[col].to_numpy() * k
            ax.plot(d["horizon_min"], y, marker="o", ms=3, color=analysis.COLORS[m], label=analysis.label(m))
            if m in analysis.DL_MODELS:
                sd = d[col + "_std"].to_numpy() * k
                ax.fill_between(d["horizon_min"], y - sd, y + sd, color=analysis.COLORS[m], alpha=0.2)
    for ax, yl in zip(axes, ("RMSE (W)", "nRMSE (%)")):
        ax.set_xticks([15, 60, 120, 180, 240])
        ax.set_xlabel("Ufuk (dk)")
        ax.set_ylabel(yl)
    axes[0].legend(fontsize=8)
    fig.suptitle("Ufka göre hata (gündüz)")
    return _fig("ufuk", fig)


# ---------------------------------------------------------------- sonuc_03
def plot_hourly(w, preds) -> Path:
    _, hour = analysis.target_day_hour(w["y_time"])
    h = config.MAIN_HORIZON_STEPS - 1
    rows = []
    for (m, seed), p in preds.items():
        for s in np.unique(hour[:, h]):
            mask = np.zeros(w["y"].shape, dtype=bool)
            mask[:, h] = w["y_day"][:, h] & (hour[:, h] == s)
            r = evaluate.metrics(w["y"], p, mask)
            rows.append(dict(model=m, seed=seed, saat=int(s), n=r["n"], MAE_W=r["MAE_W"],
                             RMSE_W=r["RMSE_W"], nRMSE=r["nRMSE"]))
    df = pd.DataFrame(rows)
    df.to_csv(config.METRICS_DIR / "hour_metrics.csv", index=False, encoding="utf-8")
    df = df[df["n"] >= 30]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for m in MO:
        d = df[df["model"] == m].groupby("saat")["RMSE_W"].agg(["mean", "std"]).fillna(0)
        ax.plot(d.index, d["mean"], marker="o", ms=3, color=analysis.COLORS[m], label=analysis.label(m))
        if m in analysis.DL_MODELS:
            ax.fill_between(d.index, d["mean"] - d["std"], d["mean"] + d["std"],
                            color=analysis.COLORS[m], alpha=0.2)
    ax.set_xlabel("Saat")
    ax.set_ylabel("RMSE (W)")
    ax.set_title("+1 saat tahmininde hedef saatine göre hata (gündüz)")
    ax.legend(fontsize=8)
    return _fig("saat", fig)


# ---------------------------------------------------------------- sonuc_02
def pick_example_days(days: pd.DataFrame) -> dict:
    """Her sınıfta KT'si sınıf medyanına en yakın test günü (model hatasına bakılmaz)."""
    t = days[days["test_gunu"].astype(bool)]
    out = {}
    for k in weather.CLASS_ORDER:
        d = t[t["sinif"] == k].sort_values("gun")
        med = d["KT"].median()
        i = (d["KT"] - med).abs().to_numpy().argmin()  # eşitlikte en erken
        out[k] = d.iloc[i]
    return out


def plot_examples(w, preds) -> Path:
    days = _read("weather_days.csv", "python -I src/weather.py")
    days["gun"] = pd.to_datetime(days["gun"])
    sel = pick_example_days(days)
    h = config.MAIN_HORIZON_STEPS - 1
    tday, _ = analysis.target_day_hour(w["y_time"])
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharey=True)
    series = [("Gerçek", None, "black", 2.4), ("persistence", None, None, 1.2),
              ("xgboost", None, None, 1.2), ("lstm", config.SEED, None, 1.4),
              ("cnn_lstm", config.SEED, None, 1.4)]
    for ax, k in zip(axes, weather.CLASS_ORDER):
        r = sel[k]
        sel_w = np.where(tday[:, h] == np.datetime64(r["gun"].date()))[0]
        t = pd.to_datetime(w["y_time"][sel_w, h])
        for name, seed, col, lw in series:
            if name == "Gerçek":
                ax.plot(t, w["y"][sel_w, h], color=col, lw=lw, label=name)
            else:
                ax.plot(t, preds[(name, seed)][sel_w, h], color=analysis.COLORS[name], lw=lw,
                        label=analysis.label(name))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.set_xlim(t[0].normalize() + pd.Timedelta(hours=4), t[0].normalize() + pd.Timedelta(hours=21))
        ax.tick_params(axis="x", labelsize=8)
        ax.set_title(f"{weather.CLASS_NAMES_TR[k]} gün — {r['gun']:%d.%m.%Y} (KT={r['KT']:.2f})", fontsize=10)
        ax.set_xlabel("Saat")
    axes[0].set_ylabel("Güç (W)")
    fig.suptitle("+1 saat tahmin ve gerçek değer (örnek test günleri)")
    axes[2].legend(fontsize=8, loc="upper right")
    return _fig("tahmin", fig)


# ---------------------------------------------------------------- sonuc_07
def plot_weather() -> Path:
    wm = _read("weather_metrics.csv", "python -I src/weather.py")
    wm = wm[wm["scope"] == "mean16"]
    ng = wm.groupby("sinif")["n_gun"].first()
    labels = []
    for k in weather.CLASS_ORDER:
        t = f"{weather.CLASS_NAMES_TR[k]}\n({int(ng[k])} gün)"
        if k == 0 and ng[k] < 25:
            t += "\n(az örnek)"
        labels.append(t)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    x = np.arange(len(weather.CLASS_ORDER))
    for ax, col, k, yl in ((axes[0], "nRMSE", 100, "nRMSE (%)"), (axes[1], "skill", 1, "Skill (persistence'a göre)")):
        models = [m for m in MO if not (col == "skill" and m == "persistence")]
        wd = 0.8 / len(models)
        for j, m in enumerate(models):
            means, sds, multi = [], [], False
            for c in weather.CLASS_ORDER:
                v = wm[(wm["model"] == m) & (wm["sinif"] == c)][col].to_numpy() * k
                means.append(v.mean())
                sds.append(v.std(ddof=1) if len(v) > 1 else 0)
                multi = len(v) > 1
            ax.bar(x + (j - (len(models) - 1) / 2) * wd, means, wd, color=analysis.COLORS[m],
                   label=analysis.label(m), yerr=sds if multi else None, capsize=2)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel(yl)
    axes[1].axhline(0, color="black", lw=0.8)
    axes[0].legend(fontsize=7, ncol=3, loc="upper center")
    axes[0].set_ylim(0, axes[0].get_ylim()[1] * 1.25)
    fig.suptitle("Hava koşuluna göre hata (gündüz, 16 ufuk)")
    return _fig("hava", fig)


def main() -> None:
    w = analysis.load_test()
    preds = analysis.load_all_preds(w)
    paths = [plot_loss(), plot_comparison(), plot_ablation(), plot_horizon(),
             plot_hourly(w, preds), plot_examples(w, preds), plot_weather()]
    for p in paths:
        print(p)
    for f in analysis.FIGURES.values():
        assert (config.FIGURES_DIR / f).exists(), f
    print("FIGURLER_TAMAM")


if __name__ == "__main__":
    main()
