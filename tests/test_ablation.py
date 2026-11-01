# -*- coding: utf-8 -*-
"""EVAL-04 birim testi: grup kanalları, tablo maskesi, build_model(n_in), train_one imzası."""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402
import torch  # noqa: E402

from src import ablation, baselines, config, models, train  # noqa: E402

FN = list(config.INPUT_FEATURES)


def test_group_channels():
    exp = {"A_guc": 1, "B_zaman": 6, "C_isinim": 7, "D_tam": 9}
    for g, n in exp.items():
        idx = ablation.feature_idx(g, FN)
        assert len(idx) == n, (g, len(idx))
        assert [FN[i] for i in idx] == ablation.GROUPS[g]


def test_tabular_mask_counts():
    X = np.random.default_rng(0).normal(size=(5, config.WINDOW, len(FN))).astype(np.float32)
    _, names = baselines.make_tabular_features(X, FN)
    exp = {"A_guc": 24, "B_zaman": 29, "C_isinim": 53, "D_tam": 57}
    for g, n in exp.items():
        assert int(ablation.tabular_mask(names, g).sum()) == n, g


def test_build_model_n_in():
    for name, n in (("lstm", 1), ("cnn_lstm", 6)):
        m = models.build_model(name, n_in=n)
        out = m(torch.zeros(2, config.WINDOW, n))
        assert tuple(out.shape) == (2, config.HORIZON)
    m = models.build_model("lstm")
    assert tuple(m(torch.zeros(2, config.WINDOW, len(FN))).shape) == (2, config.HORIZON)


def test_train_one_signature():
    p = inspect.signature(train.train_one).parameters
    assert p["feature_idx"].default is None


def _row(grup, model, seed, rmse, kaynak="ablasyon", mask="day", scope="mean16"):
    return dict(grup=grup, model=model, seed=seed, n_in=1, kaynak=kaynak, mask=mask,
                scope=scope, n=10, MAE_W=1.0, RMSE_W=rmse, R2=0.5, nRMSE=0.1)


def _old_df():
    import pandas as pd
    return pd.DataFrame([
        _row("A_guc", "linreg", float("nan"), 10.0),
        _row("A_guc", "lstm", 42, 20.0),
        _row("A_guc", "lstm", 43, 21.0),
        _row("D_tam", "lstm", 42, 5.0, kaynak="faz3"),
    ])


def test_merge_rows_kismi_korur():
    import pandas as pd
    old = _old_df()
    new = pd.DataFrame([_row("A_guc", "lstm", 42, 99.0), _row("A_guc", "lstm", 43, 98.0)])
    out = ablation.merge_rows(old, new)
    assert len(out) == 3
    assert (out["kaynak"] == "ablasyon").all()
    lin = out[out["model"] == "linreg"]
    assert len(lin) == 1 and lin["RMSE_W"].iloc[0] == 10.0
    assert sorted(out[out["model"] == "lstm"]["RMSE_W"]) == [98.0, 99.0]


def test_merge_rows_yeni_anahtar_ekler():
    import pandas as pd
    old = _old_df()
    new = pd.DataFrame([_row("B_zaman", "lstm", 42, 7.0)])
    out = ablation.merge_rows(old, new)
    assert len(out) == 4
    assert ((out["grup"] == "B_zaman") & (out["RMSE_W"] == 7.0)).sum() == 1


def test_merge_rows_faz3_dokunmaz():
    import pandas as pd
    out = ablation.merge_rows(_old_df(), pd.DataFrame([_row("A_guc", "lstm", 42, 1.0)]))
    assert "faz3" not in set(out["kaynak"])


def test_mevcut_csv_tam():
    import pandas as pd
    f = config.METRICS_DIR / "ablation_metrics.csv"
    if f.exists():
        assert len(pd.read_csv(f)) == ablation.EXPECTED_TOTAL_ROWS == 128


if __name__ == "__main__":
    for name in ("test_group_channels", "test_tabular_mask_counts",
                 "test_build_model_n_in", "test_train_one_signature",
                 "test_merge_rows_kismi_korur", "test_merge_rows_yeni_anahtar_ekler",
                 "test_merge_rows_faz3_dokunmaz", "test_mevcut_csv_tam"):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
