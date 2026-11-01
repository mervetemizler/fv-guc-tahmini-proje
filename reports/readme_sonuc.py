# -*- coding: utf-8 -*-
"""README sonuç bloğunu CSV'lerden yeniler (D-10).

results/metrics/summary.csv ve results/metrics/kazanan_ozet.csv okunur;
README.md içindeki SONUC_BASLA / SONUC_BITIS işaretçileri arasını değiştirir.
Elle sayı yazılmaz.

Çalıştırma: .venv/Scripts/python.exe -I reports/readme_sonuc.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src import analysis  # noqa: E402

BASLA = "<!-- SONUC_BASLA -->"
BITIS = "<!-- SONUC_BITIS -->"
KARAR_SIRA = [("hayır", "DL baseline'ı geçemedi"), ("belirsiz", "belirsiz"), ("evet", "DL önde")]


def fmt_tr(x, nd: int = 0) -> str:
    """Türkçe sayı biçimi: binlik ayıracı nokta, ondalık virgül."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def blok_uret() -> str:
    summ = pd.read_csv(ROOT / "results" / "metrics" / "summary.csv", encoding="utf-8")
    kaz = pd.read_csv(ROOT / "results" / "metrics" / "kazanan_ozet.csv", encoding="utf-8")
    satir: list[str] = []

    satir.append("Gündüz maskesi, test kümesi, RMSE (W); DL için 3 tohum ortalaması ± std "
                 "(kaynak: `results/metrics/summary.csv`).")
    satir.append("")
    satir.append("| Model | +1 saat RMSE (W) | +1 saat nRMSE | 16 adım ort. RMSE (W) | 16 adım ort. nRMSE |")
    satir.append("|---|---|---|---|---|")
    d = summ[summ["mask"] == "day"]
    for m in analysis.MODEL_ORDER:
        h4 = d[(d["model"] == m) & (d["scope"] == "h4")]
        m16 = d[(d["model"] == m) & (d["scope"] == "mean16")]
        if h4.empty or m16.empty:
            continue
        h4, m16 = h4.iloc[0], m16.iloc[0]

        def rm(r):
            return f"{fmt_tr(r['RMSE_W_mean'], 1)} ± {fmt_tr(r['RMSE_W_std'], 1)}"

        satir.append(
            f"| {analysis.MODEL_LABELS_TR[m]} | {rm(h4)} | {fmt_tr(h4['nRMSE_mean'], 3)} "
            f"| {rm(m16)} | {fmt_tr(m16['nRMSE_mean'], 3)} |"
        )
    satir.append("")

    n = len(kaz)
    sayim = {k: int((kaz["dl_baseline_gecti"] == k).sum()) for k, _ in KARAR_SIRA}
    satir.append(
        f"**Dürüst karşılaştırma:** {n} kesitin {sayim['hayır']}'inde DL baseline'ı geçemedi, "
        f"{sayim['belirsiz']} belirsiz, {sayim['evet']} DL önde "
        "(gün-bloklu bootstrap, B=1000; kaynak: `results/metrics/kazanan_ozet.csv`)."
    )
    satir.append("")
    satir.append("| Kesit türü | DL baseline'ı geçemedi | Belirsiz | DL önde |")
    satir.append("|---|---|---|---|")
    for kt in kaz["kesit_turu"].drop_duplicates():
        s = kaz[kaz["kesit_turu"] == kt]["dl_baseline_gecti"]
        satir.append(f"| {kt} | {int((s == 'hayır').sum())} | {int((s == 'belirsiz').sum())} "
                     f"| {int((s == 'evet').sum())} |")
    satir.append("")
    satir.append("Ayrıntı: `results/yorum.md`, `reports/rapor.docx`")
    return "\n".join(satir)


def main() -> None:
    readme = ROOT / "README.md"
    metin = readme.read_text(encoding="utf-8")
    if BASLA not in metin or BITIS not in metin:
        raise ValueError("README.md içinde SONUC_BASLA/SONUC_BITIS işaretçileri bulunamadı")
    bas = metin.index(BASLA) + len(BASLA)
    son = metin.index(BITIS)
    yeni = metin[:bas] + "\n" + blok_uret() + "\n" + metin[son:]
    readme.write_text(yeni, encoding="utf-8", newline="\n")
    print("README_SONUC_TAMAM")


if __name__ == "__main__":
    main()
