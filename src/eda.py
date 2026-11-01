# -*- coding: utf-8 -*-
"""EDA grafikleri (Türkçe, 200 dpi). Her fonksiyon PNG kaydeder ve yolunu döndürür."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import matplotlib

    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from src import config  # noqa: E402
from src import data  # noqa: E402
from src import features  # noqa: E402

config.apply_plot_style()

SEASON_COLORS = ["#1f77b4", "#2ca02c", "#d62728", "#ff7f0e"]


def _save(fig, name: str) -> Path:
    """Tek yerde kaydetme kalıbı: tight_layout, 200 dpi PNG, figürü kapat."""
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIGURES_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=config.FIG_DPI)
    plt.close(fig)
    return path


def bin_day(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Right-label ızgarada her damgayı ait olduğu TAKVİM gününe eşler.

    Damga t, (t-15dk, t] aralığını temsil eder; bu yüzden D 00:00 damgası D-1 gününe aittir.
    Gün bazlı gruplamaların hepsi bu yardımcıyla yapılmalıdır (etiket günü kullanılmaz).
    """
    return (index - pd.Timedelta(config.FREQ)).normalize()


def _noon_hour(day: pd.Timestamp) -> float:
    """Verilen gün için hesaplanan güneş öğlesi (yerel saat, ondalık saat)."""
    idx = pd.date_range(day.normalize(), periods=1440, freq="1min")
    el = features.solar_elevation_deg(idx, config.LATITUDE, config.LONGITUDE, config.UTC_OFFSET_H)
    return float(np.argmax(el) / 60.0)


def plot_time_series(grid: pd.DataFrame) -> Path:
    daily = grid[["ac_power", "poa_irradiance"]].groupby(bin_day(grid.index)).mean()
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(daily.index, daily["ac_power"], color="#1f77b4", lw=1)
    axes[0].set_ylabel("Günlük ort. AC güç [W]")
    axes[0].set_title("Günlük ortalama AC güç ve eğik düzlem ışınımı (2015–2016)")
    axes[1].plot(daily.index, daily["poa_irradiance"], color="#ff7f0e", lw=1)
    axes[1].set_ylabel("Günlük ort. POA [W/m²]")
    axes[1].set_xlabel("Tarih")
    for a in axes:
        a.grid(alpha=0.3)
    return _save(fig, "eda_01_zaman_serisi.png")


def pick_peak_week(grid: pd.DataFrame, month: int = 6, year: int | None = None) -> pd.DatetimeIndex:
    """Verilen ayda günlük POA integrali en yüksek ardışık 7 günü seçer."""
    year = config.Y1 if year is None else year
    bd = bin_day(grid.index)
    sel = (bd.year == year) & (bd.month == month)
    m = grid.loc[sel, "poa_irradiance"]
    daily = (m * 0.25).groupby(bd[sel]).sum()
    roll = daily.rolling(7).sum()
    end = roll.idxmax()
    return pd.date_range(end - pd.Timedelta(days=6), end, freq="1D")


def plot_week_zoom(grid: pd.DataFrame) -> Path:
    days = pick_peak_week(grid)
    sub = grid.loc[days[0] : days[-1] + pd.Timedelta(hours=24)]
    sub = sub.loc[sub.index > days[0]]
    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax2 = ax.twinx()
    ax.plot(sub.index, sub["ac_power"], color="#1f77b4", lw=1.4, label="AC güç [W]")
    ax2.plot(sub.index, sub["poa_irradiance"], color="#ff7f0e", lw=1.2, label="POA [W/m²]")
    for i, d in enumerate(days):
        t = d + pd.Timedelta(hours=_noon_hour(d))
        ax.axvline(t, color="k", ls="--", lw=0.9, label="Hesaplanan güneş öğlesi" if i == 0 else None)
    ax.set_ylabel("AC güç [W]")
    ax2.set_ylabel("POA [W/m²]")
    ax.set_xlabel("Zaman (yerel standart saat, UTC-7 varsayımı)")
    ax.set_title(f"Bir haftalık yakınlaştırma ({days[0].date()} – {days[-1].date()})")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=11)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    return _save(fig, "eda_02_hafta_yakinlastirma.png")


def plot_daily_profile(grid: pd.DataFrame) -> Path:
    g = grid.assign(
        hour=grid.index.hour + grid.index.minute / 60,
        season=bin_day(grid.index).month.map(config.SEASON_BY_MONTH),
    )
    fig, ax = plt.subplots(figsize=(11, 6))
    for s, name in enumerate(config.SEASON_NAMES):
        prof = g.loc[g["season"] == s].groupby("hour")["ac_power"].mean()
        ax.plot(prof.index, prof.values, color=SEASON_COLORS[s], lw=2.2, label=name)
    ax.set_xlabel("Günün saati (yerel standart saat)")
    ax.set_ylabel("Ortalama AC güç [W]")
    ax.set_title("Günlük üretim profili (mevsime göre)")
    ax.set_xticks(range(0, 25, 3))
    ax.legend()
    ax.grid(alpha=0.3)
    return _save(fig, "eda_03_gunluk_profil.png")


def plot_monthly_profile(grid: pd.DataFrame) -> Path:
    bd = bin_day(grid.index)
    daily_wh = (grid["ac_power"] * 0.25).groupby(bd).sum()  # gün başına enerji [Wh]
    wh = daily_wh.groupby([daily_wh.index.year, daily_wh.index.month]).mean()
    tab = wh.unstack(0)
    fig, ax = plt.subplots(figsize=(12, 6))
    tab.plot.bar(ax=ax, color=["#1f77b4", "#ff7f0e"], width=0.8)
    ax.set_xlabel("Ay")
    ax.set_ylabel("Günlük ort. üretim enerjisi [Wh/gün]")
    ax.set_title("Aylık ortalama günlük üretim")
    ax.set_xticklabels(["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"], rotation=0)
    ax.legend(title="Yıl", loc="upper left", ncol=2)
    ax.grid(alpha=0.3, axis="y")
    return _save(fig, "eda_04_aylik_profil.png")


def plot_correlation(grid: pd.DataFrame) -> Path:
    corr = grid[config.INPUT_FEATURES].corr()
    fig, ax = plt.subplots(figsize=(10, 8.5))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    n = len(corr)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=12)
    ax.set_yticklabels(corr.columns, fontsize=12)
    for i in range(n):
        for j in range(n):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=10,
                    color="white" if abs(v) > 0.6 else "black")
    fig.colorbar(im, ax=ax, label="Pearson korelasyonu")
    ax.set_title("Girdi kanalları korelasyon matrisi")
    return _save(fig, "eda_05_korelasyon.png")


def plot_power_vs_irradiance(grid: pd.DataFrame) -> Path:
    d = grid.loc[grid["is_day"]]
    fig, ax = plt.subplots(figsize=(10, 7))
    sc = ax.scatter(d["poa_irradiance"], d["ac_power"], c=d["module_temp_1"], s=4,
                    cmap="coolwarm", alpha=0.6, rasterized=True)
    fig.colorbar(sc, ax=ax, label="Modül sıcaklığı [°C]")
    if config.CAPACITY_W is not None:
        ax.axhline(config.CAPACITY_W, color="k", ls="--", lw=1, label=f"Kapasite {config.CAPACITY_W:.0f} W")
        ax.legend(loc="lower right")
    ax.set_xlabel("Eğik düzlem ışınımı POA [W/m²]")
    ax.set_ylabel("AC güç [W]")
    ax.set_title("AC güç – ışınım saçılımı (gündüz, 15 dk)")
    ax.grid(alpha=0.3)
    return _save(fig, "eda_06_guc_isinim_sacilim.png")


def plot_missing(raw_clean: pd.DataFrame, grid: pd.DataFrame | None = None) -> Path:
    """Sol: kolon başına NaN oranı; sağ: kolon x ay NaN oranı (1 dk, temizlik sonrası, kesmeden önce)."""
    cols = config.MEASURED_CHANNELS
    isn = raw_clean[cols].isna()
    ratio = isn.mean() * 100
    monthly = isn.groupby([isn.index.year, isn.index.month]).mean().T * 100
    labels = [f"{y}-{m:02d}" for y, m in monthly.columns]
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1, 2.2]})
    axes[0].barh(cols, ratio.values, color="#d62728")
    axes[0].set_xlabel("Eksik oran [%]")
    axes[0].set_title("Kolon başına eksik veri")
    for i, v in enumerate(ratio.values):
        axes[0].text(v, i, f" {v:.2f}", va="center", fontsize=12)
    im = axes[1].imshow(monthly.values, aspect="auto", cmap="Reds", vmin=0, vmax=100)
    axes[1].set_yticks(range(len(cols)))
    axes[1].set_yticklabels(cols)
    axes[1].set_xticks(range(0, len(labels), 2))
    axes[1].set_xticklabels(labels[::2], rotation=60, ha="right", fontsize=11)
    axes[1].set_title("Ay bazında eksik oran [%]")
    fig.colorbar(im, ax=axes[1], label="Eksik oran [%]")
    return _save(fig, "eda_07_eksik_veri.png")


def plot_cleaning_before_after(raw: pd.DataFrame, clean: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(19, 6))
    # Gece = temizlik sonrası is_day == 0 VE POA geçerli (NaN/sentinel değil). Sentinel (-7999) ve
    # uç negatifler (< POA_MIN_VALID) histogramdan dışlanır (sağ panelde ayrıca raporlanır);
    # clip() kullanılmaz, kutu aralığı range ile sabitlenir -> ilk kutuya yığılma olmaz.
    poa_raw = raw["poa_irradiance"].where(raw["poa_irradiance"] != config.MISSING_SENTINEL)
    night = (clean["is_day"] == 0) & poa_raw.notna()
    before = poa_raw[night & (poa_raw >= config.POA_MIN_VALID)]
    after = clean.loc[night, "poa_irradiance"].dropna()
    bins = np.linspace(-20, 10, 61)
    axes[0].hist(before, bins=bins, alpha=0.6, label="Öncesi (ham)", color="#d62728")
    axes[0].hist(after, bins=bins, alpha=0.6, label="Sonrası", color="#2ca02c")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Gece POA [W/m²]")
    axes[0].set_ylabel("Dakika sayısı")
    axes[0].set_title("Gece negatif POA")
    axes[0].legend(fontsize=11)
    cnt = {c: int((raw[c] == config.MISSING_SENTINEL).sum()) for c in raw.columns}
    axes[1].bar(range(len(cnt)), list(cnt.values()), color="#1f77b4")
    axes[1].set_xticks(range(len(cnt)))
    axes[1].set_xticklabels(list(cnt.keys()), rotation=30, ha="right", fontsize=11)
    axes[1].set_ylabel("-7999 sayısı")
    axes[1].set_title("Eksik değer işareti (-7999)")
    for i, v in enumerate(cnt.values()):
        axes[1].text(i, v, str(v), ha="center", va="bottom", fontsize=11)
    ext = raw["poa_irradiance"][(raw["poa_irradiance"] < config.POA_MIN_VALID) & (raw["poa_irradiance"] != config.MISSING_SENTINEL)]
    amb = raw["ambient_temp"][(raw["ambient_temp"] > config.AMBIENT_VALID_RANGE[1])]
    txt = (f"Uç negatif POA (< {config.POA_MIN_VALID:.0f}): {len(ext)} değer\n"
           f"  en düşük {ext.min():.1f} W/m²\n\n"
           f"Ortam sıcaklığı > {config.AMBIENT_VALID_RANGE[1]:.0f} °C: {len(amb)} değer\n"
           f"  en yüksek {amb.max() if len(amb) else float('nan'):.2f} °C\n\n"
           "Bu değerler NaN yapıldı;\nkısa boşluklar (≤ 2 adım)\ngeçmiş değerle (ffill) doldurulur.")
    axes[2].axis("off")
    axes[2].text(0.02, 0.5, txt, va="center", fontsize=14,
                 bbox=dict(boxstyle="round", fc="#f7f7f7", ec="#999"))
    axes[2].set_title("Uç değerler")
    return _save(fig, "eda_08_temizlik_oncesi_sonrasi.png")


def pick_cloudy_clear_days(grid: pd.DataFrame) -> dict:
    """Haziran 2016'da (yeterli veri) günlük POA integrali en yüksek (açık) ve en düşük
    (maks POA > 200, arıza değil) gün seçilir."""
    bd = bin_day(grid.index)
    sel = (bd.year == config.Y2) & (bd.month == 6)
    m = grid.loc[sel]
    daily = (m["poa_irradiance"] * 0.25).groupby(bd[sel]).sum()
    mx = m["poa_irradiance"].groupby(bd[sel]).max()
    ok = daily[mx > 200]
    return {"clear": ok.idxmax(), "cloudy": ok.idxmin()}


def plot_cloudy_vs_clear(grid: pd.DataFrame) -> Path:
    days = pick_cloudy_clear_days(grid)
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5), sharey=False)
    for ax, (key, title) in zip(axes, [("clear", "Açık gün"), ("cloudy", "Bulutlu gün")]):
        d = days[key]
        s = grid.loc[(grid.index > d) & (grid.index <= d + pd.Timedelta(days=1))]
        ax2 = ax.twinx()
        ax.plot(s.index, s["ac_power"], color="#1f77b4", lw=1.6)
        ax2.plot(s.index, s["poa_irradiance"], color="#ff7f0e", lw=1.4)
        ax.set_ylabel("AC güç [W]", color="#1f77b4")
        ax2.set_ylabel("POA [W/m²]", color="#ff7f0e")
        ax.set_title(f"{title} ({d.date()})")
        ax.set_xlabel("Saat")
        ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%H:%M"))
        ax.grid(alpha=0.3)
    return _save(fig, "eda_09_bulutlu_acik_gun.png")


def plot_december_fault(raw: pd.DataFrame) -> Path:
    d = raw.loc["2016-12-01":"2016-12-31 23:59"]
    cut = pd.Timestamp(config.DATA_END)
    poa = d["poa_irradiance"].where(d["poa_irradiance"] != config.MISSING_SENTINEL)
    ac = d["ac_power"].where(d["ac_power"] != config.MISSING_SENTINEL)
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(ac.index, ac, color="#1f77b4", lw=0.7)
    axes[0].set_ylabel("AC güç [W]")
    axes[0].set_title("Aralık 2016 ham veri (kesilmemiş)")
    axes[1].plot(poa.index, poa, color="#ff7f0e", lw=0.7)
    axes[1].set_ylabel("POA [W/m²]")
    axes[1].set_xlabel("Tarih")
    for a in axes:
        a.axvline(cut, color="k", ls="--", lw=1.5)
        a.grid(alpha=0.3)
    axes[0].text(cut, axes[0].get_ylim()[1] * 0.9, " veri burada kesildi\n (2016-12-13 00:00)",
                 va="top", fontsize=12)
    return _save(fig, "eda_10_aralik_2016_ariza.png")


def eda_stats(raw: pd.DataFrame, clean_stats: dict, grid: pd.DataFrame) -> dict:
    """Notebook yorumlarının dayandığı sayılar."""
    clean, _ = data.clean_minutely(raw)
    night_raw = raw.loc[clean["is_day"] == 0, "poa_irradiance"]
    night_raw = night_raw[night_raw != config.MISSING_SENTINEL]
    poa_raw = raw["poa_irradiance"].where(raw["poa_irradiance"] != config.MISSING_SENTINEL)
    amb_raw = raw["ambient_temp"].where(raw["ambient_temp"] != config.MISSING_SENTINEL)
    ext = poa_raw[poa_raw < config.POA_MIN_VALID]
    day = grid.loc[grid["is_day"]]
    # gün içi POA argmax saati (medyan) ve hesaplanan güneş öğlesi
    g = grid.copy()
    g["day"] = bin_day(grid.index)
    full = g.groupby("day")["poa_irradiance"].agg(["max", "count"])
    good = full[(full["max"] > 300) & (full["count"] == 96)].index
    peaks = g[g["day"].isin(good)].groupby("day")["poa_irradiance"].idxmax()
    peak_hours = [(t - d).total_seconds() / 3600 - 0.125 for d, t in peaks.items()]
    noons = [_noon_hour(d) for d in good]
    elev = grid["sun_elevation"]
    dec = raw.loc["2016-12-13":]
    dec_poa = dec["poa_irradiance"].where(dec["poa_irradiance"] != config.MISSING_SENTINEL)
    dec_ac = dec["ac_power"].where(dec["ac_power"] != config.MISSING_SENTINEL)
    dec_after = dec.loc["2016-12-14":]
    mask = (dec_poa.loc["2016-12-14":] > 500)
    ac_med_fault = float(dec_ac.loc["2016-12-14":][mask].median())
    days = pick_cloudy_clear_days(grid)
    wk = pick_peak_week(grid)
    cap = config.CAPACITY_W
    return {
        "gece_poa_median_ham": round(float(night_raw.median()), 2),
        "sentinel_sayilari": clean_stats["sentinel_counts"],
        "uc_negatif_poa_sayisi": int(len(ext)),
        "uc_negatif_poa_min": round(float(ext.min()), 1),
        "ambient_maks_ham": round(float(amb_raw.max()), 2),
        "ac_kapasite_ustu_dakika": int((raw["ac_power"] > cap).sum()) if cap is not None else None,
        "ac_poa_korelasyonu": round(float(grid["ac_power"].corr(grid["poa_irradiance"])), 4),
        "poa_tepe_saati_medyan": round(float(np.median(peak_hours)), 2),
        "hesaplanan_guney_oglesi_ortalama": round(float(np.mean(noons)), 2),
        "poa_pozitif_ama_yukselme_negatif_orani": round(
            float(((grid["poa_irradiance"] > config.DAYTIME_POA_THRESHOLD) & (elev <= 0)).sum()
                  / (grid["poa_irradiance"] > config.DAYTIME_POA_THRESHOLD).sum()), 4),
        "aralik_14_sonrasi_poa500_ac_medyan": round(ac_med_fault, 2),
        "hafta_yakinlastirma": [str(wk[0].date()), str(wk[-1].date())],
        "acik_gun": str(days["clear"].date()),
        "bulutlu_gun": str(days["cloudy"].date()),
        "gunduz_ortalama_ac": round(float(day["ac_power"].mean()), 1),
        "eksik_oran_yuzde": {c: round(float(clean[c].isna().mean() * 100), 3) for c in config.MEASURED_CHANNELS},
        "grid_satir": int(len(grid)),
    }


def plot_all() -> dict:
    raw = data.load_raw()
    clean, _ = data.clean_minutely(raw)
    grid = data.load_grid()
    return {
        "eda_01": plot_time_series(grid),
        "eda_02": plot_week_zoom(grid),
        "eda_03": plot_daily_profile(grid),
        "eda_04": plot_monthly_profile(grid),
        "eda_05": plot_correlation(grid),
        "eda_06": plot_power_vs_irradiance(grid),
        "eda_07": plot_missing(clean, grid),
        "eda_08": plot_cleaning_before_after(raw, clean),
        "eda_09": plot_cloudy_vs_clear(grid),
        "eda_10": plot_december_fault(raw),
    }


def main() -> None:
    import json

    paths = plot_all()
    raw = data.load_raw()
    _, cs = data.clean_minutely(raw)
    stats = eda_stats(raw, cs, data.load_grid())
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"EDA_TAMAM {len(paths)} figür")


if __name__ == "__main__":
    main()
