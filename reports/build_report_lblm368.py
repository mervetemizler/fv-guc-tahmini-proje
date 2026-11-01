# -*- coding: utf-8 -*-
"""LBLM368 proje rapor şablonuna göre rapor üretici (python-docx).

Taban belge reports/sablon/LBLM368_Proje_Rapor_Sablonu.docx dosyasıdır: logo paragrafı
ve sayfa düzeni (Letter, 2,54 cm kenar boşluğu) korunur, kalan gövde yeniden yazılır.
Tüm sonuç sayıları ve yön/hüküm cümleleri results/ altındaki dosyalardan türetilir.

Çalıştırma: .venv/Scripts/python.exe -I reports/build_report_lblm368.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

from reports import build_report as br  # noqa: E402
from src import analysis, compare, config  # noqa: E402

fmt_tr = br.fmt_tr
lab, kz, kz_cumle, ga = br.lab, br.kz, br.kz_cumle, br.ga
KARAR_TR, HORIZON_LABEL = br.KARAR_TR, br.HORIZON_LABEL

TEMPLATE = ROOT / "reports" / "sablon" / "LBLM368_Proje_Rapor_Sablonu.docx"
FONT = "Times New Roman"
FIG_W = Cm(14)

REFS = {
    **br.REFS,
    "claude": "Anthropic, \"Claude (Claude Code) yapay zekâ asistanı,\" projede kod geliştirme, analiz ve "
              "rapor/sunum hazırlığında kullanılan AI aracı, 2026. [Çevrimiçi]. "
              "Erişilebilir: https://www.anthropic.com/claude-code",
}
REF_KEYS: dict = {}
COUNTER = {"tablo": 0, "sekil": 0}


# --------------------------------------------------------------------------
# Veriden türetilen yön/hüküm cümlesi (elle yazılmış eğilim cümlesi YOKTUR)
# --------------------------------------------------------------------------
def yon_cumlesi(f, tur: str, ad: str) -> str:
    d = f["kazanan"]
    d = d[d.kesit_turu == tur]
    if len(d) == 0:
        raise ValueError(f"kazanan_ozet.csv'de {tur} kesiti yok")

    def adlar(karar):
        s = [str(k).split(" (")[0] for k in d[d.dl_baseline_gecti == karar].kesit]
        return ", ".join(s) if s else "yok"

    return (f"{ad} kesitlerinde derin öğrenmenin anlamlı biçimde önde olduğu: {adlar('evet')}; "
            f"fark ayırt edilemeyen (belirsiz): {adlar('belirsiz')}; "
            f"baseline'ın anlamlı biçimde önde olduğu: {adlar('hayır')}.")


def sayim_cumlesi(f) -> str:
    return (f"{f['n_toplam']} kesitin {f['n_hayir']} tanesinde baseline anlamlı biçimde önde, "
            f"{f['n_belirsiz']} tanesinde fark ayırt edilemedi (belirsiz), "
            f"{f['n_evet']} tanesinde derin öğrenme anlamlı biçimde önde.")


# --------------------------------------------------------------------------
# Taban belge ve stiller
# --------------------------------------------------------------------------
def base_document() -> Document:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Şablon bulunamadı: {TEMPLATE}")
    doc = Document(str(TEMPLATE))
    body = doc.element.body
    kids = list(body)
    first = kids[0]
    if first.tag != qn("w:p") or not first.findall(".//" + qn("a:blip")):
        raise ValueError("Şablonun ilk paragrafı logo içermiyor")
    for k in kids[1:]:
        if k.tag == qn("w:sectPr"):
            continue
        body.remove(k)
    return doc


def _font_all(style, size=None):
    style.font.name = FONT
    if size is not None:
        style.font.size = Pt(size)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(a)) is not None:
            del rfonts.attrib[qn(a)]
    return rpr


def set_styles(doc: Document) -> None:
    rpr = _font_all(doc.styles["Normal"], 12)
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), "tr-TR")
    rpr.append(lang)
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    cap = doc.styles["Caption"]
    _font_all(cap, 10)
    cap.font.color.rgb = RGBColor(0, 0, 0)
    cap.font.italic = False
    cap.font.bold = False
    _font_all(doc.styles["List Bullet"])
    doc.core_properties.title = "FV Güneş Santrali Çok Değişkenli Güç Üretim Tahmini"
    doc.core_properties.author = "LBLM368 Proje Raporu"


# --------------------------------------------------------------------------
# Yerel yardımcılar
# --------------------------------------------------------------------------
def para(doc, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    p.add_run(text)
    p.alignment = align
    return p


def etiket(doc, label: str, text: str = ""):
    p = doc.add_paragraph()
    r = p.add_run(f"{label}: ")
    r.bold = True
    if text:
        p.add_run(text)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def baslik(doc, text: str):
    doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(12)
    return p


def madde(doc, text: str):
    p = doc.add_paragraph("• " + text)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def cite(key: str) -> str:
    if key not in REFS:
        raise KeyError(f"Bilinmeyen kaynak anahtarı: {key}")
    if key not in REF_KEYS:
        REF_KEYS[key] = len(REF_KEYS) + 1
    return f"[{REF_KEYS[key]}]"


def caption(doc, text):
    p = doc.add_paragraph(text, style="Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def _add_pic(doc, path: Path, text: str) -> int:
    if not path.exists():
        raise FileNotFoundError(f"Gerekli şekil bulunamadı: {path}")
    doc.add_picture(str(path), width=FIG_W)
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    COUNTER["sekil"] += 1
    caption(doc, f"Şekil {COUNTER['sekil']}: {text}")
    return COUNTER["sekil"]


def fig(doc, key: str, text: str) -> int:
    return _add_pic(doc, config.FIGURES_DIR / analysis.FIGURES[key], text)


def eda_fig(doc, name: str, text: str) -> int:
    return _add_pic(doc, config.FIGURES_DIR / name, text)


def tablo(doc, text: str, header, rows) -> int:
    COUNTER["tablo"] += 1
    n = COUNTER["tablo"]
    caption(doc, f"Tablo {n}: {text}")
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
    size = Pt(9 if len(header) >= 5 else 10)
    for ri, row in enumerate(t.rows):
        for c in row.cells:
            for pp in c.paragraphs:
                pp.paragraph_format.space_after = Pt(0)
                for rr in pp.runs:
                    rr.font.size = size
                    if ri == 0:
                        rr.bold = True
    doc.add_paragraph()
    return n


# --------------------------------------------------------------------------
# Kapak
# --------------------------------------------------------------------------
def add_kapak(doc):
    doc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for text, size in (("İSTANBUL AREL ÜNİVERSİTESİ", 14), ("MÜHENDİSLİK FAKÜLTESİ", 14),
                       ("LBLM368 - DERİN ÖĞRENME VE SINIFLANDIRMA TEKNİKLERİ", 14),
                       ("PROJE RAPORU", 16)):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(size)
    doc.add_paragraph()
    doc.add_paragraph()
    for lab_, val in (("Proje Başlığı", "FV Güneş Santrali Çok Değişkenli Güç Üretim Tahmini: LSTM ve "
                                        "CNN-LSTM ile Gerçek Ölçüm Verisi Üzerinde Kısa Vadeli Tahmin"),
                      ("İsim_Soyisim", "[Ad Soyad]"), ("Öğrenci No", "[Öğrenci No]")):
        p = doc.add_paragraph()
        p.add_run(f"{lab_}: ").bold = True
        p.add_run(val)
    doc.add_paragraph("Tarih: Kasım 2026")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# --------------------------------------------------------------------------
# Bölümler 1-5
# --------------------------------------------------------------------------
def section_1_giris(doc):
    baslik(doc, "1. GİRİŞ")
    etiket(doc, "Amaç",
           f"Bu çalışmanın amacı, gerçek bir fotovoltaik (FV) sistemden alınmış çok değişkenli ölçüm "
           f"verisi (AC güç, eğimli yüzey ışınımı, ortam sıcaklığı, modül sıcaklığı ve zaman öznitelikleri) "
           f"kullanarak geleceğe yönelik güç üretimini tahmin etmektir. Tahmin ufku {config.HORIZON} "
           f"adımdır (15 dakikalık adımlarla 4 saate kadar); ana değerlendirme ufku +1 saattir "
           f"({config.MAIN_HORIZON_STEPS} adım ilerisi). Problem bir ileri tahmin (forecasting) "
           f"problemidir; anlık durumu kestiren nowcasting değildir ve gelecekteki ışınım değerleri "
           f"girdi olarak kullanılmaz.")
    etiket(doc, "Motivasyon",
           "FV üretimi ışınım, bulutluluk ve sıcaklığa bağlı olarak saatler içinde büyük ölçüde "
           "dalgalanır; bu değişkenlik şebekeye güvenli entegrasyonu, dengeleme kapasitesinin "
           "planlanmasını ve piyasa katılımını zorlaştırır. Kısa vadeli güç tahmini bu nedenle "
           "işletme için temel bir ihtiyaçtır. Çalışmada yalnızca gerçek ve açık erişimli ölçüm "
           "verisi kullanılmış, sentetik veri üretilmemiştir. Katkılar: (i) gerçek veri üzerinde "
           "uçtan uca, tekrar üretilebilir ve sızıntısız bir veri hazırlama ve değerlendirme hattı; "
           "(ii) basit referans yöntemler ve klasik makine öğrenmesi baseline'ları ile LSTM ve "
           "CNN-LSTM modellerinin aynı protokolle adil karşılaştırması; (iii) belgelenmiş ve sabit "
           "rastgele tohumlarla yeniden çalıştırılabilir kod tabanı.")


def section_2_literatur(doc):
    baslik(doc, "2. LİTERATÜR TARAMASI")
    para(doc, "Aşağıda, bu çalışmanın dayandığı başlıca literatür özetlenmiştir.")
    madde(doc, "FV güç tahmini yaklaşımları genel olarak fiziksel, istatistiksel ve makine öğrenmesi "
               f"tabanlı yöntemler olarak sınıflandırılır; kapsamlı bir derleme {cite('antonanzas')} "
               "yöntemleri ve kullanılan girdi türlerini karşılaştırır.")
    madde(doc, f"Yenilenebilir enerji tahminine yönelik derin öğrenme yaklaşımları ayrı bir derlemede "
               f"ele alınmıştır {cite('wang')}.")
    madde(doc, f"Uzun kısa süreli bellek (LSTM) ağları {cite('hochreiter')} kapı mekanizmaları sayesinde "
               f"uzun bağımlılıkları öğrenebilir; FV güç tahmininde LSTM tabanlı modeller "
               f"önerilmiştir {cite('abdel')}.")
    madde(doc, f"Ağaç tabanlı topluluk yöntemlerinden XGBoost {cite('chen')}, gecikmeli özniteliklerle "
               f"güçlü ve hızlı bir klasik baseline sunar.")
    madde(doc, f"Hibrit CNN-LSTM yaklaşımında evrişimli katmanlar yerel örüntüleri çıkarır, LSTM katmanı "
               f"zamansal bağımlılığı modeller; yaklaşım konutlarda enerji tüketimi tahmininde "
               f"kullanılmıştır {cite('kimcho')}.")
    madde(doc, "Çok kısa ufuklarda son ölçümün tekrarına dayanan persistence yöntemi güçlü bir referanstır; "
               "bu nedenle derin öğrenme modellerinin değeri yalnızca persistence ve mevsimsel "
               "persistence'a karşı değil, tablo tabanlı klasik yöntemlere karşı da sınanmalıdır.")


def section_3_veri(doc, f):
    s, y, w, c = f["system"], f["years"], f["windows"], f["cleaning"]
    baslik(doc, "3. VERİ SETİ TANIMI")
    etiket(doc, "Veri Seti Adı",
           f"NREL PVDAQ (Photovoltaic Data Acquisition) açık veri koleksiyonunun {s['system_id']} numaralı "
           f"sistemi ({s['name']}).")
    etiket(doc, "Kaynak",
           f"ABD Ulusal Yenilenebilir Enerji Laboratuvarı (NREL) tarafından yayımlanan veri OEDI veri "
           f"gölünden anonim olarak {s['accessed_on']} tarihinde indirilmiştir. Veri seti "
           f"{cite('deline')} ve sistem metadata kaydı {cite('meta')} kaynakçada verilmiştir "
           f"(veri seti DOI: https://doi.org/10.25984/1846021). Veri gerçek ölçümdür; simülasyon "
           f"değildir. Lisans için gönderi sayfasında ayrı bir ad doğrulanamamış; OpenEI genel koşulu "
           f"(CC BY 4.0 benzeri) atıf şartıyla varsayılmıştır.")
    tr, va, te = w["train"], w["val"], w["test"]
    etiket(doc, "Özellikler",
           f"Sistem {s['site_location']} konumunda (enlem {fmt_tr(s['latitude'], 4)}, boylam "
           f"{fmt_tr(s['longitude'], 4)}, rakım {fmt_tr(s['elevation_m'], 1)} m) yer alan, "
           f"{fmt_tr(s['tilt_deg'])}° eğimli ve {fmt_tr(s['azimuth_deg'])}° azimutlu sabit bir "
           f"sistemdir; kurulu DC kapasitesi {fmt_tr(s['capacity_kw'], 1)} kW'tır. Veri 15 dakika "
           f"çözünürlüktedir. Girdi kanalları ({len(config.INPUT_FEATURES)} adet): "
           f"{', '.join(config.INPUT_FEATURES)}; hedef değişken AC güçtür. Bölme başına pencere "
           f"sayıları Tablo {COUNTER['tablo'] + 1}'de, test pencerelerinin mevsimlere dağılımı "
           f"Tablo {COUNTER['tablo'] + 2}'de verilmiştir.")
    tablo(doc, "Bölme başına pencere sayıları", ["Küme", "Pencere sayısı", "Segment sayısı"],
          [["Eğitim", fmt_tr(tr["n_windows"]), len(tr["per_segment"])],
           ["Doğrulama", fmt_tr(va["n_windows"]), len(va["per_segment"])],
           ["Test", fmt_tr(te["n_windows"]), len(te["per_segment"])]])
    tablo(doc, "Test pencerelerinin mevsimlere dağılımı", ["Mevsim", "Test pencere sayısı"],
          [[k, fmt_tr(v)] for k, v in te["season_counts"].items()])
    etiket(doc, "Ön İşleme")
    yrs = " ve ".join(str(v) for v in y["years"])
    days = " + ".join(str(y["days"][str(v)]) for v in y["years"])
    madde(doc, f"Gerekli kanalları (AC güç, POA ışınımı, ortam ve modül sıcaklığı) içeren ardışık yıl "
               f"çiftleri arasından {yrs} yılları seçilmiştir ({days} gün; 1 dakikalık ham çözünürlük).")
    madde(doc, "Ham veride eksik ölçümler -7999 değeriyle işaretlidir; bu değerler NaN'a çevrilmiştir.")
    madde(doc, f"Veri 15 dakikalık ızgaraya yeniden örneklenmiş, gece ölçüm ofsetinden kaynaklanan negatif "
               f"ışınım değerleri sıfıra kırpılmış ve fiziksel olarak imkânsız uç değerler "
               f"temizlenmiştir. Temizlik sonrası ızgara {fmt_tr(c['n_rows'])} satır içerir "
               f"({c['start']} – {c['end']}).")
    madde(doc, f"Veri bitiş tarihi: {config.DATA_END_REASON}")
    madde(doc, config.SPLIT_RATIONALE)
    madde(doc, f"Girdi penceresi {config.WINDOW} adım (24 saat), çıktı {config.HORIZON} adımdır. Eğitim ve "
               f"doğrulama kümelerinde tamamen gece olan pencereler çıkarılmıştır (eğitim: "
               f"{fmt_tr(tr['dropped_all_night'])}, doğrulama: {fmt_tr(va['dropped_all_night'])}); test "
               f"kümesinde {fmt_tr(te['all_night_windows_kept'])} tamamen gece penceresi korunmuştur ve "
               f"değerlendirmede gündüz maskesi kullanılır.")
    madde(doc, "Girdi ölçekleyicisi yalnızca eğitim kümesine fit edilir; doğrulama ve test bilgisi "
               "eğitime sızmaz.")
    n1 = eda_fig(doc, "eda_01_zaman_serisi.png", "Güç ve ışınım zaman serisi (EDA)")
    para(doc, f"Şekil {n1}, temizlenmiş güç ve ışınım serisinin iki yıllık seyrini göstermektedir; "
              f"mevsimsel döngü ve günlük salınım görülmektedir.")
    n2 = eda_fig(doc, "eda_03_gunluk_profil.png", "Ortalama günlük güç ve ışınım profili")
    n3 = eda_fig(doc, "eda_05_korelasyon.png", "Değişkenler arası korelasyon matrisi")
    para(doc, f"Şekil {n2} ortalama günlük profili, Şekil {n3} değişkenler arasındaki korelasyonları "
              f"göstermektedir.")
    n4 = eda_fig(doc, "eda_09_bulutlu_acik_gun.png", "Açık ve bulutlu gün karşılaştırması")
    para(doc, f"Şekil {n4}, aynı mevsimde açık ve bulutlu bir günün güç profilini karşılaştırarak hava "
              f"koşulunun üretim üzerindeki etkisini göstermektedir.")


def section_4_metodoloji(doc, f):
    p = f["params"]
    baslik(doc, "4. METODOLOJİ")
    para(doc, "Yaklaşım adım adım şöyledir: gerçek ölçümler temizlenip 15 dakikalık ızgaraya getirilir; "
              "zamansal olarak ardışık eğitim/doğrulama/test kümelerine bölünür; dört baseline ve iki "
              "derin öğrenme modeli aynı pencerelerle eğitilir; hepsi tek bir değerlendirme işleviyle "
              "ve gün-bloklu bootstrap ile karşılaştırılır.")
    nf = f["n_tab_features"]
    nf_txt = f"{nf}" if nf else "tablo biçiminde"
    bi = f["baselines_info"] or {}
    xgb_strategy = (bi.get("xgboost") or {}).get("strategy", "multi_output_tree")
    etiket(doc, "Model Seçimi",
           f"Dört baseline kullanılmıştır: (i) persistence (son ölçümün tekrarı), (ii) mevsimsel "
           f"persistence ({config.STEPS_PER_DAY} adım, yani bir önceki günün aynı saati), (iii) Doğrusal "
           f"Regresyon ve (iv) XGBoost. Son ikisi gecikmeli ölçümler ve zaman özniteliklerinden oluşan "
           f"{nf_txt} öznitelikli tablo gösterimiyle çalışır ve 16 ufku çok çıktılı olarak tahmin eder "
           f"(XGBoost için {xgb_strategy}). Derin öğrenme tarafında dizi verisine uygun olduğu için LSTM "
           f"ve evrişimli özellik çıkarımını LSTM ile birleştiren CNN-LSTM seçilmiştir.")
    etiket(doc, "Kullanılan Algoritmalar/Çerçeveler",
           f"Modeller PyTorch {cite('paszke')} ile tek GPU'da (RTX 3060) Adam optimizasyonuyla "
           f"{cite('kingma')} eğitilir; baseline'lar için scikit-learn, XGBoost ve pandas kullanılmıştır.")
    etiket(doc, "Hiperparametreler",
           f"Öğrenme oranı {config.LR}, ağırlık sönümü {config.WEIGHT_DECAY}, toplu boyut "
           f"{config.BATCH_SIZE}, en fazla {config.MAX_EPOCHS} dönem, {config.EARLY_STOP_PATIENCE} "
           f"dönemlik erken durdurma sabrı, doğrulama kaybı {config.LR_PATIENCE} dönem iyileşmediğinde "
           f"öğrenme oranı düşürme (ReduceLROnPlateau), gradyan normu kırpma {config.GRAD_CLIP}, dropout "
           f"{fmt_tr(config.DROPOUT, 1)}. Her model {len(config.SEEDS)} farklı rastgele tohumla "
           f"({', '.join(str(x) for x in config.SEEDS)}) eğitilir; sonuçlar ortalama ± standart sapma "
           f"olarak raporlanır. Hiperparametre araması yapılmamıştır.")
    etiket(doc, "Model Mimarisi",
           f"LSTM modeli iki katmanlı bir LSTM ve son gizli durumdan tam bağlantılı çıkış katmanından "
           f"oluşur. CNN-LSTM modeli iki Conv1d+ReLU bloğu, ardından tek katmanlı LSTM ve tam bağlantılı "
           f"çıkış katmanı içerir (Tablo {COUNTER['tablo'] + 1}).")
    tablo(doc, "Derin öğrenme mimarileri", ["Model", "Katmanlar", "Eğitilebilir parametre"],
          [["LSTM", f"LSTM({config.LSTM_HIDDEN}) x {config.LSTM_LAYERS}, dropout {fmt_tr(config.DROPOUT, 1)}, "
                    f"Linear({config.HORIZON})", fmt_tr(p["lstm"])],
           ["CNN-LSTM", f"Conv1d({config.CNN_CHANNELS[0]}, k={config.CNN_KERNEL}) -> "
                        f"Conv1d({config.CNN_CHANNELS[1]}, k={config.CNN_KERNEL}) -> LSTM({config.LSTM_HIDDEN}) "
                        f"-> Linear({config.HORIZON})", fmt_tr(p["cnn_lstm"])]])
    para(doc, f"Değerlendirme protokolü: tüm modeller tek bir evaluate() işleviyle aynı test pencereleri "
              f"üzerinde değerlendirilir. Gece örnekleri kuralla sıfır güç kabul edilir; birincil metrikler "
              f"yalnızca gündüz hücrelerinden hesaplanır. Metrikler MAE, RMSE, R² ve nRMSE'dir; nRMSE "
              f"paydası kurulu kapasitedir ({fmt_tr(config.CAPACITY_W)} W). 16 ufuk ortalaması "
              f"havuzlanmış hücrelerden hesaplanır; +1 saatlik ufuk ayrıca raporlanır. Modeller arasındaki "
              f"farkların anlamlılığı gün-bloklu bootstrap ile sınanır (test günleri blok olarak yerine "
              f"koymalı yeniden örneklenir, B = {fmt_tr(compare.B)}). Karar kuralı: %95 güven aralığı (GA) "
              f"sıfırı içeriyorsa karar \"belirsiz\" olur; belirsiz, farkın ayırt edilemediği anlamına "
              f"gelir ve eşitlik anlamına gelmez. Erken durdurma doğrulamadan gelir; hiperparametreler "
              f"test kümesi üzerinde ayarlanmamıştır.")


def section_5_kod(doc):
    baslik(doc, "5. KOD UYGULAMASI")
    para(doc, "Kod tabanı src/ altında modüler Python paketi ve notebooks/ altında beş not defterinden "
              "(01_eda ... 05_karsilastirma) oluşur. Tüm hat tek komutla (src/run_all.py) yeniden "
              "çalıştırılabilir; bağımlılıklar requirements.txt içinde sabitlenmiş, rastgele tohumlar "
              "sabittir.")
    etiket(doc, "Kodun Ana Bölümleri")
    madde(doc, "Veri yükleme ve ön işleme: src/download_pvdaq.py (indirme), build_raw_parquet.py, "
               "data.py (temizlik), features.py (öznitelikler) ve windows.py (pencereleme ve bölme).")
    madde(doc, "Model tanımlama: src/models.py içindeki build_model ile LSTM ve CNN-LSTM, src/baselines.py "
               "içinde dört baseline. PyTorch'ta Keras tarzı bir compile adımı yoktur; kayıp işlevi ve "
               "optimizasyon düzeneği src/train.py içinde kurulur.")
    madde(doc, "Model eğitimi ve değerlendirme: src/train.py (train_one), evaluate.py, compare.py "
               "(bootstrap), weather.py (hava sınıfı analizi) ve ablation.py (öznitelik ablasyonu).")
    madde(doc, "Sonuçların görselleştirilmesi: src/figures.py ve analysis.py; çıktılar results/figures "
               "altına yazılır.")
    para(doc, f"Kod geliştirme, analiz ve rapor hazırlığında Claude Code yapay zekâ asistanından "
              f"yararlanılmıştır {cite('claude')}. Rapordaki tüm sonuçlar kodun çalıştırılmasıyla "
              f"üretilmiş ölçümlerdir.")


# --------------------------------------------------------------------------
# Bölümler 6-8
# --------------------------------------------------------------------------
def section_6_sonuclar(doc, f):
    s, u, kz_df = f["summary"], f["ufuk"], f["kazanan"]
    n_gun = int(kz_df.n_gun_boot.max())
    hs = br._hist(f)
    baslik(doc, "6. SONUÇLAR VE ANALİZ")
    para(doc, f"Tüm modeller aynı {n_gun} günlük test döneminde, yalnızca gündüz hücreleri üzerinde "
              f"değerlendirilmiştir; derin öğrenme modelleri için {len(config.SEEDS)} tohumun ortalaması ± "
              f"standart sapması verilir, baseline'lar tek koşuludur.")
    # --- kayıp
    ep = []
    for m in ("lstm", "cnn_lstm"):
        h = hs[m]
        be = sum(x["best_epoch"] for x in h) / len(h)
        sec = sum(x["total_sec"] for x in h) / len(h)
        ep.append(f"{lab(m)} için ortalama en iyi dönem {fmt_tr(be, 1)} ve tohum başına ortalama eğitim "
                  f"süresi {fmt_tr(sec, 0)} saniyedir")
    etiket(doc, "Doğruluk ve Kayıp Grafikleri",
           "Bu çalışma regresyon problemi olduğundan doğruluk (accuracy) eğrisi yoktur; bunun yerine "
           "eğitim ve doğrulama kaybı (MSE) izlenmiştir. " + "; ".join(ep) + ".")
    n = fig(doc, "kayip", "Eğitim ve doğrulama kayıp eğrileri")
    para(doc, f"Şekil {n}, her model ve tohum için eğitim ve doğrulama kayıplarını göstermektedir.")
    # --- örnek tahminler
    etiket(doc, "Örnek Tahminler",
           "Aşağıdaki şekil, test döneminden seçilmiş günler için gerçek güç ile model tahminlerini "
           "karşılaştırır.")
    fig(doc, "tahmin", "Test döneminden örnek günlerde tahmin ve gerçek güç")
    # --- performans metrikleri
    etiket(doc, "Performans Metrikleri",
           "Sınıflandırma metrikleri (Accuracy, Precision, Recall, F1) bu problemde tanımlı olmadığından "
           "regresyon metrikleri kullanılmıştır:")
    madde(doc, "MAE: ortalama mutlak hata (W).")
    madde(doc, "RMSE: hataların karesel ortalamasının karekökü (W); büyük hataları daha çok cezalandırır.")
    madde(doc, f"nRMSE: RMSE / kurulu kapasite ({fmt_tr(config.CAPACITY_W)} W).")
    madde(doc, "R²: belirlilik katsayısı; açıklanan varyans oranı.")
    d = s[(s["mask"] == "day") & (s.scope == "mean16")].copy()
    order = ["persistence", "seasonal_persistence", "linreg", "xgboost", "lstm", "cnn_lstm"]
    d = d.set_index("model").loc[order]
    rows = []
    for m, r in d.iterrows():
        rm = fmt_tr(r.RMSE_W_mean, 1) + (f" ± {fmt_tr(r.RMSE_W_std, 1)}" if r.n_runs > 1 else " (tek koşu)")
        rows.append([lab(m), rm, fmt_tr(r.MAE_W_mean, 1), fmt_tr(r.nRMSE_mean * 100, 1) + " %",
                     fmt_tr(r.R2_mean, 2)])
    best = d.RMSE_W_mean.idxmin()
    para(doc, f"Tablo {COUNTER['tablo'] + 1}, 16 ufkun ortalaması için gündüz metriklerini vermektedir. "
              f"Nokta tahminde en düşük ortalama RMSE {lab(best)} modelindedir "
              f"({fmt_tr(d.loc[best, 'RMSE_W_mean'], 1)} W); LSTM {fmt_tr(d.loc['lstm', 'RMSE_W_mean'], 1)} W, "
              f"CNN-LSTM {fmt_tr(d.loc['cnn_lstm', 'RMSE_W_mean'], 1)} W ve XGBoost "
              f"{fmt_tr(d.loc['xgboost', 'RMSE_W_mean'], 1)} W değerlerine ulaşmıştır; persistence "
              f"{fmt_tr(d.loc['persistence', 'RMSE_W_mean'], 1)} W ile en yüksek hatayı verenlerdendir.")
    tablo(doc, "Model karşılaştırması (gündüz, 16 ufuk ortalaması)",
          ["Model", "RMSE (W)", "MAE (W)", "nRMSE", "R²"], rows)
    fig(doc, "karsilastirma", "Modellerin RMSE karşılaştırması")
    # ufuk
    urows = []
    for h, lbl in HORIZON_LABEL.items():
        r = u[u.horizon_min == h * 15].iloc[0]
        urows.append([lbl] + [fmt_tr(r[f"{m}_RMSE_W"], 1) for m in order])
    tablo(doc, "Ufuğa göre gündüz RMSE (W)", ["Ufuk"] + [lab(m) for m in order], urows)
    cum = "; ".join(f"{HORIZON_LABEL[h]}: {kz_cumle(kz(f, 'ufuk', HORIZON_LABEL[h]))}" for h in HORIZON_LABEL)
    para(doc, f"Ufuk bazlı kararlar: {cum}. {yon_cumlesi(f, 'ufuk', 'Ufuk')}")
    fig(doc, "ufuk", "Tahmin ufkuna göre RMSE")
    b = f["boot"]
    lc = b[(b.model_a == "lstm") & (b.model_b == "cnn_lstm") & (b.kapsam == "mean16")].iloc[0]
    lc4 = b[(b.model_a == "lstm") & (b.model_b == "cnn_lstm") & (b.kapsam == "h4")].iloc[0]
    para(doc, f"İki derin öğrenme mimarisi arasındaki fark (LSTM - CNN-LSTM) 16 ufuk ortalamasında "
              f"{fmt_tr(lc.fark_W, 1)} W, %95 GA {ga(lc.ci_low, lc.ci_high)} ile "
              f"{'anlamlıdır' if lc.anlamli else 'anlamlı değildir'}; +1 saatte {fmt_tr(lc4.fark_W, 1)} W, "
              f"GA {ga(lc4.ci_low, lc4.ci_high)} ile {'anlamlıdır' if lc4.anlamli else 'anlamlı değildir'} "
              f"(negatif fark LSTM'in daha iyi olduğunu gösterir).")
    # --- karmaşıklık matrisi karşılığı
    etiket(doc, "Karmaşıklık Matrisi",
           "Karmaşıklık matrisi sınıflandırma problemlerine özgüdür; bu çalışma sürekli güç değeri "
           "tahmin eden bir regresyon problemidir. Karşılığı olarak hatanın koşullara göre "
           "ayrıştırılması (günün saati, hava sınıfı, öznitelik grubu) ve kesit bazlı karar tablosu "
           "verilmiştir.")
    sa = kz_df[kz_df.kesit_turu == "saat"]
    zr = sa.loc[sa.baseline_RMSE_W.idxmax()]
    para(doc, f"Günün saatine göre: en yüksek baseline hatası {zr.kesit} saatindedir "
              f"({fmt_tr(zr.baseline_RMSE_W, 1)} W). {yon_cumlesi(f, 'saat', 'Saat')}")
    fig(doc, "saat", "Günün saatine göre RMSE")
    hv = f["hava"]
    hv = hv[hv.scope == "mean16"].groupby(["model", "sinif", "sinif_ad", "n_gun"], as_index=False).RMSE_W.mean()
    hrows = []
    for sid, nm in enumerate(["Kapalı", "Parçalı", "Açık"]):
        g = hv[hv.sinif == sid]
        ng = int(g.n_gun.iloc[0])
        hrows.append([f"{nm} ({ng} gün)"] + [fmt_tr(g[g.model == m].RMSE_W.iloc[0], 1) for m in order])
    tablo(doc, "Hava sınıfına göre gündüz RMSE (W, 16 ufuk ortalaması)",
          ["Sınıf"] + [lab(m) for m in order], hrows)
    hg = f["hava_gun"]
    cnt = hg.sinif_ad.value_counts()
    ka, kp, kk = (kz(f, "hava", x) for x in ("Açık", "Parçalı", "Kapalı"))
    if kk.fark_W > 0:
        yon_k = f"nokta tahmin {lab(kk.en_iyi_baseline)} lehine {fmt_tr(kk.fark_W, 1)} W"
    else:
        yon_k = f"nokta tahmin {lab(kk.en_iyi_dl)} lehine {fmt_tr(-kk.fark_W, 1)} W"
    n_kk = int(kk.n_gun_boot)
    para(doc, f"Günler açıklık indeksine (KT) göre sınıflanmıştır; tüm dönemde {int(cnt.get('Açık', 0))} açık, "
              f"{int(cnt.get('Parçalı', 0))} parçalı ve {int(cnt.get('Kapalı', 0))} kapalı gün vardır. "
              f"Açık günlerde {kz_cumle(ka)}. Parçalı günlerde {kz_cumle(kp)}. Kapalı günlerde "
              f"{kz_cumle(kk)}; {yon_k}, ancak sınıf test döneminde yalnızca {n_kk} güne dayandığından "
              f"güven aralığı geniştir ve sıralama kesin kabul edilmemelidir. "
              f"{yon_cumlesi(f, 'hava', 'Hava sınıfı')}")
    fig(doc, "hava", "Hava koşulu sınıflarına göre RMSE")
    # ablasyon
    ab = f["ablasyon"]
    ab = ab[(ab["mask"] == "day") & (ab.scope == "mean16")]
    arows = []
    for m in ("lstm", "cnn_lstm", "xgboost", "linreg"):
        g = ab[ab.model == m].set_index("grup")
        row = [lab(m)]
        for gname in ("A_guc", "B_zaman", "C_isinim", "D_tam"):
            v = g.loc[gname]
            cell = fmt_tr(v.RMSE_W_mean, 1)
            if gname != "A_guc":
                cell += f" ({'+' if v.katki_W > 0 else ''}{fmt_tr(v.katki_W, 1)})"
            row.append(cell)
        arows.append(row)
    cg = ab[ab.grup == "C_isinim"].set_index("model").katki_W
    para(doc, "Ablasyonda girdi grupları kümülatif olarak eklenmiştir: A yalnızca güç, B + zaman "
              "öznitelikleri, C + ışınım, D + sıcaklıklar (tam küme). Parantez içindeki değer bir önceki "
              f"gruba göre RMSE değişimidir (negatif iyileşme). Işınım grubunun katkısı LSTM'de "
              f"{fmt_tr(cg['lstm'], 1)} W, CNN-LSTM'de {fmt_tr(cg['cnn_lstm'], 1)} W'tır. Katkılar "
              f"kümülatif ve tek sırada ölçüldüğünden bireysel etki olarak yorumlanmamalıdır. "
              f"{yon_cumlesi(f, 'ablasyon', 'Ablasyon grubu')}")
    tablo(doc, "Ablasyon: gündüz RMSE (W, 16 ufuk ortalaması) ve önceki gruba göre değişim",
          ["Model", "A: güç", "B: + zaman", "C: + ışınım", "D: tam"], arows)
    fig(doc, "ablasyon", "Öznitelik ablasyonu")
    # kesit bazlı karar tablosu
    dtam = kz(f, "ablasyon", "D_tam")
    uo = kz(f, "ufuk_ort", "16")
    if dtam.dl_baseline_gecti != uo.dl_baseline_gecti:
        raise ValueError("D_tam ve 16-ufuk ortalaması kararları eşit değil")
    krows = []
    for _, r in kz_df.iterrows():
        ci = "= 16-ufuk ort." if (r.kesit_turu == "ablasyon" and r.kesit == "D_tam") else ga(r.ci_low, r.ci_high)
        krows.append([f"{r.kesit_turu}: {r.kesit}", lab(r.en_iyi_baseline), fmt_tr(r.baseline_RMSE_W, 1),
                      lab(r.en_iyi_dl), fmt_tr(r.dl_RMSE_W, 1), fmt_tr(r.fark_W, 1), ci,
                      KARAR_TR[r.dl_baseline_gecti]])
    para(doc, f"Tablo {COUNTER['tablo'] + 1}, tüm kesitler için en iyi baseline ile en iyi derin öğrenme "
              f"modelini karşılaştırır (fark pozitifse baseline daha iyidir). Ablasyon D_tam satırı "
              f"16-ufuk ortalaması ile aynı karşılaştırmadır. {sayim_cumlesi(f)}")
    tablo(doc, "Kesit bazında en iyi baseline ve en iyi DL (RMSE, W)",
          ["Kesit", "Baseline", "RMSE", "DL", "RMSE", "Fark", "%95 GA", "Karar"], krows)


def _kesit_listesi(df):
    return "; ".join(f"{r.kesit_turu} {r.kesit}" for _, r in df.iterrows()) or "yok"


def section_7_tartisma(doc, f):
    kz_df = f["kazanan"]
    n_gun = int(kz_df.n_gun_boot.max())
    baslik(doc, "7. TARTIŞMA VE SONUÇ")
    etiket(doc, "Performans Değerlendirmesi")
    if f["n_evet"] == 0:
        karsilandi = "karşılanmamıştır"
    elif f["n_evet"] < f["n_toplam"] / 2:
        karsilandi = "yalnızca sınırlı sayıda kesitte karşılanmıştır"
    else:
        karsilandi = "büyük ölçüde karşılanmıştır"
    madde(doc, f"Derin öğrenme modellerinin baseline'ları açıkça geçmesi beklentisi {karsilandi}: "
               f"{sayim_cumlesi(f)} Belirsiz kararı, {n_gun} günlük tek bir test döneminde farkın ayırt "
               f"edilemediği anlamına gelir; eşitlik anlamına gelmez.")
    madde(doc, f"16 ufuk ortalamasında {kz_cumle(kz(f, 'ufuk_ort', '16'))}.")
    h = kz_df[kz_df.dl_baseline_gecti == "hayır"]
    e = kz_df[kz_df.dl_baseline_gecti == "evet"]
    madde(doc, f"Baseline'ın anlamlı biçimde önde olduğu kesitler: {_kesit_listesi(h)}.")
    madde(doc, f"Derin öğrenmenin anlamlı biçimde önde olduğu kesitler: {_kesit_listesi(e)}.")
    etiket(doc, "Karşılaşılan Zorluklar")
    madde(doc, "Python 3.14 ve Windows üzerinde GPU destekli PyTorch kurulumu: CUDA 13.2 (cu132) indeksinden "
               "sanal ortamda kurulmuş ve GPU duman testiyle doğrulanmıştır.")
    madde(doc, "Gerekli veri kanallarının birlikte bulunduğu ardışık yıl çiftinin seçilmesi.")
    madde(doc, f"Veri kesimi: {config.DATA_END_REASON}")
    madde(doc, "Gece/gündüz maskesi ve sızıntısız ölçekleme: ölçekleyici yalnızca eğitime fit edilmiş, "
               "metrikler gündüz hücrelerinden hesaplanmıştır.")
    madde(doc, "Test kümesinde seçim: her kesitte en iyi DL ve en iyi baseline test kümesi üzerinde "
               "seçilmiştir; bu, kazanan seçimi yanlılığı doğurur.")
    madde(doc, f"Çoklu karşılaştırma: {f['n_toplam']} kesit için karşılaştırma başına %95 GA kullanılmış, "
               f"çoklu karşılaştırma düzeltmesi yapılmamıştır.")
    madde(doc, "Tohum belirsizliği: bootstrap yalnızca test günü örneklemesini kapsar; baseline modeller "
               "tek koşuludur.")
    madde(doc, "Tek santral: veri PVDAQ sistem 4'ten (yaklaşık 1 kW) gelir; sonuçlar başka santrale "
               "genellenemez. Az günlü hava sınıflarında güven aralıkları geniştir.")
    madde(doc, "Hava tahmini girdisi yoktur ve hiperparametre araması yapılmamıştır.")
    etiket(doc, "Bulgularınızı Özetleyin")
    r240 = kz(f, "ufuk", "+4 saat")
    para(doc, f"Gerçek bir FV sistemin ölçüm verisi üzerinde LSTM ve CNN-LSTM modelleri dört baseline ile "
              f"aynı protokolde karşılaştırılmıştır. 16 ufuk ortalamasında "
              f"{kz_cumle(kz(f, 'ufuk_ort', '16'))}. +4 saatte {kz_cumle(r240)}. "
              f"{yon_cumlesi(f, 'ufuk', 'Ufuk')} {yon_cumlesi(f, 'hava', 'Hava sınıfı')} "
              f"Genel tablo: {sayim_cumlesi(f)}")
    etiket(doc, "Gelecek Çalışmalar",
           "Sayısal hava tahmini (NWP) ışınımının girdi olarak eklenmesi; birden fazla santral ve daha uzun "
           "veri ile genelleme; hiperparametre araması; olasılıksal (aralık veya kuantil) tahmin; kazanan "
           "seçiminin ayrı bir doğrulama kümesinde yapılması.")


def section_8_kaynakca(doc, f):
    baslik(doc, "8. KAYNAKÇA")
    erisim = f["system"]["accessed_on"]
    for key, n in sorted(REF_KEYS.items(), key=lambda kv: kv[1]):
        doc.add_paragraph(f"[{n}] " + REFS[key].replace("{erisim}", str(erisim)))
    unused = set(REFS) - set(REF_KEYS)
    assert not unused, f"Metinde atıf yapılmayan kaynaklar: {unused}"


def main():
    REF_KEYS.clear()
    COUNTER.update(tablo=0, sekil=0)
    facts = br.load_facts()
    doc = base_document()
    set_styles(doc)
    add_kapak(doc)
    section_1_giris(doc)
    section_2_literatur(doc)
    section_3_veri(doc, facts)
    section_4_metodoloji(doc, facts)
    section_5_kod(doc)
    section_6_sonuclar(doc, facts)
    section_7_tartisma(doc, facts)
    section_8_kaynakca(doc, facts)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORTS_DIR / "rapor_lblm368.docx"
    doc.save(str(out))
    print(f"Kaydedildi: {out}")
    print("RAPOR_LBLM368_TAMAM")


if __name__ == "__main__":
    main()
