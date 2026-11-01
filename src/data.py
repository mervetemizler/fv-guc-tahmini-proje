# -*- coding: utf-8 -*-
"""Ham 1 dk parquet -> temiz 15 dk ızgara (temizleme, resample, kısa boşluk doldurma, doğrulama)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402
from src import features  # noqa: E402


def load_raw(path=config.RAW_PARQUET) -> pd.DataFrame:
    """Ham parquet'ten 4 ölçüm kanalını kanonik adlarla okur. -7999 değiştirilmez, kesme yok."""
    raw = pd.read_parquet(path)
    cols = {}
    for name in config.MEASURED_CHANNELS:
        prefix = config.CHANNEL_PREFIXES[name]
        found = [c for c in raw.columns if str(c).startswith(prefix)]
        if len(found) != 1:
            raise ValueError(
                f"'{prefix}' önekiyle tam 1 kolon beklenirdi, bulunan: {found}"
            )
        cols[found[0]] = name
    out = raw[["measured_on", *cols.keys()]].rename(columns=cols)
    out = out.set_index("measured_on")
    out.index = pd.DatetimeIndex(out.index, name="timestamp")
    return out


def clean_minutely(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """D-12 sırasıyla 1 dk temizleme. AC'ye dokunulmaz (gece ofseti korunur)."""
    stats: dict = {}
    sentinel_counts = {c: int((df[c] == config.MISSING_SENTINEL).sum()) for c in df.columns}
    stats["sentinel_counts"] = sentinel_counts
    d = df.mask(df == config.MISSING_SENTINEL)

    poa = d["poa_irradiance"]
    is_day = (poa > config.DAYTIME_POA_THRESHOLD).fillna(False)  # clip'ten ÖNCE
    extreme = poa < config.POA_MIN_VALID
    stats["poa_extreme_negative_count"] = int(extreme.sum())
    poa = poa.mask(extreme)
    night_neg = (poa < 0) & (~is_day)
    stats["poa_night_negative_clipped_count"] = int(night_neg.sum())
    poa = poa.mask(night_neg, 0.0)

    lo, hi = config.AMBIENT_VALID_RANGE
    amb = d["ambient_temp"]
    amb_bad = (amb < lo) | (amb > hi)
    stats["ambient_out_of_range_count"] = int(amb_bad.sum())
    lo, hi = config.MODULE_TEMP_VALID_RANGE
    mt = d["module_temp_1"]
    mt_bad = (mt < lo) | (mt > hi)
    stats["module_temp_out_of_range_count"] = int(mt_bad.sum())

    out = d.assign(
        poa_irradiance=poa,
        ambient_temp=amb.mask(amb_bad),
        module_temp_1=mt.mask(mt_bad),
        is_day=is_day.astype(float),
    )
    return out, stats


def cut_to_data_end(df: pd.DataFrame) -> pd.DataFrame:
    """DATA_START < index <= DATA_END satırlarını tutar (right-closed resample ile uyumlu).

    Bitiş: DATA_END dakikası dahil; böylece son bin (23:45, 00:00] tam 15 dk içerir.
    Başlangıç: DATA_START dakikası bilinçli dışlanır; right-closed kuralında o dakika
    (2014-12-31 23:45, 00:00] binine aittir ve ızgara DATA_START+15dk'dan başlar.
    """
    return df.loc[
        (df.index > pd.Timestamp(config.DATA_START)) & (df.index <= pd.Timestamp(config.DATA_END))
    ]


def _default_index() -> pd.DatetimeIndex:
    return pd.date_range(
        pd.Timestamp(config.DATA_START) + pd.Timedelta(config.FREQ),
        pd.Timestamp(config.DATA_END),
        freq=config.FREQ,
        name="timestamp",
    )


def resample_15min(df: pd.DataFrame, target_index: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    """15 dk ortalama; closed="right", label="right".

    t damgalı değer yalnızca (t-15dk, t] verisini içerir (geleceğe sızıntı yok);
    label="left" YASAK: t damgasına t..t+15 verisini koyardı.
    """
    if "is_day" not in df.columns:
        raise ValueError("resample_15min: girdide 'is_day' kolonu bekleniyor (clean_minutely çıktısı).")
    rs = df.resample(config.FREQ, closed="right", label="right")
    res = rs.mean()
    # Yetersiz örneklem: bin içinde < MIN_VALID_MINUTES geçerli dakika varsa ortalama NaN olur
    # (tek bir dakikalık değerin 15 dk'yı temsil etmesi engellenir). is_day hariç tutulur.
    cnt = rs.count()
    for col in config.MEASURED_CHANNELS:
        if col in res.columns:
            res[col] = res[col].where(cnt[col] >= config.MIN_VALID_MINUTES)
    if target_index is None:
        target_index = _default_index()
    res = res.reindex(target_index)
    res.index.name = "timestamp"
    return res.assign(is_day=(res["is_day"].fillna(0.0) >= 0.5))


def fill_short_gaps(df: pd.DataFrame, max_steps: int = config.MAX_FILL_STEPS) -> tuple[pd.DataFrame, dict]:
    """Yalnızca uzunluğu <= max_steps olan NaN çalışmalarını GEÇMİŞ değerle (ileri doldurma) doldurur.

    İnterpolasyon kullanılmaz: boşluğun sağındaki (gelecekteki) değer boşluğa taşınmaz; böylece
    girdi penceresi/hedef sınırında geleceğe sızıntı oluşmaz. Baştaki NaN'lar doldurulmaz.
    """
    stats: dict = {}
    out = df
    for col in config.MEASURED_CHANNELS:
        if col not in out.columns:
            continue
        s = out[col]
        na = s.isna()
        group = (~na).cumsum()
        run_len = na.groupby(group).transform("sum").where(na, 0)
        past = s.ffill(limit=max_steps)
        fill_mask = na & (run_len <= max_steps) & past.notna()
        filled = s.where(~fill_mask, past)
        stats[col] = {
            "filled_steps": int(fill_mask.sum()),
            "remaining_nan": int(filled.isna().sum()),
        }
        out = out.assign(**{col: filled})
    return out, stats


def validate_grid(grid: pd.DataFrame) -> dict:
    """Veri sözleşmesi (DATA-04); ihlalde Türkçe AssertionError."""
    idx = grid.index
    assert idx.is_monotonic_increasing and idx.is_unique, "Index monoton artan ve benzersiz olmalı"
    diffs = idx.to_series().diff().dropna()
    assert (diffs == pd.Timedelta(config.FREQ)).all(), "Tüm adımlar tam 15 dk olmalı"
    assert idx.min() == pd.Timestamp(config.DATA_START) + pd.Timedelta(config.FREQ), "Başlangıç etiketi hatalı"
    assert idx.max() == pd.Timestamp(config.DATA_END), f"Son etiket {config.DATA_END} olmalı"
    assert not (idx > pd.Timestamp(config.DATA_END)).any(), "DATA_END sonrası zaman damgası var"
    expected = set(config.MEASURED_CHANNELS) | {"is_day"} | set(config.TIME_FEATURES)
    assert set(grid.columns) == expected, f"Kolonlar beklenenden farklı: {set(grid.columns) ^ expected}"
    for c in config.MEASURED_CHANNELS:
        assert pd.api.types.is_float_dtype(grid[c]), f"{c} float olmalı"
        assert not np.isinf(grid[c].to_numpy()).any(), f"{c} içinde sonsuz değer var"
    nan_ratio = {c: float(grid[c].isna().mean()) for c in config.MEASURED_CHANNELS}
    for c in ("ac_power", "poa_irradiance", "ambient_temp"):
        assert nan_ratio[c] == 0, f"{c} NaN oranı 0 olmalı: {nan_ratio[c]}"
    assert nan_ratio["module_temp_1"] < config.MODULE_TEMP_MAX_NAN_RATIO, (
        f"module_temp_1 NaN oranı çok yüksek: {nan_ratio['module_temp_1']}"
    )
    for col, (lo, hi) in {
        "ac_power": config.AC_CONTRACT_RANGE,
        "poa_irradiance": config.POA_CONTRACT_RANGE,
        "ambient_temp": config.AMBIENT_VALID_RANGE,
        "module_temp_1": config.MODULE_TEMP_VALID_RANGE,
    }.items():
        v = grid[col].dropna()
        assert v.between(lo, hi).all(), f"{col} sözleşme aralığı [{lo}, {hi}] dışında: {v.min()}..{v.max()}"
    assert (grid["poa_irradiance"] < 0).sum() == 0, "Negatif POA kaldı"
    assert len(grid) == len(_default_index()), "Satır sayısı beklenenden farklı"
    return {"n_rows": int(len(grid)), "nan_ratio": nan_ratio}


def build_grid(save: bool = True) -> pd.DataFrame:
    """Tüm boru hattı: ham -> temiz -> kes -> 15 dk -> doldur -> öznitelik -> doğrula."""
    raw = load_raw()
    cleaned, clean_stats = clean_minutely(raw)
    cut = cut_to_data_end(cleaned)
    raw_cut = cut_to_data_end(raw)
    # Kapasite bilinmiyorsa (system_info.json) bu istatistik atlanır; sessiz TypeError yerine None.
    ac_over = (
        int((raw_cut["ac_power"] > config.CAPACITY_W).sum()) if config.CAPACITY_W is not None else None
    )
    grid = resample_15min(cut)
    grid, fill_stats = fill_short_gaps(grid)
    grid = features.add_time_features(grid)
    summary = validate_grid(grid)
    if save:
        config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        grid.to_parquet(config.GRID_PARQUET, engine="pyarrow")
        report = {
            **clean_stats,
            "fill": fill_stats,
            "n_rows": summary["n_rows"],
            "nan_ratio": summary["nan_ratio"],
            "start": str(grid.index.min()),
            "end": str(grid.index.max()),
            "data_end": config.DATA_END,
            "data_end_reason": config.DATA_END_REASON,
            "ac_over_capacity_minutes": ac_over,
        }
        with open(config.CLEANING_REPORT, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return grid


def load_grid() -> pd.DataFrame:
    """Kaydedilmiş ızgarayı okur (DatetimeIndex)."""
    g = pd.read_parquet(config.GRID_PARQUET)
    g.index = pd.DatetimeIndex(g.index, name="timestamp")
    return g


def main() -> None:
    try:
        grid = build_grid()
    except Exception as e:  # noqa: BLE001
        print(f"HATA: {e}", file=sys.stderr)
        sys.exit(4)
    print(grid.describe().T)
    print(f"GRID_TAMAM satır={len(grid)}")


if __name__ == "__main__":
    main()
