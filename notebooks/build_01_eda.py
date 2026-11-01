# -*- coding: utf-8 -*-
"""notebooks/01_eda.ipynb dosyasını üretir (nbformat). Mantık src/eda.py içindedir."""
import sys
from pathlib import Path

import nbformat as nbf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {"name": "pv-forecast", "display_name": "pv-forecast", "language": "python"}
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell


def show(fn_call: str, key: str) -> str:
    return (f"p = {fn_call}\nprint(p.name)\nImage(filename=str(p))")


nb.cells = [
    md("# Faz 2 - Keşifsel Veri Analizi (EDA)\n\n"
       "Veri: NREL PVDAQ sistem 4 (Golden, CO), 2015-2016, 1 dk çözünürlüklü **gerçek** ölçümler, "
       "nominal kapasite 1 kW. Bu notebook yalnızca anlatır; grafik mantığı `src/eda.py` içindedir. "
       "Yorumlardaki sayılar aşağıdaki `stats` çıktısından gelir."),
    code("import sys\nfrom pathlib import Path\n"
         "PROJECT_ROOT = Path.cwd().resolve()\n"
         "if not (PROJECT_ROOT / 'src').exists():\n    PROJECT_ROOT = PROJECT_ROOT.parent\n"
         "sys.path.insert(0, str(PROJECT_ROOT))\n"
         "import json\nimport pandas as pd\nfrom IPython.display import Image\n"
         "from src import config, data, eda\nconfig.apply_plot_style()\n"
         "%matplotlib inline\nprint(config.summary())"),
    md("## Veri yükleme ve sayısal özet"),
    code("raw = data.load_raw()\nclean, cstats = data.clean_minutely(raw)\ngrid = data.load_grid()\n"
         "stats = eda.eda_stats(raw, cstats, grid)\n"
         "print(json.dumps(stats, ensure_ascii=False, indent=2))"),
    code(r"""from IPython.display import Markdown, display


def tr(x, nd=1):
    '''Türkçe ondalık virgül biçimi.'''
    return f"{x:.{nd}f}".replace(".", ",")


def tr_int(n):
    '''Binlik ayracı nokta olan tam sayı.'''
    return f"{int(n):,}".replace(",", ".")
"""),
    md("## Veri kesme kararı (2016-12-13)\n\n"
       "Veri **2016-12-13 00:00**'da kesilmiştir. Gerekçe: 13 Aralık'tan itibaren `module_temp_1` sürekli "
       "eksik, 14 Aralık'tan itibaren invertör kapalıdır; ışınım yüksekken AC güç neredeyse sıfırda kalır "
       "(sayısal değer aşağıda yazdırılır). Bu günlerde ışınımdan güç tahmin edilemez; modeli yanıltacağı için dışarıda bırakıldı. "
       "Aşağıdaki grafik ham (kesilmemiş) Aralık verisini ve kesme çizgisini gösterir."),
    code(show("eda.plot_december_fault(raw)", "eda_10")),
    code("print(config.DATA_END_REASON)\n"
         "print('14 Aralık sonrası POA>500 iken AC medyanı [W]:', stats['aralik_14_sonrasi_poa500_ac_medyan'])"),
    md("## 1. Zaman serisi\n\n"
       "Günlük ortalama AC güç ve POA 2015-2016 boyunca mevsimsel bir salınım gösterir; kışın düşük, "
       "yaz ve erken sonbaharda yüksektir. AC güç ile POA arasındaki korelasyon çok yüksektir "
       "(aşağıda yazdırılır), yani ışınım gücün ana belirleyicisidir. Kısa süreli düşüşler bulut, kar "
       "veya invertör olaylarına işaret eder (örn. Şubat 2015)."),
    code(show("eda.plot_time_series(grid)", "eda_01") +
         "\nprint('AC-POA korelasyonu:', stats['ac_poa_korelasyonu'])"),
    md("## 2. Bir haftalık yakınlaştırma\n\n"
       "Haziran 2015'in en güneşli ardışık 7 günü seçilmiştir (tarihler aşağıda). AC güç ışınımı neredeyse "
       "birebir izler; bulutlu saatlerde ikisi birlikte oynar. Kesikli çizgiler her gün için hesaplanan "
       "güneş öğlesidir; POA tepeleri bu çizgilerin çok yakınında, hafifçe solunda yer alır."),
    code(show("eda.plot_week_zoom(grid)", "eda_02") + "\nprint(stats['hafta_yakinlastirma'])"),
    md("### Saat dilimi notu"),
    code(r"""fark_dk = (stats['hesaplanan_guney_oglesi_ortalama'] - stats['poa_tepe_saati_medyan']) * 60
display(Markdown(
    "Zaman damgası sabit yerel standart saat (**UTC-7**, DST yok) varsayılmıştır. Günlük POA tepe saatinin "
    f"medyanı yaklaşık {tr(stats['poa_tepe_saati_medyan'], 2)}; hesaplanan güneş öğlesi ortalaması yaklaşık "
    f"**{tr(stats['hesaplanan_guney_oglesi_ortalama'], 2)}**. Fark yaklaşık {tr(abs(fark_dk), 0)} dakikadır; "
    f"POA>20 iken güneş yüksekliği ≤ 0 olan satır oranı {tr(stats['poa_pozitif_ama_yukselme_negatif_orani']*100, 2)}% "
    "(ihmal edilebilir düzeyde). Tepenin biraz erken olması panel eğim/azimutundan ve bulut etkisinden "
    "kaynaklanabilir. Kesin zaman ofseti bu veriyle doğrulanamamıştır; UTC-7 çalışma varsayımıdır."))"""),
    code("print('POA tepe saati medyanı:', stats['poa_tepe_saati_medyan'])\n"
         "print('Hesaplanan güneş öğlesi ortalaması:', stats['hesaplanan_guney_oglesi_ortalama'])\n"
         "print('POA>20 ve yükseklik<=0 oranı:', stats['poa_pozitif_ama_yukselme_negatif_orani'])"),
    md("## 3. Günlük profil (mevsime göre)\n\n"
       "Gün içi üretim çan biçimindedir ve öğle civarında tepe yapar. Yaz profili hem daha yüksek hem daha "
       "geniştir (uzun gün); kış profili alçak ve dardır. Bu nedenle saat ve yılın günü öznitelikleri "
       "modelde anlamlıdır."),
    code(show("eda.plot_daily_profile(grid)", "eda_03")),
    md("## 4. Aylık profil\n\n"
       "Günlük ortalama enerji kışın düşük, yaz ve erken sonbaharda yüksektir (değerler grafikte). İki yıl arasında aynı ayda bile belirgin fark vardır (örn. Ocak ve Şubat 2015 "
       "2016'dan düşüktür); bu, hava koşulu ve olaylardan kaynaklanır. Aralık 2016 yalnızca veri kesme "
       "tarihine kadarki günleri içerir (gün ataması bin başlangıcına göre yapılır)."),
    code(show("eda.plot_monthly_profile(grid)", "eda_04")),
    md("## 5. Korelasyon matrisi\n\n"
       "AC güç, POA ve modül sıcaklığı birbirleriyle güçlü pozitif ilişkilidir; ortam sıcaklığı daha "
       "zayıf ilişkilidir. Saat/yılın günü sin-cos çiftleri tek başına doğrusal korelasyonda düşük "
       "görünebilir ama döngüsel yapıyı taşırlar; güneş yüksekliği güçle yüksek korelasyon verir."),
    code(show("eda.plot_correlation(grid)", "eda_05")),
    md("## 6. Güç - ışınım saçılımı\n\n"
       "Gündüz satırlarında AC güç ışınımla yaklaşık doğrusal artar (korelasyon yukarıda). Aynı ışınımda "
       "saçılma modül sıcaklığına göre renk farkı olarak görülür: sıcak modüller verimi düşürür. "
       "Yatay çizgi nominal kapasiteyi gösterir (değer grafikte etiketlidir)."),
    code(show("eda.plot_power_vs_irradiance(grid)", "eda_06")),
    md("### Kapasite kırpılması notu"),
    code(r"""n_ust = stats['ac_kapasite_ustu_dakika']
if n_ust is not None:
    oran = 100 * n_ust / len(raw)
    display(Markdown(
        f"Ham veride AC güç nominal kapasiteyi ({tr(config.CAPACITY_W, 0)} W) aşan dakika sayısı **{tr_int(n_ust)}** "
        f"(toplamın %{tr(oran, 2)}'si). Bu değerler olası bir invertör sınırı/kırpılma ya da ölçüm "
        "belirsizliğine işaret edebilir; ayrıntılı analiz kapsam dışıdır, değerler silinmemiştir."))
print('AC > kapasite dakika:', n_ust)"""),
    md("## 7. Eksik veri özeti"),
    code(r"""eo = stats['eksik_oran_yuzde']
display(Markdown(
    "Temizlik sonrası, veri kesmeden önce eksik oranları (1 dk): "
    + ", ".join(f"`{k}` %{tr(v, 2)}" for k, v in eo.items())
    + ". `module_temp_1` eksiklerinin büyük bölümü Aralık 2016'nın sonunda toplanır; kesme kararıyla bu blok "
    "dışarıda kalır."))"""),
    code(show("eda.plot_missing(clean, grid)", "eda_07")),
    md("## 8. Temizlik öncesi / sonrası"),
    code(r"""sc = stats['sentinel_sayilari']
display(Markdown(
    "Ham gece POA değerleri sensör ofsetinden dolayı negatiftir "
    f"(medyan yaklaşık {tr(stats['gece_poa_median_ham'], 1)} W/m²); temizlik bunları 0'a çeker. "
    f"-7999 eksik işareti: `module_temp_1` {tr_int(sc['module_temp_1'])}, `poa_irradiance` {sc['poa_irradiance']}, "
    f"`ambient_temp` {sc['ambient_temp']}. {stats['uc_negatif_poa_sayisi']} uç negatif POA "
    f"(min {tr(stats['uc_negatif_poa_min'], 1)}) ve ham ortam sıcaklığı maksimumu "
    f"{tr(stats['ambient_maks_ham'], 2)} °C NaN yapılır; ≤ 2 adımlık boşluklar geçmiş değerle (ffill) doldurulur."))"""),
    code(show("eda.plot_cleaning_before_after(raw, clean)", "eda_08") +
         "\nprint('Gece POA medyanı (ham):', stats['gece_poa_median_ham'])\n"
         "print(stats['sentinel_sayilari'])\n"
         "print('Uç negatif POA:', stats['uc_negatif_poa_sayisi'], stats['uc_negatif_poa_min'])\n"
         "print('Ortam maks (ham):', stats['ambient_maks_ham'])"),
    md("## 9. Bulutlu ve açık gün\n\n"
       "Haziran 2016'dan günlük POA integrali en yüksek (açık) ve en düşük (ama arıza olmayan) gün "
       "seçilmiştir. Açık günde güç düzgün bir çan eğrisi çizer; bulutlu günde güç ışınımla birlikte "
       "hızlı ve düzensiz dalgalanır. Bu bulut kaynaklı değişkenlik tahmin edilmesi en zor kısımdır."),
    code(show("eda.plot_cloudy_vs_clear(grid)", "eda_09") +
         "\nprint('Açık gün:', stats['acik_gun'], ' Bulutlu gün:', stats['bulutlu_gun'])"),
    md("## Kapanış: Faz 2 temizlik kuralları özeti\n\n"
       "Sıra: (1) -7999 -> NaN, (2) POA gece negatifi 0'a ve uç negatifler NaN, (3) ortam/modül "
       "sıcaklığı fiziksel aralık dışı NaN, (4) 2016-12-13 00:00'da kesme, (5) right-label 15 dk "
       "ortalama, (6) yalnızca <= 2 adımlık boşluklar geçmiş değerle (ileri doldurma, geleceğe sızıntı yok) doldurulur; "
       "15 dk bininde en az MIN_VALID_MINUTES geçerli dakika şartı aranır. "
       "Problem tanımı ve bölme gerekçesi: `docs/PROBLEM_TANIMI.md`."),
]
nbf.write(nb, Path(__file__).resolve().parent / "01_eda.ipynb")
print("NB_URETILDI", len(nb.cells))
