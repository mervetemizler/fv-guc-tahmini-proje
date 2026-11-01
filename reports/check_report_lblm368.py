# -*- coding: utf-8 -*-
"""reports/rapor_lblm368.docx yapı, biçim, atıf ve veri-tutarlılık kontrolü.

Çalıştırma: .venv/Scripts/python.exe -I reports/check_report_lblm368.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

from reports import build_report as br  # noqa: E402
from reports.build_report_lblm368 import sayim_cumlesi, yon_cumlesi  # noqa: E402
from src import config  # noqa: E402

BOLUMLER = ("1. GİRİŞ", "2. LİTERATÜR TARAMASI", "3. VERİ SETİ TANIMI", "4. METODOLOJİ",
            "5. KOD UYGULAMASI", "6. SONUÇLAR VE ANALİZ", "7. TARTIŞMA VE SONUÇ", "8. KAYNAKÇA")
ETIKETLER = ("Amaç", "Motivasyon", "Veri Seti Adı", "Kaynak", "Özellikler", "Ön İşleme", "Model Seçimi",
             "Kullanılan Algoritmalar/Çerçeveler", "Hiperparametreler", "Model Mimarisi",
             "Kodun Ana Bölümleri", "Doğruluk ve Kayıp Grafikleri", "Karmaşıklık Matrisi",
             "Örnek Tahminler", "Performans Metrikleri", "Performans Değerlendirmesi",
             "Karşılaşılan Zorluklar", "Bulgularınızı Özetleyin", "Gelecek Çalışmalar")
YASAK = ("başa baş", "değişkenliği arttıkça", "ŞABLONU", "Örnek:", "NOT:", "TODO", "lorem", "Taslak",
         "eklenecek")


def _near(a, b, tol_cm=0.05):
    return abs(a - b) <= Cm(tol_cm)


def main():
    path = config.REPORTS_DIR / "rapor_lblm368.docx"
    assert path.exists(), f"Rapor bulunamadı: {path}"
    doc = Document(str(path))

    sec = doc.sections[0]
    assert _near(sec.page_width, Cm(21.59)) and _near(sec.page_height, Cm(27.94)), "Sayfa Letter değil"
    for nm in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        assert _near(getattr(sec, nm), Cm(2.54)), f"Kenar boşluğu 2,54 cm değil: {nm}"

    normal = doc.styles["Normal"]
    assert normal.font.name == "Times New Roman" and normal.font.size == Pt(12), "Normal stil TNR 12 pt değil"
    runs = [r for p in doc.paragraphs for r in p.runs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    runs.extend(p.runs)
    for r in runs:
        assert r.font.name in (None, "Times New Roman"), f"Yanlış yazı tipi: {r.font.name}"

    body_p = doc.paragraphs
    assert "a:blip" in body_p[0]._p.xml, "İlk paragrafta logo yok"
    assert len(doc.inline_shapes) >= 12, f"Görsel sayısı yetersiz: {len(doc.inline_shapes)}"

    # kapak
    ilk = body_p[:15]
    sira = ["İSTANBUL AREL ÜNİVERSİTESİ", "MÜHENDİSLİK FAKÜLTESİ",
            "LBLM368 - DERİN ÖĞRENME VE SINIFLANDIRMA TEKNİKLERİ", "PROJE RAPORU"]
    idx = []
    for s_ in sira:
        m = [i for i, p in enumerate(ilk) if p.text.strip() == s_]
        assert m, f"Kapak satırı eksik: {s_}"
        p = ilk[m[0]]
        assert p.alignment == WD_ALIGN_PARAGRAPH.CENTER and all(r.bold for r in p.runs if r.text.strip()), \
            f"Kapak satırı ortalı/kalın değil: {s_}"
        idx.append(m[0])
    assert idx == sorted(idx), "Kapak satırları sırasız"
    for s_ in ("Proje Başlığı:", "İsim_Soyisim:", "Öğrenci No:"):
        assert any(p.text.startswith(s_) for p in ilk), f"Kapak alanı eksik: {s_}"

    # bölümler
    pos = []
    for b in BOLUMLER:
        m = [i for i, p in enumerate(body_p) if p.text.strip() == b and p.runs and all(r.bold for r in p.runs)]
        assert len(m) == 1, f"Bölüm başlığı {b!r} {len(m)} kez bulundu"
        pos.append(m[0])
    assert pos == sorted(pos), "Bölüm sırası bozuk"
    i_kay = pos[-1]

    paras = [p.text for p in body_p]
    tum = "\n".join(paras)
    for e in ETIKETLER:
        assert any(t.startswith(f"{e}:") for t in paras), f"Alt etiket eksik: {e}"
    km = next(t for t in paras if t.startswith("Karmaşıklık Matrisi:"))
    assert "sınıflandırma" in km and "regresyon" in km, "Karmaşıklık matrisi uyarlama notu eksik"
    for k in ("RMSE", "MAE", "nRMSE", "R²"):
        assert k in tum, f"Metrik metinde yok: {k}"

    # kaynakça
    kaynak = [t for t in paras[i_kay + 1:] if t.strip()]
    nums = []
    for t in kaynak:
        m = re.match(r"\[(\d+)\]", t)
        assert m, f"Kaynakça kaydı [n] ile başlamıyor: {t[:60]}"
        nums.append(int(m.group(1)))
        assert "doi" in t.lower() or "http" in t, f"Kayıtta DOI/URL yok: {t[:60]}"
    assert 10 <= len(kaynak) <= 13, f"Kaynakça kayıt sayısı: {len(kaynak)}"
    assert sorted(nums) == list(range(1, len(nums) + 1)), f"Numaralar ardışık değil: {nums}"
    assert any("Claude" in t and "Anthropic" in t for t in kaynak), "AI aracı kaynakçada yok"
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

    # veri-türetilmiş hükümler
    facts = br.load_facts()
    kz = pd.read_csv(config.RESULTS_DIR / "metrics" / "kazanan_ozet.csv")
    assert sayim_cumlesi(facts) in tum, "Sayım cümlesi metinde yok"
    assert f"{len(kz)} kesitin {int((kz.dl_baseline_gecti == 'hayır').sum())} tanesinde baseline" in tum
    for tur, ad in (("ufuk", "Ufuk"), ("hava", "Hava sınıfı"), ("saat", "Saat")):
        assert yon_cumlesi(facts, tur, ad) in tum, f"Yön cümlesi metinde yok: {tur}"
    n_gun = int(kz.n_gun_boot.max())
    assert f"{n_gun} gün" in tum, "Test gün sayısı metinde yok"

    low = tum.lower()
    for y in YASAK:
        assert not re.search(r"(?<!\w)" + re.escape(y.lower()) + r"(?!\w)", low), f"Yasak ifade bulundu: {y}"

    assert (config.REPORTS_DIR / "rapor.docx").exists() and (config.REPORTS_DIR / "build_report.py").exists(), \
        "Eski rapor dosyaları eksik"

    print(f"Bölüm: {len(BOLUMLER)}, şekil: {len(doc.inline_shapes) - 1}, tablo: {len(doc.tables)}, "
          f"kaynak: {len(kaynak)}")
    print("RAPOR_LBLM368_KONTROL_TAMAM")


if __name__ == "__main__":
    main()
