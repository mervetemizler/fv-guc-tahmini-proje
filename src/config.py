# -*- coding: utf-8 -*-
"""Merkezi sabitler: yollar, seed, pencere/ufuk, bölme tarihleri, hiperparametreler.

Yalnızca standart kütüphane kullanır (matplotlib fonksiyon içinde import edilir).
"""
from __future__ import annotations

import json
from pathlib import Path

# --- Yollar -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_CSV_DIR = RAW_DIR / "pvdaq_csv"
PROCESSED_DIR = DATA_DIR / "processed"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
RESULTS_DIR = PROJECT_ROOT / "results"
METRICS_DIR = RESULTS_DIR / "metrics"
FIGURES_DIR = RESULTS_DIR / "figures"
MODELS_DIR = RESULTS_DIR / "models"
PREDICTIONS_DIR = RESULTS_DIR / "predictions"
REPORTS_DIR = PROJECT_ROOT / "reports"
PRESENTATION_DIR = PROJECT_ROOT / "presentation"

ENCODING = "utf-8"

# --- Tekrar üretilebilirlik -------------------------------------------------
SEED = 42
SEEDS = (42, 43, 44)

# --- Veri ve zaman ----------------------------------------------------------
SYSTEM_ID = 4
MISSING_SENTINEL = -7999
RAW_FREQ = "1min"
FREQ = "15min"
STEPS_PER_HOUR = 4
STEPS_PER_DAY = 96

WINDOW = 96            # 24 saat geçmiş
HORIZON = 16           # 1-16 adım (4 saate kadar)
MAIN_HORIZON_STEPS = 4  # +1 saat ana ufuk
MAX_FILL_STEPS = 2
MIN_VALID_MINUTES = 8  # 15 dk bininde ölçüm kanalı için gereken en az geçerli (NaN olmayan) dakika
MAX_GAP_IN_WINDOW = 0  # pencere içinde doldurulmamış boşluk kabul edilmez

DAYTIME_POA_THRESHOLD = 20.0  # W/m2, gündüz maskesi eşiği

TARGET = "ac_power"
# Hedefin birimi: PVDAQ ac_power__315 kolonu WATT (W) cinsindendir (ham max ~1158,8 W).
# Faz 2'de hedef kW'a çevrilirse bu dönüşüm TEK bir yerde yapılmalı ve TARGET_UNIT güncellenmeli.
TARGET_UNIT = "W"
# PVDAQ kolonlarında "__NNN" sensör eki yıla göre değişebilir; kolonlar ön ek ile seçilir.
RAW_COLUMN_PREFIXES = {
    "ac_power": "ac_power",
    "dc_power": "dc_power",
    "poa_irradiance": "poa_irradiance",
    "ambient_temp": "ambient_temp",
    "module_temp": "module_temp_1",
}


# --- Seçilen yıllar ve sistem bilgisi (Plan 01-02 yazar, burası okur) -------
def _load_json(path: Path):
    """Dosya yoksa None döner."""
    if not Path(path).exists():
        return None
    with open(path, "r", encoding=ENCODING) as f:
        return json.load(f)


SELECTED_YEARS_FILE = RAW_DIR / "selected_years.json"
SYSTEM_INFO_FILE = RAW_DIR / "system_info.json"

_sel = _load_json(SELECTED_YEARS_FILE)
if _sel is None:
    # Sessiz varsayılan YOK: yanlış yıllar parquet yolunu ve bölme tarihlerini kaydırır.
    raise FileNotFoundError(
        f"{SELECTED_YEARS_FILE} bulunamadı; önce 'python -I src/download_pvdaq.py probe' "
        "çalıştırarak yıl seçimini üretin."
    )
try:
    _years = tuple(int(y) for y in _sel["years"])
except (KeyError, TypeError, ValueError) as e:
    raise ValueError(f"selected_years.json geçersiz ('years' okunamadı): {e}") from e
if len(_years) != 2 or _years[1] != _years[0] + 1:
    raise ValueError(
        f"selected_years.json geçersiz: ardışık 2 yıl bekleniyordu, bulunan: {_years}"
    )
DATA_YEARS = _years
Y1, Y2 = DATA_YEARS

RAW_PARQUET = RAW_DIR / f"pvdaq_sys4_{Y1}_{Y2}.parquet"

_info = _load_json(SYSTEM_INFO_FILE)
# Nominal kapasite kW cinsinden (yalnızca belgeleme/gösterim için).
# DİKKAT: nRMSE paydası olarak CAPACITY_KW KULLANILMAZ (hedef W cinsinden -> 1000 kat hata).
CAPACITY_KW = (
    float(_info["capacity_kw"])
    if _info is not None and _info.get("capacity_kw") is not None
    else None
)
# nRMSE paydası (hedefle aynı birim, W): nRMSE = RMSE[W] / CAPACITY_W.
# Faz 3'te None ise hata verilmelidir.
CAPACITY_W = CAPACITY_KW * 1000.0 if CAPACITY_KW is not None else None

# --- Kronolojik bölme (ay-segmentleri, sol kapalı sağ açık) -----------------
DATA_START = f"{Y1}-01-01 00:00"
# Izgaranın SON bin etiketi. 15 dk resample right-closed/right-label olduğundan ham
# satırlar DATA_START < measured_on <= DATA_END tutulur (son bin (23:45, 00:00] tam 15 dk).
DATA_END = f"{Y2}-12-13 00:00"
DATA_END_REASON = (
    "2016-12-13 10:13'ten itibaren module_temp_1 sürekli eksik ve 2016-12-14'ten itibaren "
    "invertör kapalı (POA 1000+ W/m² iken AC ≈ 3 W); bu günler fiziksel olarak tahmin "
    "edilemez. Kullanıcı kararıyla veri 2016-12-13 00:00'da kesildi; Aralık test segmenti "
    "12 gündür."
)


def _month_segment(year: int, month: int) -> tuple[str, str]:
    """[ay başı, sonraki ay başı) çifti (bin BAŞLANGICINA göre yorumlanır)."""
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return (f"{year}-{month:02d}-01 00:00", f"{ny}-{nm:02d}-01 00:00")


# Segmentler bin başlangıcına göre yorumlanır (15 dk bin başlangıcı = etiket - 15 dk).
SPLITS = {
    "train": [(f"{Y1}-01-01 00:00", f"{Y2}-01-01 00:00")],
    "val": [_month_segment(Y2, m) for m in (1, 3, 5, 7, 9, 11)],
    "test": [_month_segment(Y2, m) for m in (2, 4, 6, 8, 10)] + [(f"{Y2}-12-01 00:00", DATA_END)],
}
# KARAR VERİLDİ (Faz 2, D-01..D-05): tek/çift ay bölmesi her mevsimi hem val hem test'e
# koyar; pencereler segment içinde üretilir (D-02). Val ile test komşu aylardır; erken
# durdurma bu aylardan gelir ama hiperparametre testte ayarlanmaz (dürüstlük notu).
SPLIT_RATIONALE = (
    "Kronolojik bölme (KARAR VERİLDİ, Faz 2): train = Y1 tamamı; Y2'de tek aylar "
    "(Oca, Mar, May, Tem, Eyl, Kas) = val, çift aylar (Şub, Nis, Haz, Ağu, Eki, Ara) = test. "
    "Her mevsim val ve test'te temsil edilir; pencereler ay-segmenti içinde üretilir; "
    "val/test komşu aylardır, erken durdurma val'den gelir ancak hiperparametre testte "
    "ayarlanmaz. Veri 2016-12-13 00:00'da kesilir."
)

# --- Öznitelikler (D-06, D-07, D-09) ---------------------------------------
MEASURED_CHANNELS = ["ac_power", "poa_irradiance", "ambient_temp", "module_temp_1"]
CHANNEL_PREFIXES = {
    "ac_power": "ac_power__",
    "poa_irradiance": "poa_irradiance__",
    "ambient_temp": "ambient_temp__",
    "module_temp_1": "module_temp_1__",
}
TIME_FEATURES = ["hour_sin", "hour_cos", "doy_sin", "doy_cos", "sun_elevation"]
INPUT_FEATURES = MEASURED_CHANNELS + TIME_FEATURES  # 9 kanal, sıra sabit

# --- Temizlik eşikleri ------------------------------------------------------
POA_MIN_VALID = -50.0
AMBIENT_VALID_RANGE = (-35.0, 45.0)
MODULE_TEMP_VALID_RANGE = (-40.0, 90.0)
AC_CONTRACT_RANGE = (-5.0, 1300.0)
POA_CONTRACT_RANGE = (0.0, 1600.0)
MODULE_TEMP_MAX_NAN_RATIO = 0.005
UTC_OFFSET_H = -7.0  # sabit yerel standart saat, DST yok (D-07)

_lat = _info.get("latitude") if _info is not None else None
_lon = _info.get("longitude") if _info is not None else None
if _lat is None or _lon is None:
    raise ValueError("system_info.json içinde latitude/longitude bulunamadı.")
LATITUDE = float(_lat)
LONGITUDE = float(_lon)

SEASON_BY_MONTH = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3}
SEASON_NAMES = ("Kış", "İlkbahar", "Yaz", "Sonbahar")
DROP_ALL_NIGHT_SPLITS = ("train", "val")  # D-10

# --- Çıktı dosyaları --------------------------------------------------------
GRID_PARQUET = PROCESSED_DIR / "grid_15min.parquet"
CLEANING_REPORT = PROCESSED_DIR / "cleaning_report.json"
SCALERS_FILE = PROCESSED_DIR / "scalers.joblib"
WINDOWS_NPZ = {s: PROCESSED_DIR / f"windows_{s}.npz" for s in ("train", "val", "test")}
WINDOWS_SUMMARY = PROCESSED_DIR / "windows_summary.json"

# --- Eğitim hiperparametreleri ---------------------------------------------
BATCH_SIZE = 256
LR = 1e-3
WEIGHT_DECAY = 1e-5
MAX_EPOCHS = 60
EARLY_STOP_PATIENCE = 8
LR_PATIENCE = 3
GRAD_CLIP = 1.0
LSTM_HIDDEN = 64
LSTM_LAYERS = 2
DROPOUT = 0.2
CNN_CHANNELS = (32, 64)
CNN_KERNEL = 3

# --- Grafik stili -----------------------------------------------------------
MPL_FONT = "DejaVu Sans"
FIG_DPI = 200
FIG_FONT_SIZE = 14


def apply_plot_style() -> None:
    """matplotlib rcParams ayarlarını uygular (import burada, config hafif kalsın)."""
    import matplotlib

    matplotlib.rcParams.update(
        {
            "font.family": MPL_FONT,
            "font.size": FIG_FONT_SIZE,
            "savefig.dpi": FIG_DPI,
            "axes.unicode_minus": False,
            "figure.dpi": 100,
        }
    )


def summary() -> str:
    """Yapılandırmanın Türkçe özeti."""
    return (
        f"Yıllar: {Y1}-{Y2}\n"
        f"Ham parquet: {RAW_PARQUET}\n"
        f"Bölme: train {len(SPLITS['train'])} segment, val {len(SPLITS['val'])} segment, "
        f"test {len(SPLITS['test'])} segment; veri sonu {DATA_END}\n"
        f"Hedef: {TARGET} [{TARGET_UNIT}]\n"
        f"Kapasite: {CAPACITY_KW} kW = {CAPACITY_W} W (nRMSE paydası: CAPACITY_W)"
    )
