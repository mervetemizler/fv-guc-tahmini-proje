# FV Güneş Santrali Çok Değişkenli Güç Üretim Tahmini

Bu proje, bir fotovoltaik (FV) güneş santralinin güç üretimini **gerçek ölçüm verisi** (NREL PVDAQ) ile tahmin eder; sahte veya sentetik veri kullanılmaz. Girdi olarak son 96 adımlık (24 saat, 15 dk) ışınım, modül/ortam sıcaklığı, geçmiş güç ve zaman öznitelikleri kullanılır; ana ufuk +1 saattir ve model 16 adımlık (4 saat) çıkış üretir. Baseline modeller (persistence, mevsimsel persistence, doğrusal regresyon, XGBoost) ile LSTM ve CNN-LSTM aynı test penceresinde, aynı metrik fonksiyonuyla ve tekrar üretilebilir biçimde karşılaştırılır. Karşılaştırma dürüsttür: derin öğrenmenin baseline'ı geçemediği durumlar da raporlanır.

## Veri

- Kaynak: NREL **PVDAQ Public Datasets**, sistem 4 ("NREL x-Si -1", Golden, CO; 1,0 kW DC), 2015-2016, 1 dk ölçüm, 15 dk ızgaraya indirgenir.
- Lisans: gönderi sayfasında ayrı bir lisans adı doğrulanamadı; OpenEI genel koşulu CC BY 4.0 benzeri kabul edilmiş, atıf yapılmıştır (ayrıntı: [data/raw/DATA_SOURCE.md](data/raw/DATA_SOURCE.md)).
- Atıf: Deline, C., Perry, K., Deceglie, M., Muller, M., Sekulic, W., & Jordan, D. (2021). Photovoltaic Data Acquisition (PVDAQ) Public Datasets. [Data set]. OEDI, NREL. https://doi.org/10.25984/1846021
- Ham veri git'te **yoktur**; şu komutlarla indirilir: `src/download_pvdaq.py` ve `src/build_raw_parquet.py` (aşağıdaki "Çalıştırma" bölümüne bakın).
- Problem tanımı: [docs/PROBLEM_TANIMI.md](docs/PROBLEM_TANIMI.md)

## Kurulum (Windows)

```powershell
# 1) Sanal ortam (Python 3.14)
uv venv --python 3.14
# 2) GPU PyTorch: yalnız torch CUDA indeksinden (PyPI Windows wheel'i CPU-only)
uv pip install torch --index-url https://download.pytorch.org/whl/cu132
#    yedek indeksler: .../whl/cu130 veya .../whl/cu126
# 3) Diğer paketler (sabitlenmiş sürümler)
uv pip install -r requirements.txt
# 4) Çekirdeği Jupyter'e tanıt
.venv\Scripts\python.exe -m ipykernel install --user --name pv-forecast
```

Sunum üretimi için ayrıca Node ve `npm i -g pptxgenjs` gerekir. Slaytları PDF/PNG'ye çevirip görsel kontrol etmek için LibreOffice ve Poppler kullanılır (yalnız sunum render QA için; bkz. [presentation/TOOLCHAIN.md](presentation/TOOLCHAIN.md)).

## Çalıştırma

**Hızlı yol (önerilen):** Notebook'ları (`notebooks/01_eda.ipynb` ... `05_karsilastirma.ipynb`, çekirdek `pv-forecast`) açıp *Restart & Run All* yapın. Notebook'lar `results/` altındaki kayıtlı çıktıları okur, **yeniden eğitim yapmaz**. Komut satırından:

```bash
.venv/Scripts/python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks/05_karsilastirma.ipynb
```

**Tam yeniden üretim sırası** (proje kökünden; her komut `.venv/Scripts/python.exe -I ...` ile):

```bash
.venv/Scripts/python.exe -I src/download_pvdaq.py download --years 2015 2016 --workers 8
.venv/Scripts/python.exe -I src/build_raw_parquet.py --years 2015 2016
.venv/Scripts/python.exe -I src/data.py
.venv/Scripts/python.exe -I src/windows.py
.venv/Scripts/python.exe -I src/run_all.py          # baseline + LSTM/CNN-LSTM eğitimi (GPU)
.venv/Scripts/python.exe -I src/ablation.py         # öznitelik ablasyonu (yeniden eğitim); --only dl|tab kısmi koşu mevcut CSV ile birleştirilir
.venv/Scripts/python.exe -I src/weather.py          # hava sınıfı bazında hata
.venv/Scripts/python.exe -I src/figures.py          # sonuç figürleri
.venv/Scripts/python.exe -I src/compare.py          # bootstrap karşılaştırma, kazanan_ozet.csv, yorum.md
.venv/Scripts/python.exe reports/build_report.py    # reports/rapor.docx
.venv/Scripts/python.exe -I reports/readme_sonuc.py # bu README'nin sonuç bloğu
NODE_PATH="$(npm root -g)" node presentation/build_deck.js   # presentation/sunum.pptx
```

**Testler:** `pytest` ortama kurulu değildir; test dosyaları kendi `__main__` çalıştırıcısıyla koşulur:

```bash
.venv/Scripts/python.exe -I tests/test_windows.py
.venv/Scripts/python.exe -I tests/test_evaluate.py
.venv/Scripts/python.exe -I tests/test_baselines.py
.venv/Scripts/python.exe -I tests/test_models.py
.venv/Scripts/python.exe -I tests/test_ablation.py
.venv/Scripts/python.exe -I tests/test_weather.py
.venv/Scripts/python.exe -I tests/test_compare.py
.venv/Scripts/python.exe -I tests/test_yorum.py
```

Rapor ve sunum kontrolleri: `reports/check_report.py`, `presentation/check_deck.py`. Not: Windows'ta `python -c "..."` ile çok satırlı/Türkçe karakterli kod çalıştırmak sorun çıkarır; betik dosyası kullanın.

## Klasör Yapısı

| Yol | Açıklama |
|---|---|
| `data/` | Veri kaynağı ve envanter dosyaları (`DATA_SOURCE.md`); ham/işlenmiş veri dosyaları boyut nedeniyle pakette yoktur, "Çalıştırma" adımlarıyla indirilip üretilir |
| `src/` | Veri, pencereleme, modeller, eğitim, değerlendirme, karşılaştırma betikleri |
| `notebooks/` | Türkçe anlatımlı 5 notebook (EDA, hazırlık, baseline, derin öğrenme, karşılaştırma) |
| `results/metrics/` | Metrik CSV/JSON dosyaları (`summary.csv`, `kazanan_ozet.csv` vb.) |
| `results/figures/` | 200 dpi Türkçe etiketli figürler |
| `results/predictions/` | Kayıtlı test tahminleri |
| `results/models/` | Eğitilmiş model ağırlıkları (git dışı) |
| `reports/` | Word raporları (`rapor.docx`, LBLM368 şablonlu `rapor_lblm368.docx`) ve üretici/kontrol betikleri |
| `presentation/` | PPTX sunum (`sunum.pptx`), üretici ve kontrol betikleri |
| `tests/` | Birim testleri |
| `docs/` | Problem tanımı |

## Sonuçlar

<!-- SONUC_BASLA -->
Gündüz maskesi, test kümesi, RMSE (W); DL için 3 tohum ortalaması ± std (kaynak: `results/metrics/summary.csv`).

| Model | +1 saat RMSE (W) | +1 saat nRMSE | 16 adım ort. RMSE (W) | 16 adım ort. nRMSE |
|---|---|---|---|---|
| Persistence | 197,2 ± 0,0 | 0,197 | 304,6 ± 0,0 | 0,305 |
| Mevsimsel persistence | 246,9 ± 0,0 | 0,247 | 246,9 ± 0,0 | 0,247 |
| Doğrusal regresyon | 148,2 ± 0,0 | 0,148 | 172,2 ± 0,0 | 0,172 |
| XGBoost | 134,0 ± 0,0 | 0,134 | 155,2 ± 0,0 | 0,155 |
| LSTM | 136,9 ± 0,8 | 0,137 | 154,1 ± 0,3 | 0,154 |
| CNN-LSTM | 137,9 ± 2,5 | 0,138 | 154,5 ± 0,8 | 0,154 |

**Dürüst karşılaştırma:** 30 kesitin 3'inde DL baseline'ı geçemedi, 23 belirsiz, 4 DL önde (gün-bloklu bootstrap, B=1000; kaynak: `results/metrics/kazanan_ozet.csv`).

| Kesit türü | DL baseline'ı geçemedi | Belirsiz | DL önde |
|---|---|---|---|
| ufuk | 2 | 1 | 1 |
| ufuk_ort | 0 | 1 | 0 |
| mevsim | 0 | 4 | 0 |
| hava | 0 | 2 | 1 |
| saat | 1 | 12 | 1 |
| ablasyon | 0 | 3 | 1 |

Ayrıntı: `results/yorum.md`, `reports/rapor.docx`
<!-- SONUC_BITIS -->

Teslim dosyaları: [Word raporu](reports/rapor.docx), [PowerPoint sunumu](presentation/sunum.pptx), [Yorum](results/yorum.md).

## Yapılan Adımların Kaydı

### Faz 1: Ortam ve veri edinimi

- uv ile Python 3.14 sanal ortamı, GPU'lu PyTorch (cu132, RTX 3060 doğrulandı), sabitlenmiş `requirements.txt`, merkezi `src/config.py`.
- PVDAQ sistem 4 için 2010-2024 yıl envanteri çıkarıldı; 2015-2016 seçildi, 731 günlük 1 dk veri 8 thread ile eksiksiz indirildi.
- Günlük CSV'ler tek ham parquet'e birleştirildi; gün, satır, -7999 yer tutucusu, birim ve saat dilimi doğrulandı.
- Kapasite (1 kW), lisans ve atıf `data/raw/DATA_SOURCE.md`'ye yazıldı.


### Faz 2: Temizleme, EDA, öznitelik ve pencereleme

- Ham 1 dk veri temizlenip sızıntısız 15 dk ızgaraya indirildi (68.352 satır, 9 girdi kanalı + `is_day`).
- Ay-segmentli train/val/test bölmesi; ölçekleyiciler yalnız train'e fit edildi.
- Segment içi 96 adım girdi, 16 adım çıkış pencereleri üretildi; birim testleri ve bütünlük kontrolleri eklendi.
- 10 Türkçe EDA figürü ve baştan sona çalışan `01_eda.ipynb` hazırlandı.


### Faz 3: Baseline ve derin öğrenme modelleri

- Ortak `evaluate()` (gece kuralı; MAE/RMSE/R2/nRMSE) ve dört baseline kuruldu.
- LSTM ve CNN-LSTM, elle batch'li, seed'li, early-stopping'li GPU eğitim döngüsüyle 3 seed eğitildi.
- 10 koşu tek metrik fonksiyonuyla ölçüldü; iki Türkçe notebook yürütüldü.
- Taslak rapor ve 7 slaytlık sunum taslağı üretildi (sayılar JSON dosyalarından okunur).


### Faz 4: Karşılaştırma ve hata analizi

- POA tabanlı açıklık indeksiyle test günleri Açık/Parçalı/Kapalı etiketlendi; sınıf bazında metrikler üretildi.
- Dört kümülatif öznitelik grubuyla ablasyon yapıldı (yalnız güç, +zaman, +ışınım, +sıcaklıklar).
- Yedi sabit adlı, 200 dpi Türkçe sonuç figürü yeniden eğitimsiz üretildi.
- Gün-bloklu bootstrap ile kesit bazında kazanan tablosu ve `results/yorum.md` oluşturuldu.


### Faz 5: Rapor, sunum ve son kontrol

- CR-01: karışık karar kuralı kaldırıldı; 30 kesitin tamamı ilgili maske ile gün-bloklu bootstrap'e bağlandı. CR-02: `ablation.py --only` artık mevcut CSV ile birleştirir.
- Word raporu (`reports/build_report.py`): sayılar CSV'lerden üretilir, IEEE kaynakça Crossref ile doğrulandı.
- Sunum (`presentation/build_deck.js`): 14 slayt, konuşmacı notlu, LibreOffice/Poppler ile görsel QA yapıldı.
- Beş notebook `nbconvert --execute --inplace` ile baştan hatasız yürütüldü; notebook 05 sonuç cümleleri CSV'den üretilir.
- Bu README ve sonuç bloğu üreticisi (`reports/readme_sonuc.py`) eklendi.


## Sınırlamalar

- Tek sistem (1 kW, Golden CO) ve iki yıllık veri; sonuçlar başka tesislere doğrudan genellenmez.
- Hava tahmini girdisi yoktur; yalnız geçmiş ölçümler kullanılır.
- Kazanan model seçimi test kümesi üzerinde raporlanmıştır (ayrı bir dış test kümesi yoktur); bu nedenle sonuçlar iyimser olabilir.
- Çoğu kesitte fark istatistiksel olarak belirsizdir; bkz. sonuç tablosu.

## Kaynaklar

- Veri seti: Deline vd. (2021), PVDAQ Public Datasets, https://doi.org/10.25984/1846021
- Akademik kaynakça (IEEE) için `reports/rapor.docx` içindeki "Kaynakça" bölümüne bakın.
