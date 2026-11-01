# -*- coding: utf-8 -*-
"""Rapor üretici (python-docx).

Giriş, Literatür, Veri, Yöntem, Deneyler, Sonuçlar, Tartışma, Sonuç ve Kaynakça
bölümlerini üretir. Tüm sonuç sayıları results/ altındaki JSON/CSV dosyalarından
okunur ve fmt_tr ile biçimlenir; atıflar IEEE numaralı biçimdedir.

Çalıştırma: .venv/Scripts/python.exe reports/build_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

from src import analysis, compare, config  # noqa: E402


# --------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------
def fmt_tr(x, nd: int = 0) -> str:
    """Türkçe sayı biçimi: binlik ayıracı nokta, ondalık virgül."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _read_json(path: Path):
    if not Path(path).exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _require_json(path: Path):
    """Zorunlu girdi: eksikse hangi dosyanın eksik olduğunu açıkça bildir."""
    data = _read_json(path)
    if data is None:
        raise FileNotFoundError(f"Gerekli girdi dosyası bulunamadı: {path}")
    return data


def _require_csv(path: Path) -> pd.DataFrame:
    """Zorunlu CSV girdisi: eksikse hangi dosyanın eksik olduğunu açıkça bildir."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Gerekli girdi dosyası bulunamadı: {path}")
    return pd.read_csv(path)


def load_facts() -> dict:
    facts = {
        "system": _require_json(config.SYSTEM_INFO_FILE),
        "years": _require_json(config.SELECTED_YEARS_FILE),
        "windows": _require_json(config.WINDOWS_SUMMARY),
        "cleaning": _require_json(config.CLEANING_REPORT),
        "baselines_info": _read_json(config.MODELS_DIR / "baselines_info.json"),
    }
    from src import models

    facts["params"] = {
        "lstm": models.count_params(models.build_model("lstm")),
        "cnn_lstm": models.count_params(models.build_model("cnn_lstm")),
    }
    bi = facts["baselines_info"]
    facts["n_tab_features"] = bi.get("n_features") if bi else None
    m = config.RESULTS_DIR / "metrics"
    facts["summary"] = _require_csv(m / "summary.csv")
    facts["ufuk"] = _require_csv(m / "ufuk_tablosu.csv")
    facts["kazanan"] = _require_csv(m / "kazanan_ozet.csv")
    facts["boot"] = _require_csv(m / "bootstrap_fark.csv")
    facts["ablasyon"] = _require_csv(m / "ablation_summary.csv")
    facts["hava"] = _require_csv(m / "weather_metrics.csv")
    facts["hava_gun"] = _require_csv(m / "weather_days.csv")
    vc = facts["kazanan"]["dl_baseline_gecti"].value_counts()
    facts["n_toplam"] = int(len(facts["kazanan"]))
    facts["n_hayir"] = int(vc.get("hayır", 0))
    facts["n_belirsiz"] = int(vc.get("belirsiz", 0))
    facts["n_evet"] = int(vc.get("evet", 0))
    return facts


def set_styles(doc: Document) -> None:
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    rpr = st.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(a), "Calibri")
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), "tr-TR")
    rpr.append(lang)
    st.paragraph_format.space_after = Pt(6)


def para(doc, text, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def caption(doc, text):
    try:
        p = doc.add_paragraph(text, style="Caption")
    except KeyError:
        p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def table(doc, header, rows):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
    if len(header) >= 5:  # geniş tablolar: küçük punto, taşmayı önler
        for row in t.rows:
            for c in row.cells:
                for pp in c.paragraphs:
                    pp.paragraph_format.space_after = Pt(0)
                    for rr in pp.runs:
                        rr.font.size = Pt(8)
    return t


# --------------------------------------------------------------------------
# Kaynakça ve IEEE atıf düzeni (numara = metindeki ilk atıf sırası)
# --------------------------------------------------------------------------
REFS = {
    "antonanzas": "J. Antonanzas, N. Osorio, R. Escobar, R. Urraca, F. J. Martinez-de-Pison ve F. Antonanzas-Torres, \"Review of photovoltaic power forecasting,\" Solar Energy, cilt 136, s. 78–111, 2016, doi: 10.1016/j.solener.2016.06.069.",
    "wang": "H. Wang, Z. Lei, X. Zhang, B. Zhou ve J. Peng, \"A review of deep learning for renewable energy forecasting,\" Energy Conversion and Management, cilt 198, s. 111799, 2019, doi: 10.1016/j.enconman.2019.111799.",
    "hochreiter": "S. Hochreiter ve J. Schmidhuber, \"Long short-term memory,\" Neural Computation, cilt 9, sayı 8, s. 1735–1780, 1997, doi: 10.1162/neco.1997.9.8.1735.",
    "abdel": "M. Abdel-Nasser ve K. Mahmoud, \"Accurate photovoltaic power forecasting models using deep LSTM-RNN,\" Neural Computing and Applications, cilt 31, sayı 7, s. 2727–2740, 2019, doi: 10.1007/s00521-017-3225-z.",
    "chen": "T. Chen ve C. Guestrin, \"XGBoost: A scalable tree boosting system,\" Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining, s. 785–794, 2016, doi: 10.1145/2939672.2939785.",
    "kimcho": "T.-Y. Kim ve S.-B. Cho, \"Predicting residential energy consumption using CNN-LSTM neural networks,\" Energy, cilt 182, s. 72–81, 2019, doi: 10.1016/j.energy.2019.05.230.",
    "deline": "C. Deline, K. Perry, M. Deceglie, M. Muller, W. Sekulic ve D. Jordan, \"Photovoltaic Data Acquisition (PVDAQ) Public Datasets,\" veri seti, Open Energy Data Initiative (OEDI), NREL, 2021, doi: 10.25984/1846021.",
    "meta": "NREL, \"PVDAQ sistem 4 (NREL x-Si -1) metadata,\" OEDI veri gölü, erişim: {erisim}. [Çevrimiçi]. Erişilebilir: https://oedi-data-lake.s3.amazonaws.com/pvdaq/csv/system_metadata/4_system_metadata.json",
    "kingma": "D. P. Kingma ve J. Ba, \"Adam: A method for stochastic optimization,\" arXiv:1412.6980, 2014. [Çevrimiçi]. Erişilebilir: https://arxiv.org/abs/1412.6980",
    "paszke": "A. Paszke vd., \"PyTorch: An imperative style, high-performance deep learning library,\" arXiv:1912.01703, 2019. [Çevrimiçi]. Erişilebilir: https://arxiv.org/abs/1912.01703",
}
REF_KEYS: dict = {}


COUNTER = {"tablo": 3, "sekil": 0}  # Tablo 1-3 Veri/Yöntem bölümlerinde; şekiller sayaçla numaralanır


def cite(key: str) -> str:
    """IEEE atıf numarası: ilk atıf sırasına göre atanır, "[n]" döndürür."""
    if key not in REFS:
        raise KeyError(f"Bilinmeyen kaynak anahtarı: {key}")
    if key not in REF_KEYS:
        REF_KEYS[key] = len(REF_KEYS) + 1
    return f"[{REF_KEYS[key]}]"


# --------------------------------------------------------------------------
# Bölümler
# --------------------------------------------------------------------------
def add_title_page(doc):
    doc.core_properties.author = "Derin Öğrenme Dersi Dönem Projesi"
    doc.core_properties.title = "FV Güneş Santrali Çok Değişkenli Güç Üretim Tahmini"
    for _ in range(6):
        doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("FV Güneş Santrali Çok Değişkenli Güç Üretim Tahmini")
    r.bold = True
    r.font.size = Pt(26)
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = s.add_run("LSTM ve CNN-LSTM ile Gerçek Ölçüm Verisi Üzerinde Kısa Vadeli Tahmin")
    r.font.size = Pt(14)
    d = doc.add_paragraph()
    d.alignment = WD_ALIGN_PARAGRAPH.CENTER
    d.add_run("Derin Öğrenme Dersi Dönem Projesi").font.size = Pt(12)
    for _ in range(4):
        doc.add_paragraph()
    for line in ("[Ad Soyad]",
                 "[Öğrenci No]",
                 "[Ders]",
                 "[Öğretim Üyesi]",
                 "Kasım 2026"):
        q = doc.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        q.add_run(line).font.size = Pt(12)
    doc.add_page_break()


def _fld(run, kind):
    el = OxmlElement("w:fldChar")
    el.set(qn("w:fldCharType"), kind)
    run._r.append(el)


def add_toc(doc):
    doc.add_heading("İçindekiler", level=1)
    p = doc.add_paragraph()
    r = p.add_run()
    _fld(r, "begin")
    r2 = p.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    r2._r.append(instr)
    r3 = p.add_run()
    _fld(r3, "separate")
    p.add_run("İçindekiler tablosu Word'de açıldığında F9 ile güncellenir.")
    r5 = p.add_run()
    _fld(r5, "end")
    n = doc.add_paragraph()
    nr = n.add_run("Word'de açılışta alanları güncelleyin (F9).")
    nr.italic = True
    nr.font.size = Pt(8)
    uf = OxmlElement("w:updateFields")
    uf.set(qn("w:val"), "true")
    doc.settings.element.append(uf)
    doc.add_page_break()


def section_giris(doc):
    doc.add_heading("1. Giriş", level=1)
    para(doc, "Fotovoltaik (FV) güneş enerjisi santrallerinin güç üretimi; ışınım, bulutluluk ve "
              "sıcaklık gibi atmosferik koşullara bağlı olarak saatler içinde büyük ölçüde dalgalanır. "
              "Bu değişkenlik, üretimin şebekeye güvenli biçimde entegre edilmesini, dengeleme "
              "kapasitesinin planlanmasını ve piyasa katılımını zorlaştırır. Bu nedenle kısa vadeli "
              "(dakikalardan birkaç saate kadar) güç üretimi tahmini, FV sistemlerinin işletilmesinde "
              "temel bir ihtiyaçtır.")
    para(doc, f"Bu çalışmanın amacı, gerçek bir FV sistemden alınmış çok değişkenli ölçüm verisi "
              f"(AC güç, eğimli yüzey ışınımı, ortam sıcaklığı, modül sıcaklığı ve zaman öznitelikleri) "
              f"kullanarak geleceğe yönelik güç üretimini tahmin etmektir. Tahmin ufku "
              f"{config.HORIZON} adımdır (15 dakikalık adımlarla 4 saate kadar); ana değerlendirme ufku "
              f"+1 saattir ({config.MAIN_HORIZON_STEPS} adım ilerisi). Problem bir ileri tahmin "
              f"(forecasting) problemidir; anlık durumu kestiren nowcasting değildir ve gelecekteki "
              f"ışınım değerleri girdi olarak kullanılmaz.")
    para(doc, "Çalışmada yalnızca gerçek ve açık erişimli ölçüm verisi kullanılmıştır; sentetik veri "
              "üretilmemiştir. Katkılar şunlardır: (i) gerçek veri üzerinde uçtan uca, tekrar "
              "üretilebilir bir veri hazırlama ve sızıntısız değerlendirme hattı; (ii) basit referans "
              "yöntemler ve klasik makine öğrenmesi baseline'ları ile LSTM ve CNN-LSTM modellerinin "
              "aynı protokolle adil karşılaştırması; (iii) belgelenmiş ve sabit rastgele tohumlarla "
              "yeniden çalıştırılabilir kod tabanı.")


def section_literatur(doc):
    doc.add_heading("2. Literatür", level=1)
    para(doc, "FV güç tahmini yaklaşımları literatürde genel olarak fiziksel, istatistiksel ve "
              "makine öğrenmesi tabanlı yöntemler olarak sınıflandırılır; Antonanzas vd. bu "
              f"yöntemleri ve kullanılan girdi türlerini kapsamlı biçimde derlemiştir {cite('antonanzas')}. Fiziksel "
              "modeller sistem ve hava durumu bilgisini ışınım-güç dönüşüm zincirine bağlar; "
              "istatistiksel ve makine öğrenmesi yöntemleri ise geçmiş ölçümlerden doğrudan öğrenir. "
              f"Yenilenebilir enerji tahminine yönelik derin öğrenme yaklaşımları da ayrı bir derlemede "
              f"ele alınmıştır {cite('wang')}.")
    para(doc, f"Zaman serisi tahmininde yinelemeli sinir ağları, özellikle uzun kısa süreli bellek "
              f"(LSTM) ağları {cite('hochreiter')}, kapı mekanizmaları sayesinde uzun "
              f"bağımlılıkları öğrenebildiği için yaygın olarak kullanılır; FV güç tahmininde de "
              f"LSTM tabanlı modeller önerilmiştir {cite('abdel')}. Ağaç tabanlı topluluk "
              f"yöntemlerinden XGBoost {cite('chen')} ise tablo biçimindeki gecikmeli "
              f"özniteliklerle güçlü ve hızlı bir klasik baseline sunar.")
    para(doc, f"Hibrit CNN-LSTM yaklaşımında evrişimli katmanlar girdi penceresindeki yerel örüntüleri "
              f"çıkarır, LSTM katmanı ise bu özellik dizisindeki zamansal bağımlılığı modeller; bu "
              f"yaklaşım örneğin konutlarda enerji tüketimi tahmininde kullanılmıştır {cite('kimcho')}. Bu "
              "çalışmada aynı fikir, parametre sayısı bakımından LSTM ile kıyaslanabilir küçük bir "
              "mimariyle denenmiştir.")
    para(doc, "Son olarak, çok kısa ufuklarda son ölçümün tekrarına dayanan persistence yönteminin "
              "güçlü bir referans olduğu, bu nedenle derin öğrenme modellerinin değerinin yalnızca "
              "persistence ve mevsimsel persistence'a karşı gösterilebildiği unutulmamalıdır.")


def eda_fig(doc, name, text):
    path = config.FIGURES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Gerekli şekil bulunamadı: {path}")
    doc.add_picture(str(path), width=Cm(13))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    COUNTER["sekil"] += 1
    caption(doc, f"Şekil {COUNTER['sekil']}: {text}")


def section_veri(doc, f):
    s, y, w = f["system"], f["years"], f["windows"]
    doc.add_heading("3. Veri", level=1)
    doc.add_heading("3.1 Veri kaynağı ve sistem", level=2)
    para(doc, f"Veri, ABD Ulusal Yenilenebilir Enerji Laboratuvarı (NREL) tarafından yayımlanan "
              f"PVDAQ (Photovoltaic Data Acquisition) açık veri koleksiyonunun {s['system_id']} numaralı "
              f"sistemidir ({s['name']}). Sistem {s['site_location']} konumunda "
              f"(enlem {fmt_tr(s['latitude'], 4)}, boylam {fmt_tr(s['longitude'], 4)}, rakım "
              f"{fmt_tr(s['elevation_m'], 1)} m) yer alan, {fmt_tr(s['tilt_deg'])}° eğimli ve "
              f"{fmt_tr(s['azimuth_deg'])}° azimutlu (güneye bakan) sabit bir sistemdir; kurulu DC "
              f"kapasitesi {fmt_tr(s['capacity_kw'], 1)} kW'tır (5 adet Sanyo HIP-200BA3 mono-Si modül). "
              f"Veri gerçek ölçümdür; simülasyon değildir. Veri OEDI veri gölünden anonim olarak "
              f"{s['accessed_on']} tarihinde indirilmiştir. Veri seti {cite('deline')} ve sistem metadata kaydı {cite('meta')} kaynakçada verilmiştir "
              f"(veri seti DOI: https://doi.org/10.25984/1846021). "
              f"Lisans için gönderi sayfasında ayrı bir ad doğrulanamamış; OpenEI genel koşulu "
              f"(CC BY 4.0 benzeri) atıf şartıyla varsayılmıştır.")
    doc.add_heading("3.2 Seçilen dönem ve ön işleme", level=2)
    yrs = " ve ".join(str(v) for v in y["years"])
    days = " + ".join(str(y["days"][str(v)]) for v in y["years"])
    c = f["cleaning"]
    txt = (f"Gerekli kanalları (AC güç, POA ışınımı, ortam ve modül sıcaklığı) içeren ardışık yıl "
           f"çiftleri arasından {yrs} yılları seçilmiştir ({days} gün; 1 dakikalık ham çözünürlük). "
           f"Ham veride eksik ölçümler -7999 değeriyle işaretlidir; bu değerler NaN'a çevrilmiştir. "
           f"Veri 15 dakikalık ızgaraya yeniden örneklenmiş, gece ölçüm ofsetinden kaynaklanan "
           f"negatif ışınım değerleri sıfıra kırpılmış ve fiziksel olarak imkânsız uç değerler "
           f"temizlenmiştir. Temizlik sonrası ızgara {fmt_tr(c['n_rows'])} satır içerir "
           f"({c['start']} – {c['end']}).")
    para(doc, txt)
    para(doc, f"Veri bitiş tarihi: {config.DATA_END_REASON}")
    doc.add_heading("3.3 Bölme ve pencereler", level=2)
    para(doc, config.SPLIT_RATIONALE)
    tr, va, te = w["train"], w["val"], w["test"]
    para(doc, f"Girdi penceresi {config.WINDOW} adım (24 saat), çıktı {config.HORIZON} adımdır. "
              f"Pencere sayıları Tablo 1'de verilmiştir. Eğitim ve doğrulama kümelerinde tamamen gece "
              f"olan pencereler çıkarılmıştır (eğitim: {fmt_tr(tr['dropped_all_night'])}, doğrulama: "
              f"{fmt_tr(va['dropped_all_night'])}); test kümesinde ise "
              f"{fmt_tr(te['all_night_windows_kept'])} tamamen gece penceresi korunmuştur ve "
              f"değerlendirmede gündüz maskesi kullanılır.")
    caption(doc, "Tablo 1: Bölme başına pencere sayıları")
    table(doc, ["Küme", "Pencere sayısı", "Segment sayısı"],
          [["Eğitim", fmt_tr(tr["n_windows"]), len(tr["per_segment"])],
           ["Doğrulama", fmt_tr(va["n_windows"]), len(va["per_segment"])],
           ["Test", fmt_tr(te["n_windows"]), len(te["per_segment"])]])
    doc.add_paragraph()
    caption(doc, "Tablo 2: Test pencerelerinin mevsimlere dağılımı")
    sc = te["season_counts"]
    table(doc, ["Mevsim", "Test pencere sayısı"],
          [[k, fmt_tr(v)] for k, v in sc.items()])
    doc.add_paragraph()
    doc.add_heading("3.4 Keşifsel veri analizi", level=2)
    para(doc, "Şekil 1, temizlenmiş güç ve ışınım serisinin iki yıllık seyrini göstermektedir; "
              "mevsimsel döngü ve günlük salınım açıkça görülmektedir.")
    eda_fig(doc, "eda_01_zaman_serisi.png", "Güç ve ışınım zaman serisi (EDA)")
    para(doc, "Şekil 2, ortalama günlük güç ve ışınım profilini; Şekil 3, değişkenler arasındaki korelasyonları "
              "göstermektedir. Güç ile eğimli yüzey ışınımı arasındaki güçlü ilişki, ışınımın bu problemde "
              "temel bir girdi olduğunu düşündürür.")
    eda_fig(doc, "eda_03_gunluk_profil.png", "Ortalama günlük güç ve ışınım profili")
    eda_fig(doc, "eda_05_korelasyon.png", "Değişkenler arası korelasyon matrisi")
    para(doc, "Şekil 4, aynı mevsimde açık ve bulutlu bir günün güç profilini karşılaştırarak hava koşulunun "
              "üretim üzerindeki etkisini göstermektedir.")
    eda_fig(doc, "eda_09_bulutlu_acik_gun.png", "Açık ve bulutlu gün karşılaştırması")


def section_yontem(doc, f):
    p = f["params"]
    doc.add_heading("4. Yöntem", level=1)
    doc.add_heading("4.1 Problem tanımı", level=2)
    n_in = len(config.INPUT_FEATURES)
    para(doc, f"Model girdisi son {config.WINDOW} adımlık (24 saat) pencerede {n_in} kanaldır: "
              f"{', '.join(config.INPUT_FEATURES)}. Çıktı, AC gücün sonraki {config.HORIZON} adımlık "
              f"({config.HORIZON * 15} dakika) tahminidir. Gelecekteki ışınım ölçümü girdi olarak "
              f"kullanılmaz. Girdi ölçekleyicisi yalnızca eğitim kümesine fit edilir; böylece "
              f"doğrulama ve test bilgisi eğitime sızmaz.")
    doc.add_heading("4.2 Baseline yöntemler", level=2)
    nf = f["n_tab_features"]
    nf_txt = f"{nf}" if nf else "tablo biçiminde"
    bi = f["baselines_info"] or {}
    xgb_strategy = (bi.get("xgboost") or {}).get("strategy", "multi_output_tree")
    para(doc, f"Dört baseline kullanılmıştır: (i) persistence (son ölçümün tekrarı), (ii) mevsimsel "
              f"persistence ({config.STEPS_PER_DAY} adım, yani bir önceki günün aynı saati), "
              f"(iii) Doğrusal Regresyon ve (iv) XGBoost. Son ikisi gecikmeli ölçümler ve zaman "
              f"özniteliklerinden oluşan {nf_txt} öznitelikli tablo gösterimiyle çalışır ve 16 ufku "
              f"çok çıktılı olarak tahmin eder (XGBoost için {xgb_strategy}).")
    doc.add_heading("4.3 Derin öğrenme modelleri", level=2)
    para(doc, "LSTM modeli iki katmanlı bir LSTM ve son gizli durumdan tam bağlantılı çıkış "
              "katmanından oluşur. CNN-LSTM modeli iki Conv1d+ReLU bloğu, ardından tek katmanlı LSTM "
              "ve tam bağlantılı çıkış katmanı içerir. Mimariler Tablo 3'te özetlenmiştir.")
    caption(doc, "Tablo 3: Derin öğrenme mimarileri")
    table(doc, ["Model", "Katmanlar", "Eğitilebilir parametre"],
          [["LSTM", f"LSTM({config.LSTM_HIDDEN}) x {config.LSTM_LAYERS}, dropout {fmt_tr(config.DROPOUT, 1)}, Linear({config.HORIZON})",
            fmt_tr(p["lstm"])],
           ["CNN-LSTM", f"Conv1d({config.CNN_CHANNELS[0]}, k={config.CNN_KERNEL}) -> Conv1d({config.CNN_CHANNELS[1]}, k={config.CNN_KERNEL}) -> LSTM({config.LSTM_HIDDEN}) -> Linear({config.HORIZON})",
            fmt_tr(p["cnn_lstm"])]])
    doc.add_paragraph()
    doc.add_heading("4.4 Eğitim", level=2)
    para(doc, f"Modeller PyTorch {cite('paszke')} ile tek GPU'da (RTX 3060) Adam optimizasyonuyla {cite('kingma')} eğitilir "
              f"(öğrenme oranı {config.LR}, ağırlık sönümü {config.WEIGHT_DECAY}, toplu boyut "
              f"{config.BATCH_SIZE}). Doğrulama kaybı {config.LR_PATIENCE} dönem iyileşmediğinde "
              f"öğrenme oranı düşürülür (ReduceLROnPlateau); en fazla {config.MAX_EPOCHS} dönem ve "
              f"{config.EARLY_STOP_PATIENCE} dönemlik sabır ile erken durdurma uygulanır; gradyan "
              f"normu {config.GRAD_CLIP} değerinde kırpılır. Her model {len(config.SEEDS)} farklı "
              f"rastgele tohumla ({', '.join(str(x) for x in config.SEEDS)}) eğitilir ve sonuçlar "
              f"ortalama ± standart sapma olarak raporlanır.")
    doc.add_heading("4.5 Değerlendirme protokolü", level=2)
    para(doc, f"Tüm modeller tek bir evaluate() işleviyle aynı test pencereleri üzerinde "
              f"değerlendirilir. Gece örnekleri (güneş doğmadan önceki ve battıktan sonraki) kuralla "
              f"sıfır güç kabul edilir; birincil metrikler yalnızca gündüz hücrelerinden hesaplanır. "
              f"Metrikler MAE, RMSE, R² ve nRMSE'dir. nRMSE paydası kurulu kapasitedir "
              f"({fmt_tr(config.CAPACITY_W)} W). 16 ufuk ortalaması havuzlanmış hücrelerden hesaplanır; "
              f"+1 saatlik ufuk ayrıca raporlanır. Doğrulama ve test kümeleri komşu aylar olduğundan "
              f"erken durdurma doğrulamadan gelir; ancak hiperparametreler test kümesi üzerinde "
              f"ayarlanmamıştır.")


# ---------------------------------------------------------------------------
# Deneyler, Sonuçlar, Tartışma, Sonuç (tüm sayılar results/ dosyalarından)
# ---------------------------------------------------------------------------
FIG_W = Cm(13)

KARAR_TR = {"hayır": "baseline önde", "belirsiz": "belirsiz", "evet": "DL önde"}
HORIZON_LABEL = {1: "+15 dk", 4: "+1 saat", 8: "+2 saat", 16: "+4 saat"}


def fig(doc, key: str, text: str):
    path = config.FIGURES_DIR / analysis.FIGURES[key]
    if not path.exists():
        raise FileNotFoundError(f"Gerekli şekil bulunamadı: {path}")
    doc.add_picture(str(path), width=FIG_W)
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    COUNTER["sekil"] += 1
    caption(doc, f"Şekil {COUNTER['sekil']}: {text}")
    return COUNTER["sekil"]


def tab(doc, text: str, header, rows):
    COUNTER["tablo"] += 1
    caption(doc, f"Tablo {COUNTER['tablo']}: {text}")
    table(doc, header, rows)
    doc.add_paragraph()
    return COUNTER["tablo"]


def lab(model: str) -> str:
    return analysis.model_label(model) if hasattr(analysis, "model_label") else analysis.MODEL_LABELS_TR.get(model, model)


def kz(f, tur: str, kesit_prefix: str):
    d = f["kazanan"]
    r = d[(d.kesit_turu == tur) & (d.kesit.astype(str).str.startswith(kesit_prefix))]
    if len(r) != 1:
        raise ValueError(f"kazanan_ozet.csv'de {tur}/{kesit_prefix} için tek satır beklendi, {len(r)} bulundu")
    return r.iloc[0]


def ga(lo, hi, nd=1) -> str:
    return f"[{fmt_tr(lo, nd)}; {fmt_tr(hi, nd)}]"


def kz_cumle(r) -> str:
    """Bir kazanan_ozet satırını karar_olcutu'ndan bağımsız, koşullu bir cümleye çevirir."""
    d = r.dl_baseline_gecti
    d_ad, b_ad = lab(r.en_iyi_dl), lab(r.en_iyi_baseline)
    ci = f"fark {fmt_tr(r.fark_W, 1)} W, %95 GA {ga(r.ci_low, r.ci_high)}"
    if d == "evet":
        return f"{d_ad} ({fmt_tr(r.dl_RMSE_W, 1)} W), {b_ad} ({fmt_tr(r.baseline_RMSE_W, 1)} W) karşısında anlamlı biçimde önde ({ci})"
    if d == "hayır":
        return f"{d_ad} ({fmt_tr(r.dl_RMSE_W, 1)} W), {b_ad} ({fmt_tr(r.baseline_RMSE_W, 1)} W) karşısında geride ({ci})"
    return f"{d_ad} ({fmt_tr(r.dl_RMSE_W, 1)} W) ile {b_ad} ({fmt_tr(r.baseline_RMSE_W, 1)} W) arasındaki fark ayırt edilemedi ({ci})"


def _hist(f):
    out = {}
    for m in ("lstm", "cnn_lstm"):
        hs = [_require_json(config.MODELS_DIR / f"{m}_seed{s}_history.json") for s in config.SEEDS]
        out[m] = hs
    return out


def section_deneyler(doc, f):
    w = f["windows"]
    tr, va, te = w["train"], w["val"], w["test"]
    n_gun = int(f["boot"].n_gun.iloc[0])
    hs = _hist(f)
    doc.add_heading("5. Deneyler", level=1)
    doc.add_heading("5.1 Deney düzeni", level=2)
    para(doc, f"Eğitim, doğrulama ve test kümeleri zamansal olarak ardışıktır ve sırasıyla "
              f"{fmt_tr(tr['n_windows'])}, {fmt_tr(va['n_windows'])} ve {fmt_tr(te['n_windows'])} pencere "
              f"içerir (Tablo 1). Test kümesi {n_gun} takvim gününü kapsar. Derin öğrenme modelleri "
              f"{len(config.SEEDS)} farklı tohumla ({', '.join(str(x) for x in config.SEEDS)}) eğitilmiş, "
              f"sonuçlar tohumlar üzerinden ortalama ± standart sapma olarak verilmiştir. Optimizasyon "
              f"Adam ile {cite('kingma')}, doğrulama kaybı üzerinden erken durdurma ve öğrenme oranı "
              f"düşürme ile yapılmıştır. Persistence, mevsimsel persistence, Doğrusal Regresyon ve "
              f"XGBoost tek koşuyla (tohum çeşitlemesi olmadan) çalıştırılmıştır.")
    ep_txt = []
    for m in ("lstm", "cnn_lstm"):
        h = hs[m]
        be = sum(x["best_epoch"] for x in h) / len(h)
        sec = sum(x["total_sec"] for x in h) / len(h)
        ep_txt.append(f"{lab(m)} için ortalama en iyi dönem {fmt_tr(be, 1)} ve tohum başına ortalama "
                      f"eğitim süresi {fmt_tr(sec, 0)} saniyedir")
    para(doc, "Eğitim süreci: " + "; ".join(ep_txt) + ". Bu süreler, modellerin tek bir RTX 3060 üzerinde "
              "dakikalar mertebesinde eğitilebildiğini göstermektedir.")
    doc.add_heading("5.2 Değerlendirme ve karar ölçütü", level=2)
    para(doc, f"Tüm modeller aynı test pencerelerinde, yalnızca gündüz hücreleri üzerinde RMSE, MAE ve "
              f"nRMSE ile değerlendirilir. Raporlanan kapsamlar +15 dk, +1 saat, +2 saat ve +4 saat "
              f"ufuklarıyla 16 ufkun ortalamasıdır. Modeller arasındaki farkların istatistiksel "
              f"anlamlılığı gün-bloklu bootstrap ile sınanır: test günleri blok olarak yerine koymalı "
              f"yeniden örneklenir (B = {fmt_tr(compare.B)}) ve RMSE farkı için %95 güven aralığı (GA) "
              f"hesaplanır. Her kesit için en iyi derin öğrenme modeli ile en iyi baseline karşılaştırılır; "
              f"GA sıfırı içeriyorsa karar \"belirsiz\", içermiyorsa fark yönüne göre \"DL önde\" veya "
              f"\"baseline önde\" olur. Toplam {f['n_toplam']} kesit (ufuk, mevsim, hava sınıfı, saat ve "
              f"ablasyon grubu) aynı kuralla karara bağlanmıştır.")
    doc.add_heading("5.3 Eğitim eğrileri", level=2)
    para(doc, "Aşağıdaki şekil, her model ve tohum için eğitim ve doğrulama kayıplarını göstermektedir.")
    fig(doc, "kayip", "Eğitim ve doğrulama kayıp eğrileri")


def section_sonuclar(doc, f):
    s, u, kz_df = f["summary"], f["ufuk"], f["kazanan"]
    doc.add_heading("6. Sonuçlar", level=1)
    # 6.1
    doc.add_heading("6.1 Genel karşılaştırma", level=2)
    d = s[(s["mask"] == "day") & (s.scope == "mean16")].copy()
    order = ["persistence", "seasonal_persistence", "linreg", "xgboost", "lstm", "cnn_lstm"]
    d = d.set_index("model").loc[order]
    rows = []
    for m, r in d.iterrows():
        rm = fmt_tr(r.RMSE_W_mean, 1) + (f" ± {fmt_tr(r.RMSE_W_std, 1)}" if r.n_runs > 1 else " (tek koşu)")
        rows.append([lab(m), rm, fmt_tr(r.MAE_W_mean, 1), fmt_tr(r.nRMSE_mean * 100, 1) + " %"])
    best = d.RMSE_W_mean.idxmin()
    para(doc, f"Tablo {COUNTER['tablo'] + 1}, 16 ufkun ortalaması için gündüz RMSE, MAE ve nRMSE değerlerini "
              f"vermektedir. Nokta tahminde en düşük ortalama RMSE {lab(best)} modelindedir "
              f"({fmt_tr(d.loc[best, 'RMSE_W_mean'], 1)} W); LSTM {fmt_tr(d.loc['lstm', 'RMSE_W_mean'], 1)} W, "
              f"CNN-LSTM {fmt_tr(d.loc['cnn_lstm', 'RMSE_W_mean'], 1)} W ve XGBoost "
              f"{fmt_tr(d.loc['xgboost', 'RMSE_W_mean'], 1)} W değerlerine ulaşmıştır. Persistence "
              f"{fmt_tr(d.loc['persistence', 'RMSE_W_mean'], 1)} W ile en zayıf referanstır.")
    tab(doc, "Model karşılaştırması (gündüz, 16 ufuk ortalaması)", ["Model", "RMSE (W)", "MAE (W)", "nRMSE"], rows)
    fig(doc, "karsilastirma", "Modellerin RMSE karşılaştırması")
    b = f["boot"]
    bn = {"h4": "+1 saat", "mean16": "16-ufuk ort."}
    brow = []
    for (ma, mb), g in b.groupby(["model_a", "model_b"], sort=False):
        for k in ("h4", "mean16"):
            r = g[g.kapsam == k].iloc[0]
            brow.append([f"{lab(ma)} - {lab(mb)}", bn[k], ("+" if r.fark_W > 0 else "") + fmt_tr(r.fark_W, 1),
                         ga(r.ci_low, r.ci_high), "evet" if r.anlamli else "hayır"])
    lx = b[(b.model_a == "lstm") & (b.model_b == "xgboost") & (b.kapsam == "mean16")].iloc[0]
    ll = b[(b.model_a == "lstm") & (b.model_b == "linreg") & (b.kapsam == "mean16")].iloc[0]
    lc = b[(b.model_a == "lstm") & (b.model_b == "cnn_lstm") & (b.kapsam == "mean16")].iloc[0]
    para(doc, f"Tablo {COUNTER['tablo'] + 1}'de model çiftleri için bootstrap farkları verilmiştir "
              f"(negatif fark ilk modelin daha iyi olduğunu gösterir). LSTM - XGBoost farkı 16 ufuk "
              f"ortalamasında {fmt_tr(lx.fark_W, 1)} W olup %95 GA {ga(lx.ci_low, lx.ci_high)} "
              f"{'sıfırı içermediği için anlamlıdır' if lx.anlamli else 'sıfırı içerdiği için anlamlı değildir'}. "
              f"Doğrusal Regresyona karşı LSTM farkı {fmt_tr(ll.fark_W, 1)} W (GA {ga(ll.ci_low, ll.ci_high)}) "
              f"olup {'anlamlıdır' if ll.anlamli else 'anlamlı değildir'}. İki derin öğrenme mimarisi arasındaki "
              f"fark (LSTM - CNN-LSTM) {fmt_tr(lc.fark_W, 1)} W, GA {ga(lc.ci_low, lc.ci_high)} ile "
              f"{'anlamlıdır' if lc.anlamli else 'anlamlı değildir'}.")
    tab(doc, "Gün-bloklu bootstrap ile RMSE farkları (W)", ["Çift", "Kapsam", "Fark", "%95 GA", "Anlamlı"], brow)
    # 6.2
    doc.add_heading("6.2 Tahmin ufkuna göre hata", level=2)
    urows = []
    for h, lbl in HORIZON_LABEL.items():
        r = u[u.horizon_min == h * 15].iloc[0]
        urows.append([lbl] + [fmt_tr(r[f"{m}_RMSE_W"], 1) for m in order])
    tab(doc, "Ufuğa göre gündüz RMSE (W)", ["Ufuk"] + [lab(m) for m in order], urows)
    r15, r60, r120, r240 = (kz(f, "ufuk", x) for x in ("+15", "+1 saat", "+2 saat", "+4 saat"))
    para(doc, "Persistence hatası ufukla hızla artar; mevsimsel persistence ise her ufukta aynı hatayı verir "
              "çünkü tahmini dünün aynı saatlerinden kurulur. Ufuk bazlı kararlar şöyledir: "
              f"+15 dk'da {kz_cumle(r15)}; +1 saatte {kz_cumle(r60)}; +2 saatte {kz_cumle(r120)}; "
              f"+4 saatte {kz_cumle(r240)}.")
    fig(doc, "ufuk", "Tahmin ufkuna göre RMSE")
    # 6.3 / 6.4
    doc.add_heading("6.3 Tahmin örnekleri", level=2)
    para(doc, "Aşağıdaki şekil, test döneminden seçilmiş günler için gerçek güç ile model tahminlerini karşılaştırır.")
    fig(doc, "tahmin", "Test döneminden örnek günlerde tahmin ve gerçek güç")
    doc.add_heading("6.4 Günün saatine göre hata", level=2)
    sa = kz_df[kz_df.kesit_turu == "saat"]
    n_sa_hayir = int((sa.dl_baseline_gecti == "hayır").sum())
    n_sa_evet = int((sa.dl_baseline_gecti == "evet").sum())
    zr = sa.loc[sa.baseline_RMSE_W.idxmax()]
    para(doc, f"Hata öğle saatlerinde en yüksektir: en yüksek baseline hatası {zr.kesit} saatindedir "
              f"({fmt_tr(zr.baseline_RMSE_W, 1)} W). {len(sa)} saatlik kesitten {n_sa_hayir} tanesinde "
              f"baseline, {n_sa_evet} tanesinde derin öğrenme anlamlı biçimde önde; kalan "
              f"{len(sa) - n_sa_hayir - n_sa_evet} saatte fark ayırt edilemedi (Tablo {COUNTER['tablo'] + 3}).")
    fig(doc, "saat", "Günün saatine göre RMSE")
    # 6.5 hava
    doc.add_heading("6.5 Hava koşuluna göre hata", level=2)
    hv = f["hava"]
    hv = hv[hv.scope == "mean16"].groupby(["model", "sinif", "sinif_ad", "n_gun"], as_index=False).RMSE_W.mean()
    hk = ["Kapalı", "Parçalı", "Açık"]
    hrows = []
    for sid, nm in enumerate(hk):
        g = hv[hv.sinif == sid]
        ng = int(g.n_gun.iloc[0])
        hrows.append([f"{nm} ({ng} gün)"] + [fmt_tr(g[g.model == m].RMSE_W.iloc[0], 1) for m in order])
    tab(doc, "Hava sınıfına göre gündüz RMSE (W, 16 ufuk ortalaması)", ["Sınıf"] + [lab(m) for m in order], hrows)
    hg = f["hava_gun"]
    cnt = hg.sinif_ad.value_counts()
    ka, kp, kk = (kz(f, "hava", x) for x in ("Açık", "Parçalı", "Kapalı"))
    para(doc, f"Günler açıklık indeksine (KT) göre sınıflanmıştır; tüm dönemde {int(cnt.get('Açık', 0))} açık, "
              f"{int(cnt.get('Parçalı', 0))} parçalı ve {int(cnt.get('Kapalı', 0))} kapalı gün vardır. "
              f"Açık günlerde {kz_cumle(ka)}. Parçalı günlerde {kz_cumle(kp)}. Kapalı günlerde "
              f"{kz_cumle(kk)}; bu sınıf yalnızca {kk.kesit.split('(')[1].split(' ')[0]} test gününe "
              f"dayandığından sıralamalar kesin kabul edilmemelidir.")
    fig(doc, "hava", "Hava koşulu sınıflarına göre RMSE")
    # 6.6 ablasyon
    doc.add_heading("6.6 Öznitelik ablasyonu", level=2)
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
    para(doc, "Ablasyonda girdi grupları kümülatif olarak eklenmiştir: A yalnızca güç, B + zaman öznitelikleri, "
              "C + ışınım, D + sıcaklıklar (tam küme). Parantez içindeki değer bir önceki gruba göre RMSE "
              f"değişimidir (negatif iyileşme). Işınım grubunun katkısı LSTM'de {fmt_tr(cg['lstm'], 1)} W, "
              f"CNN-LSTM'de {fmt_tr(cg['cnn_lstm'], 1)} W'tır. Katkılar kümülatif ve tek sırada ölçüldüğünden "
              f"bireysel etki olarak yorumlanmamalıdır. Karşılaştırma kararları: "
              + "; ".join(f"grup {g[0]}: {KARAR_TR[kz(f, 'ablasyon', g).dl_baseline_gecti]}"
                          for g in ("A_guc", "B_zaman", "C_isinim", "D_tam")) + ".")
    tab(doc, "Ablasyon: gündüz RMSE (W, 16 ufuk ortalaması) ve önceki gruba göre değişim",
        ["Model", "A: güç", "B: + zaman", "C: + ışınım", "D: tam"], arows)
    fig(doc, "ablasyon", "Öznitelik ablasyonu")
    # 6.7 kazanan özeti
    doc.add_heading("6.7 Kazanan özeti", level=2)
    krows = []
    for _, r in kz_df.iterrows():
        krows.append([f"{r.kesit_turu}: {r.kesit}", lab(r.en_iyi_baseline), fmt_tr(r.baseline_RMSE_W, 1),
                      lab(r.en_iyi_dl), fmt_tr(r.dl_RMSE_W, 1), fmt_tr(r.fark_W, 1),
                      ga(r.ci_low, r.ci_high), KARAR_TR[r.dl_baseline_gecti]])
    para(doc, f"Tablo {COUNTER['tablo'] + 1}, {f['n_toplam']} kesitin tamamı için en iyi baseline ile en iyi derin "
              f"öğrenme modelini karşılaştırır. Sonuç: {f['n_hayir']} kesitte baseline önde, {f['n_belirsiz']} "
              f"kesitte fark belirsiz, {f['n_evet']} kesitte derin öğrenme anlamlı biçimde önde.")
    tab(doc, "Kesit bazında en iyi baseline ve en iyi DL (RMSE, W)",
        ["Kesit", "Baseline", "RMSE", "DL", "RMSE", "Fark", "%95 GA", "Karar"], krows)


def section_tartisma(doc, f):
    kz_df = f["kazanan"]
    doc.add_heading("7. Tartışma", level=1)
    para(doc, f"Bulgular, derin öğrenme modellerinin bu veri setinde klasik baseline'lara göre belirgin bir "
              f"üstünlük sağlamadığını göstermektedir: {f['n_toplam']} kesitin {f['n_hayir']} tanesinde "
              f"baseline anlamlı biçimde önde, {f['n_belirsiz']} tanesinde fark belirsiz ve yalnızca "
              f"{f['n_evet']} tanesinde derin öğrenme anlamlı biçimde önde. \"Belirsiz\" kararı, 157 günlük "
              f"tek bir test döneminde farkın ayırt edilemediği anlamına gelir; iki yöntemin eşit olduğu "
              f"anlamına gelmez.")
    doc.add_heading("7.1 Derin öğrenmenin baseline'ı geçemediği kesitler", level=2)
    h = kz_df[kz_df.dl_baseline_gecti == "hayır"]
    if len(h) == 0:
        para(doc, "Hiçbir kesitte baseline anlamlı biçimde önde değildir.")
    for _, r in h.iterrows():
        doc.add_paragraph(f"{r.kesit_turu.capitalize()} kesiti {r.kesit}: en iyi baseline {lab(r.en_iyi_baseline)} "
                          f"({fmt_tr(r.baseline_RMSE_W, 1)} W), en iyi DL {lab(r.en_iyi_dl)} "
                          f"({fmt_tr(r.dl_RMSE_W, 1)} W); fark {fmt_tr(r.fark_W, 1)} W, %95 GA "
                          f"{ga(r.ci_low, r.ci_high)}.", style="List Bullet")
    para(doc, "Kısa ufuklarda son ölçümler ve gecikmeli öznitelikler zaten yüksek bilgi taşıdığından, basit ve "
              "iyi ayarlanabilir yöntemler (Doğrusal Regresyon, XGBoost) derin ağlarla başa baş veya onlardan "
              "daha iyidir. Derin öğrenmenin avantajı, hata ufuk uzadıkça ve hava değişkenliği arttıkça "
              "ortaya çıkmaya başlar.")
    doc.add_heading("7.2 Belirsiz ve DL lehine kesitler", level=2)
    e = kz_df[kz_df.dl_baseline_gecti == "evet"]
    para(doc, f"{f['n_belirsiz']} kesitte güven aralığı sıfırı içerir; nokta tahmin bir yön gösterse de bu yön "
              f"istatistiksel olarak desteklenmemiştir. Derin öğrenmenin anlamlı biçimde önde olduğu "
              f"{f['n_evet']} kesit: " + ", ".join(f"{r.kesit_turu} {r.kesit}" for _, r in e.iterrows()) + ".")
    doc.add_heading("7.3 Sınırlamalar", level=2)
    for t in (
        "Test kümesinde seçim: her kesitte en iyi DL ve en iyi baseline test kümesi üzerinde seçilmiştir; bu, "
        "kazanan seçimi yanlılığı doğurur.",
        f"Çoklu karşılaştırma: {f['n_toplam']} kesit için karşılaştırma başına %95 GA kullanılmış, çoklu "
        f"karşılaştırma düzeltmesi yapılmamıştır; birkaç \"anlamlı\" sonuç şansa bağlı olabilir.",
        "Tohum belirsizliği: bootstrap yalnızca test günü örneklemesini kapsar; derin öğrenme tohum "
        "değişkenliği yalnızca ortalama alınarak sönümlenmiştir, baseline modeller tek koşuludur.",
        "Tek santral ve tek sistem: veri PVDAQ sistem 4'ten (yaklaşık 1 kW) gelir; sonuçlar başka santrale, "
        "iklime veya ölçeğe genellenemez.",
        "Kısa kapsam: yalnızca iki yıllık veri kullanılmış ve tek bir ardışık test dönemi değerlendirilmiştir; "
        "az günlü sınıflarda (ör. kapalı hava) güven aralıkları geniştir.",
        "Aralık 2016 arıza dönemi: veri, modül sıcaklığı kanalının ve eviricinin devre dışı kaldığı "
        "13 Aralık 2016'da kesilmiştir; bu dönem değerlendirmeye dahil değildir.",
        "Hava tahmini girdisi yok: modeller gelecekteki ışınım veya bulutluluk tahminini kullanmaz; bu, "
        "uzun ufuklarda ulaşılabilir doğruluğu sınırlar.",
        "Hiperparametreler sabit tutulmuş, arama yapılmamıştır; nokta tahmin yapılmış, olasılıksal tahmin "
        "yapılmamıştır.",
    ):
        doc.add_paragraph(t, style="List Bullet")


def section_sonuc(doc, f):
    r = kz(f, "ufuk_ort", "16")
    hv_a, hv_k = kz(f, "hava", "Açık"), kz(f, "hava", "Kapalı")
    r240 = kz(f, "ufuk", "+4 saat")
    doc.add_heading("8. Sonuç", level=1)
    para(doc, f"Bu çalışmada gerçek bir FV sistemin ölçüm verisi üzerinde LSTM ve CNN-LSTM modelleri, dört "
              f"baseline ile aynı protokolde karşılaştırılmıştır. 16 ufuk ortalamasında {kz_cumle(r)}. "
              f"Ufuk bazında bakıldığında kısa ufuklarda klasik yöntemler güçlüdür; +4 saatte "
              f"{kz_cumle(r240)}. Hava koşulu açısından açık günlerde {kz_cumle(hv_a)}, kapalı günlerde "
              f"{kz_cumle(hv_k)}. Genel tablo, {f['n_toplam']} kesitin {f['n_evet']} tanesinde derin "
              f"öğrenmenin, {f['n_hayir']} tanesinde baseline'ın anlamlı biçimde önde olduğu, geri kalanında "
              f"ise farkın ayırt edilemediği şeklindedir.")
    para(doc, "Gelecek çalışmalarda hava tahmini girdilerinin (ör. sayısal hava tahmini ışınımı) eklenmesi, "
              "birden fazla santral ve daha uzun veri ile genelleme, hiperparametre araması ve "
              "olasılıksal (aralık veya kuantil) tahmin değerlendirilebilir.")


def section_kaynakca(doc, f):
    doc.add_heading("9. Kaynakça", level=1)
    erisim = f["system"]["accessed_on"]
    for key, n in sorted(REF_KEYS.items(), key=lambda kv: kv[1]):
        doc.add_paragraph(f"[{n}] " + REFS[key].replace("{erisim}", str(erisim)))
    unused = set(REFS) - set(REF_KEYS)
    assert not unused, f"Metinde atıf yapılmayan kaynaklar: {unused}"


def write_config_snapshot() -> Path:
    """Sunumun (build_deck.js) okuduğu yapılandırma özeti; rapor ve sunum aynı kaynaktan beslenir."""
    snap = {"seeds": list(config.SEEDS), "window": config.WINDOW, "horizon": config.HORIZON,
            "n_channels": len(config.INPUT_FEATURES)}
    path = config.RESULTS_DIR / "config_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return path


def main():
    REF_KEYS.clear()
    COUNTER.update(tablo=3, sekil=0)
    write_config_snapshot()
    facts = load_facts()
    doc = Document()
    set_styles(doc)
    add_title_page(doc)
    add_toc(doc)
    section_giris(doc)
    section_literatur(doc)
    section_veri(doc, facts)
    section_yontem(doc, facts)
    section_deneyler(doc, facts)
    section_sonuclar(doc, facts)
    section_tartisma(doc, facts)
    section_sonuc(doc, facts)
    section_kaynakca(doc, facts)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORTS_DIR / "rapor.docx"
    doc.save(str(out))
    print(f"Kaydedildi: {out}")
    print("RAPOR_TAMAM")


if __name__ == "__main__":
    main()
