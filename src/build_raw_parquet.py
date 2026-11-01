# -*- coding: utf-8 -*-
"""Günlük PVDAQ CSV'lerini tek bir ham parquet dosyasına birleştirir ve envanter çıkarır.

Ham değerler DEĞİŞTİRİLMEZ (-7999 olduğu gibi kalır); temizleme Faz 2'nin işidir.
Kullanım: python -I src/build_raw_parquet.py --years 2015 2016
"""
import argparse
import glob
import json
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Varsayılan yollar çalışma dizinine değil proje köküne bağlıdır (config.py ile aynı kök).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV_DIR = os.path.join(ROOT, "data", "raw", "pvdaq_csv")
DEFAULT_OUT_DIR = os.path.join(ROOT, "data", "raw")
SELECTED_YEARS_FILE = os.path.join(ROOT, "data", "raw", "selected_years.json")

SENTINEL = -7999
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # PVDAQ günlük CSV'lerindeki measured_on biçimi
REQUIRED_ALL = ["ac_power", "dc_power", "poa_irradiance", "ambient_temp", "module_temp_1"]
REQUIRED_HARD = ["ac_power", "poa_irradiance", "ambient_temp", "module_temp_1"]


def _rel_to_root(path):
    """Yol proje kökü içindeyse köke göreli ('/' ayraçlı), değilse mutlak döner."""
    p = os.path.abspath(path)
    try:
        if os.path.commonpath([p, ROOT]) == ROOT:
            return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:  # farklı sürücüler (Windows)
        pass
    return p.replace("\\", "/")


def read_year(csv_dir, year):
    """Bir yılın tüm günlük CSV'lerini okuyup birleştirir."""
    files = sorted(glob.glob(os.path.join(csv_dir, str(year), "system_4_*.csv")))
    if not files:
        print(f"HATA: {year} için CSV bulunamadı", file=sys.stderr)
        sys.exit(4)
    parts = [pd.read_csv(f, encoding="utf-8", low_memory=False) for f in files]
    df = pd.concat(parts, ignore_index=True)
    # Zaman formatı açıkça zorlanır (pandas 3 formatı ilk elemandan çıkarır; farklı formatlı
    # bir gün sessizce yanlış ayrıştırılmasın, hata versin).
    try:
        df["measured_on"] = pd.to_datetime(df["measured_on"], format=TIME_FORMAT)
    except (ValueError, TypeError) as e:
        print(f"HATA: {year} measured_on '{TIME_FORMAT}' formatında değil: {e}", file=sys.stderr)
        sys.exit(4)
    # Ölçüm kolonları sayısal olmak zorunda: metin/karışık tipli bir kolon sentinel ve
    # aralık kontrollerinden sessizce kaçar ya da to_parquet'te ArrowTypeError verir.
    data_cols = [c for c in df.columns if c != "measured_on"]
    converted = {}
    for c in data_cols:
        try:
            converted[c] = pd.to_numeric(df[c], errors="raise")
        except (ValueError, TypeError) as e:
            print(f"HATA: {year} '{c}' kolonu sayısal değil: {e}", file=sys.stderr)
            sys.exit(4)
    df = df.assign(**converted)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", default=DEFAULT_CSV_DIR)
    ap.add_argument("--years", nargs=2, type=int, required=True)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    y1, y2 = args.years

    # --years, config.py'nin okuduğu selected_years.json ile tutarlı olmalı; aksi halde
    # config.RAW_PARQUET ile eşleşmeyen bir parquet üretilir ve envanter üzerine yazılır.
    if not os.path.exists(SELECTED_YEARS_FILE):
        print(f"HATA: {SELECTED_YEARS_FILE} yok; önce 'python -I src/download_pvdaq.py probe' "
              "çalıştırın", file=sys.stderr)
        sys.exit(2)
    with open(SELECTED_YEARS_FILE, "r", encoding="utf-8") as f:
        sel_years = [int(y) for y in json.load(f)["years"]]
    if [y1, y2] != sel_years:
        print(f"HATA: --years {y1} {y2}, selected_years.json ile uyuşmuyor ({sel_years}); "
              "config.RAW_PARQUET bu yılları bekler", file=sys.stderr)
        sys.exit(2)

    years_inv = {}
    frames = []
    dup_total = {}
    for y in (y1, y2):
        df = read_year(args.csv_dir, y)
        df = df.sort_values("measured_on", kind="stable")
        n0 = len(df)
        df = df.drop_duplicates(subset="measured_on", keep="first")
        dup_total[y] = n0 - len(df)
        days = df["measured_on"].dt.normalize()
        expected = pd.date_range(f"{y}-01-01", f"{y}-12-31", freq="D")
        present = set(days.unique())
        missing = [d.strftime("%Y-%m-%d") for d in expected if d not in present]
        per_day = df.groupby(days).size()
        years_inv[str(y)] = {
            "days": int(days.nunique()),
            "expected_days": int(len(expected)),
            "missing_dates": missing,
            "rows": int(len(df)),
            "rows_per_day_min": int(per_day.min()),
            "rows_per_day_median": float(per_day.median()),
            "rows_per_day_max": int(per_day.max()),
            "time_min": str(df["measured_on"].min()),
            "time_max": str(df["measured_on"].max()),
            "duplicates_dropped": int(dup_total[y]),
        }
        frames.append(df)

    full = pd.concat(frames, ignore_index=True).sort_values("measured_on", kind="stable")
    full = full.reset_index(drop=True)
    columns = list(full.columns)

    # Gerekli kolonlar (ön ek -> gerçek adlar)
    required = {p: [c for c in columns if c.startswith(p)] for p in REQUIRED_ALL}

    # -7999 oranları
    num_cols = [c for c in columns if c != "measured_on" and pd.api.types.is_numeric_dtype(full[c])]
    sentinel_share = {c: float((full[c] == SENTINEL).mean()) for c in num_cols}
    all_sentinel = [c for c in num_cols if ((full[c] == SENTINEL) | full[c].isna()).all()]

    # Yıl bazında gerekli ön ek kontrolü
    bad = []
    for y, df in zip((y1, y2), frames):
        for p in REQUIRED_HARD:
            cols = [c for c in df.columns if c.startswith(p)]
            if not cols:
                bad.append(f"{y}: {p} kolonu yok")
                continue
            if all(((df[c] == SENTINEL) | df[c].isna()).all() for c in cols):
                bad.append(f"{y}: {p} tamamen boş (-7999/NaN)")
    if bad:
        print("HATA: gerekli kolon sorunu: " + "; ".join(bad), file=sys.stderr)
        sys.exit(4)
    for p, cols in required.items():
        if len(cols) > 1:
            print(f"UYARI: '{p}' için birden fazla kolon: {cols} (Faz 2 birleştirir)")

    # Birim/saat dilimi kanıtı: sentinel hariç değer aralıkları ve tepe saat
    ranges = {}
    for c in num_cols:
        s = full[c][full[c] != SENTINEL]
        if len(s):
            ranges[c] = {"min": float(s.min()), "p99": float(s.quantile(0.99)), "max": float(s.max())}
    poa = required["poa_irradiance"][0]
    acp = required["ac_power"][0]
    valid = full[
        (full[poa] != SENTINEL) & (full[acp] != SENTINEL) & full[poa].notna() & full[acp].notna()
    ]
    # Dakika çözünürlüğünde gün içi profil (saat kutusu kullanılmaz: dt.hour aşağı yuvarlar
    # ve kutuyu sol kenarında temsil ettiği için merkez ~0,5 saat erken çıkıyordu).
    minute_of_day = valid["measured_on"].dt.hour * 60 + valid["measured_on"].dt.minute
    poa_prof = valid.groupby(minute_of_day)[poa].mean()
    ac_prof = valid.groupby(minute_of_day)[acp].mean()
    # Tepe: 15 dk merkezli kayan ortalama ile yumuşatılmış profilin maksimumu
    poa_peak_h = float(poa_prof.rolling(15, center=True).mean().idxmax()) / 60.0
    ac_peak_h = float(ac_prof.rolling(15, center=True).mean().idxmax()) / 60.0
    # Gün içi ortalama profilin merkezi (ağırlıklı saat) güneş öğlesi tahmini için
    pos = poa_prof.clip(lower=0)
    centroid = float((pos * pos.index).sum() / pos.sum()) / 60.0 if pos.sum() > 0 else None

    def _hhmm(h):
        if h is None:
            return None
        m = int(round(h * 60))
        return f"{m // 60:02d}:{m % 60:02d}"

    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, f"pvdaq_sys4_{y1}_{y2}.parquet")
    full.to_parquet(out, engine="pyarrow", index=False)
    mb = os.path.getsize(out) / 1e6

    inv = {
        "years": years_inv,
        "columns": columns,
        "required_columns": required,
        "sentinel_share": sentinel_share,
        "all_sentinel_columns": all_sentinel,
        "value_ranges_excl_sentinel": ranges,
        "timezone_evidence": {
            "method": "dakika bazlı gün içi ortalama profil; tepe = 15 dk merkezli kayan "
                      "ortalamanın maksimumu; merkez = POA (>=0) ağırlıklı ortalama dakika",
            "poa_peak_hour": round(poa_peak_h, 3),
            "poa_peak_hhmm": _hhmm(poa_peak_h),
            "ac_power_peak_hour": round(ac_peak_h, 3),
            "ac_power_peak_hhmm": _hhmm(ac_peak_h),
            "poa_centroid_hour": round(centroid, 3) if centroid is not None else None,
            "poa_centroid_hhmm": _hhmm(centroid),
        },
        "parquet_path": _rel_to_root(out),
        "parquet_mb": round(mb, 2),
        "built_on": "2026-11-01",
    }
    with open(os.path.join(args.out_dir, "raw_inventory.json"), "w", encoding="utf-8") as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)
    print(f"Tamam: {out} ({mb:.1f} MB), satır={len(full)}")
    for y, v in years_inv.items():
        print(y, v["days"], "/", v["expected_days"], "gün,", v["rows"], "satır")


if __name__ == "__main__":
    main()
