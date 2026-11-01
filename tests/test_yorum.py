# -*- coding: utf-8 -*-
"""results/yorum.md sayıları ile kazanan_ozet.csv tutarlılığı (CR-01 sonrası)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd  # noqa: E402

from src import config  # noqa: E402

KZ = config.METRICS_DIR / "kazanan_ozet.csv"
YORUM = Path(__file__).resolve().parents[1] / "results" / "yorum.md"


def _sayilar():
    df = pd.read_csv(KZ)
    vc = df["dl_baseline_gecti"].value_counts()
    return df, int(len(df)), int(vc.get("hayır", 0)), int(vc.get("belirsiz", 0)), int(vc.get("evet", 0))


def test_yorum_sayilari_csv_ile_eslesir():
    df, n, n_hayir, n_bel, n_evet = _sayilar()
    txt = YORUM.read_text(encoding="utf-8")
    assert f"{n} kesitten {n_hayir}" in txt, (n, n_hayir)
    assert f"{n_bel}'" in txt and f"{n_evet}'" in txt
    assert n_hayir + n_bel + n_evet == n


def test_eski_sayi_kalmadi():
    _, n, n_hayir, _, _ = _sayilar()
    if not (n_hayir == 14 and n == 30):
        assert "30 kesitten 14'ünde" not in YORUM.read_text(encoding="utf-8")


def test_karar_olcutu_ve_ci():
    df, *_ = _sayilar()
    assert "karar_olcutu" in df.columns
    assert set(df["karar_olcutu"]) <= {"bootstrap", "seed_std"}
    b = df[df["karar_olcutu"] == "bootstrap"]
    assert len(b) > 0
    assert (b["ci_low"] <= b["boot_fark_W"]).all() and (b["boot_fark_W"] <= b["ci_high"]).all()
    # karar, GA ile tutarlı
    belirsiz = (b["ci_low"] <= 0) & (b["ci_high"] >= 0)
    assert ((b["dl_baseline_gecti"] == "belirsiz") == belirsiz).all()


if __name__ == "__main__":
    for name in ("test_yorum_sayilari_csv_ile_eslesir", "test_eski_sayi_kalmadi", "test_karar_olcutu_ve_ci"):
        globals()[name]()
        print(f"OK {name}")
    print("TESTLER_TAMAM")
