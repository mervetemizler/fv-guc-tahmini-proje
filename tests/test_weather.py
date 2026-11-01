# -*- coding: utf-8 -*-
"""EVAL-06 birim testi: hava sınıfı eşikleri, bin günü kayması, KT aralığı, hücre sınıflaması."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import analysis, data, weather  # noqa: E402


def test_classify_thresholds():
    assert weather.classify(0.80) == 2
    assert weather.classify(0.75) == 2
    assert weather.classify(0.5) == 1
    assert weather.classify(0.40) == 1
    assert weather.classify(0.39) == 0
    assert weather.classify(float("nan")) == -1


def test_bin_day_shift():
    yt = np.array([[np.datetime64("2016-06-02T00:00:00", "ns")]])
    day, hour = analysis.target_day_hour(yt)
    assert day[0, 0] == np.datetime64("2016-06-01")
    assert hour[0, 0] == 23


def test_kt_range():
    days = weather.daily_clearness(data.load_grid())
    kt = days["KT"].dropna()
    assert len(kt) > 0
    assert kt.min() >= 0.0 and kt.max() <= 1.2, (kt.min(), kt.max())


def test_test_cells_classified():
    days = weather.daily_clearness(data.load_grid())
    w = analysis.load_test()
    cls = weather.cell_class(w["y_time"], days)
    assert cls.shape == w["y"].shape
    assert int(((cls == -1) & w["y_day"]).sum()) == 0
    assert set(np.unique(cls[w["y_day"]])) <= {0, 1, 2}


if __name__ == "__main__":
    for name in ("test_classify_thresholds", "test_bin_day_shift", "test_kt_range", "test_test_cells_classified"):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
