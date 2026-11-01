# -*- coding: utf-8 -*-
"""MODEL-03/04 birim testi: çıktı şekli, ara uzunluk, parametre oranı, build_model.

Not: torch.zeros girdileri YALNIZCA şekil testi içindir; eğitim gerçek veriyle yapılır.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch  # noqa: E402

from src import config, models  # noqa: E402

torch.manual_seed(0)
W, H, C = config.WINDOW, config.HORIZON, len(config.INPUT_FEATURES)


def test_cikis_sekli():
    x = torch.zeros(4, W, C)
    for m in (models.LSTMNet(), models.CNNLSTM()):
        assert m(x).shape == (4, H)


def test_cnn_ara_uzunluk():
    m = models.CNNLSTM()
    z = m.conv(torch.zeros(4, W, C).transpose(1, 2))
    assert z.shape == (4, 64, 46), z.shape


def test_param_orani():
    a, b = models.count_params(models.LSTMNet()), models.count_params(models.CNNLSTM())
    assert a / b < 3 and b / a < 3, (a, b)
    assert 20_000 < a < 100_000 and 20_000 < b < 100_000, (a, b)


def test_build_model():
    assert isinstance(models.build_model("lstm"), models.LSTMNet)
    assert isinstance(models.build_model("cnn_lstm"), models.CNNLSTM)
    try:
        models.build_model("x")
    except ValueError:
        return
    raise AssertionError("ValueError bekleniyordu")


if __name__ == "__main__":
    for name in ("test_cikis_sekli", "test_cnn_ara_uzunluk", "test_param_orani", "test_build_model"):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
