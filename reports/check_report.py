# -*- coding: utf-8 -*-
"""reports/rapor.docx yapı, atıf ve yer tutucu kontrolü.

Çalıştırma: .venv/Scripts/python.exe -I reports/check_report.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402

from src import config  # noqa: E402

BASLIKLAR = ("Giriş", "Literatür", "Veri", "Yöntem", "Deneyler", "Sonuçlar", "Tartışma", "Sonuç", "Kaynakça")
YASAK = ("Taslak", "eklenecek", "TODO", "lorem")


def main():
    path = config.REPORTS_DIR / "rapor.docx"
    assert path.exists(), f"Rapor bulunamadı: {path}"
    doc = Document(str(path))

    h1 = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
    for b in BASLIKLAR:
        assert any(b in h for h in h1), f"Başlık eksik: {b} (mevcut: {h1})"

    xml = doc.element.xml
    assert "w:fldChar" in xml and "TOC" in xml, "İçindekiler alanı yok"
    n_img = len(doc.inline_shapes)
    assert n_img >= 10, f"Şekil sayısı yetersiz: {n_img}"

    paras = [p.text for p in doc.paragraphs]
    i_kay = max(i for i, p in enumerate(doc.paragraphs) if p.style.name == "Heading 1" and "Kaynakça" in p.text)
    kaynak = [t for t in paras[i_kay + 1:] if t.strip()]
    nums = []
    for t in kaynak:
        m = re.match(r"\[(\d+)\]", t)
        assert m, f"Kaynakça kaydı [n] ile başlamıyor: {t[:60]}"
        nums.append(int(m.group(1)))
        assert "doi" in t.lower() or "http" in t, f"Kayıtta DOI/URL yok: {t[:60]}"
    assert 8 <= len(kaynak) <= 12, f"Kaynakça kayıt sayısı: {len(kaynak)}"
    assert sorted(nums) == list(range(1, len(nums) + 1)), f"Numaralar ardışık değil: {nums}"

    govde = "\n".join(paras[:i_kay])
    for tbl in doc.tables:
        for row in tbl.rows:
            for c in row.cells:
                govde += "\n" + c.text
    atif = set()
    for m in re.finditer(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]", govde):
        for x in re.split(r"\s*,\s*", m.group(1)):
            atif.add(int(x))
    assert atif == set(nums), f"Atıf kümesi {sorted(atif)} != kaynakça {sorted(nums)}"

    tum = "\n".join(paras)
    for y in YASAK:
        assert y.lower() not in tum.lower(), f"Yasak ifade bulundu: {y}"
    assert "[Ad Soyad]" in tum and "Kasım 2026" in tum, "Kapak yer tutucuları/tarih eksik"

    kz = pd.read_csv(config.RESULTS_DIR / "metrics" / "kazanan_ozet.csv")
    n_toplam = len(kz)
    n_hayir = int((kz.dl_baseline_gecti == "hayır").sum())
    assert f"{n_hayir}" in tum and f"{n_toplam}" in tum, "kazanan_ozet sayıları metinde yok"
    assert f"{n_toplam} kesitin {n_hayir} tanesinde" in tum, "Tartışma özet cümlesi kazanan_ozet ile uyumsuz"

    print(f"Başlıklar: {len(h1)}, şekil: {n_img}, tablo: {len(doc.tables)}, kaynak: {len(kaynak)}")
    print("RAPOR_KONTROL_TAMAM")


if __name__ == "__main__":
    main()
