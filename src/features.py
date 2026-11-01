# -*- coding: utf-8 -*-
"""Zaman ve güneş konumu öznitelikleri (pvlib yok, NOAA/Spencer numpy formülü)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config


def solar_elevation_deg(
    idx: pd.DatetimeIndex, lat: float, lon: float, utc_offset_h: float
) -> np.ndarray:
    """Güneş yüksekliği (derece). Zaman damgası sabit yerel standart saat kabul edilir (D-07)."""
    doy = idx.day_of_year.to_numpy()
    h = idx.hour.to_numpy() + idx.minute.to_numpy() / 60
    g = 2 * np.pi / 365 * (doy - 1 + (h - 12) / 24)
    eot = 229.18 * (
        0.000075
        + 0.001868 * np.cos(g)
        - 0.032077 * np.sin(g)
        - 0.014615 * np.cos(2 * g)
        - 0.040849 * np.sin(2 * g)
    )
    decl = (
        0.006918
        - 0.399912 * np.cos(g)
        + 0.070257 * np.sin(g)
        - 0.006758 * np.cos(2 * g)
        + 0.000907 * np.sin(2 * g)
        - 0.002697 * np.cos(3 * g)
        + 0.00148 * np.sin(3 * g)
    )
    tst = h * 60 + eot + 4 * lon - 60 * utc_offset_h
    ha = np.deg2rad(tst / 4 - 180)
    la = np.deg2rad(lat)
    return np.rad2deg(
        np.arcsin(np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ha))
    )


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Saat/yılın günü sin-cos ve güneş yüksekliği ekler (etiket zaman damgasında)."""
    idx = df.index
    h = idx.hour.to_numpy() + idx.minute.to_numpy() / 60
    doy = idx.day_of_year.to_numpy()
    return df.assign(
        hour_sin=np.sin(2 * np.pi * h / 24),
        hour_cos=np.cos(2 * np.pi * h / 24),
        doy_sin=np.sin(2 * np.pi * doy / 365.25),
        doy_cos=np.cos(2 * np.pi * doy / 365.25),
        sun_elevation=solar_elevation_deg(
            idx, config.LATITUDE, config.LONGITUDE, config.UTC_OFFSET_H
        ),
    )
