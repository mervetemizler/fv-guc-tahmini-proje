# -*- coding: utf-8 -*-
"""Ortam kontrolü: GPU smoke testi ve Türkçe karakter test grafiği."""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from src import config  # noqa: E402


def gpu_kontrol() -> None:
    import torch
    import torch.nn as nn

    print("torch:", torch.__version__)
    print("CUDA sürümü:", torch.version.cuda)
    print("cuda.is_available():", torch.cuda.is_available())
    if not torch.cuda.is_available():
        print("HATA: CUDA kullanılamıyor; GPU'lu torch kurulumunu kontrol edin.")
        sys.exit(1)
    print("Cihaz:", torch.cuda.get_device_name(0))
    lstm = nn.LSTM(input_size=8, hidden_size=16, batch_first=True).to("cuda")
    cikti, _ = lstm(torch.randn(4, 96, 8, device="cuda"))
    print("LSTM çıktı şekli:", tuple(cikti.shape))


def turkce_kontrol() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    config.apply_plot_style()
    with warnings.catch_warnings(record=True) as yakalanan:
        warnings.simplefilter("always")
        fig, ax = plt.subplots(figsize=(8, 4.5))
        x = np.linspace(0, 24, 200)
        ax.plot(x, np.sin(x / 24 * 2 * np.pi))
        ax.set_title("Türkçe karakter testi: ç ğ ı İ ö ş ü Ç Ğ Ö Ş Ü")
        ax.set_xlabel("Saat (yerel)")
        ax.set_ylabel("Güç (kW) — ışınım")
        ax.text(0.05, 0.05, "Çok değişkenli güneş üretimi tahmini",
                transform=ax.transAxes,
                bbox=dict(boxstyle="round", facecolor="white"))
        config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(config.FIGURES_DIR / "tr_karakter_testi.png", dpi=config.FIG_DPI)
        plt.close(fig)
    kotu = [str(w.message) for w in yakalanan
            if "Glyph" in str(w.message) or "missing from font" in str(w.message)]
    if kotu:
        print("Eksik glif uyarıları:")
        for m in kotu:
            print(" -", m)
        sys.exit(2)
    print("Türkçe grafik üretildi, eksik glif yok.")


if __name__ == "__main__":
    gpu_kontrol()
    turkce_kontrol()
    print("ORTAM_KONTROLU_TAMAM")
