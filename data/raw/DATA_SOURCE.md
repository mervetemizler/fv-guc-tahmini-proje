# Veri Kaynağı: NREL PVDAQ Sistem 4

## Özet

Bu projede kullanılan veri, ABD Ulusal Yenilenebilir Enerji Laboratuvarı (NREL) tarafından yayımlanan **PVDAQ (Photovoltaic Data Acquisition) Public Datasets** koleksiyonunun **sistem 4** ("NREL x-Si -1") kaydıdır. Veri, Golden, Colorado'daki gerçek bir FV sistemden alınmış **gerçek ölçüm verisidir**; sentetik veya modellenmiş (simülasyon) veri değildir. Veri OEDI (Open Energy Data Initiative) veri gölünde anonim, herkese açık olarak yayımlanır.

- Gönderi sayfası: https://data.openei.org/submissions/4568
- DOI: https://doi.org/10.25984/1846021

## Sistem

| Alan | Değer |
|---|---|
| Ad | NREL x-Si -1 (sistem 4) |
| Konum | Golden, CO, ABD |
| Enlem / Boylam | 39,7406 / -105,1774 |
| Rakım | 1795,3 m |
| Eğim / Azimut | 40° / 180° (sabit, güneye bakan, yer tipi) |
| Modüller | 5 adet Sanyo HIP-200BA3 (mono-Si, 200 W) |
| Evirici | 1 adet (model "1800") |
| DC kapasite | **1,0 kW** |
| Zaman dilimi | UTC-7 (Mountain Time) |

Kapasite kaynağı (`capacity_source`): `systems_20250729.csv` içindeki `dc_capacity_kW = 1` değeri; `4_system_metadata.json` içindeki `System.power = "1.0"` alanı ile tutarlıdır ve 5 x 200 W modül toplamıyla (1,0 kW) örtüşür. Metadata'daki `power` alanının birimi dosyada belirtilmediğinden birincil kaynak olarak CSV'deki `dc_capacity_kW` alınmıştır. Kapasite tahmin edilmemiştir. Yapılandırılmış kayıt: `data/raw/system_info.json`.

Not: Sistem listesindeki QA alanı "pass" olmakla birlikte şu uyarıları içerir: "Filtered time series less than 1.0 years data, Percent clipping exceeded threshold of 10%, Inconclusive orientation". Bu, 1 kW'lık küçük bir sistemde evirici kırpmasının (clipping) olabileceği anlamına gelir; Faz 2'de EDA'da incelenmelidir.

## Erişim

- Bucket kökü (anonim, HTTPS): `https://oedi-data-lake.s3.amazonaws.com`
- Listeleme URL deseni (S3 ListObjectsV2): `https://oedi-data-lake.s3.amazonaws.com/?list-type=2&prefix=pvdaq/csv/pvdata/system_id=4/year=YYYY/&max-keys=1000`
- Gün dosyası URL deseni: `https://oedi-data-lake.s3.amazonaws.com/pvdaq/csv/pvdata/system_id=4/year=YYYY/month=M/day=D/system_4__date_YYYY_MM_DD.csv` (yaklaşık 250 KB, 1440 satır = 1 dakikalık çözünürlük)
- Sistem metadata: `https://oedi-data-lake.s3.amazonaws.com/pvdaq/csv/system_metadata/4_system_metadata.json`
- Sistem listesi: `https://oedi-data-lake.s3.amazonaws.com/pvdaq/csv/systems_20250729.csv`

Yeniden üretme komutları (proje kökünden, yalnızca standart kütüphane, sistem Python'u):

```
python -I src/download_pvdaq.py probe --start 2010 --end 2024
python -I src/download_pvdaq.py download --years 2015 2016 --workers 8
python -I src/build_raw_parquet.py --years 2015 2016
```

İndirme 8 thread ile paralel yapılır; 5xx/429/bağlantı hatalarında 5 denemeye kadar üstel bekleme (1, 2, 4, 8 sn) uygulanır. Betik yeniden başlatılabilirdir (boyutu doğru olan dosyalar atlanır). Her dosya önce `.part` olarak yazılır, ilk satırın `measured_on` ile başladığı ve boyutun listedeki değerle eşleştiği doğrulanır.

## Seçilen Dönem

**Seçilen yıllar: 2015 ve 2016** (365 + 366 = 731 gün; veri 1 dakikalık çözünürlüktedir).

Canlı listeleme ile sayılan gün sayıları (2024 yılında veri yoktur):

| Yıl | Gün sayısı | Gerekli kolonlar |
|---|---|---|
| 2010 | 207 | hayır (poa_irradiance yok) |
| 2011 | 365 | evet |
| 2012 | 366 | evet |
| 2013 | 365 | evet |
| 2014 | 365 | evet |
| 2015 | 365 | evet |
| 2016 | 366 | evet |
| 2017 | 353 | evet |
| 2018 | 298 | evet |
| 2019 | 304 | evet |
| 2020 | 255 | evet |
| 2021 | 255 | evet |
| 2022 | 301 | evet |
| 2023 | 59 | evet |
| 2024 | 0 | hayır |

Seçim gerekçesi: Ardışık yıl çiftleri arasından, her iki yılı da gerekli kolonlara (ac_power, poa_irradiance, ambient_temp, module_temp_1) sahip olan ve en az 350 gün içerenler değerlendirildi; en küçük gün sayısı en büyük olan çift seçildi. (2011-2012), (2012-2013), (2013-2014), (2014-2015) ve (2015-2016) çiftleri 365 gün ile eşit çıktı; toplam gün sayısı da eşit (731) olduğundan kural gereği en yeni çift olan **2015-2016** seçildi. Ayrıntılar: `data/raw/year_inventory.json`, `data/raw/selected_years.json`.

## Değişkenler

Ham kolonlar (2015-2016; `__NNN` eki sensör kimliğidir ve yıllara göre değişebilir, bu yüzden kolonlar ön ekle seçilmelidir):

| Kolon (ön ek) | Anlam | Birim |
|---|---|---|
| measured_on | Ölçüm zaman damgası (1 dk) | zaman |
| ac_power__315 | AC güç (hedef değişken adayı) | W (varsayım; birim metadata'da doğrulanamadı) |
| dc_power__314 | DC güç | W (varsayım; doğrulanamadı) |
| ac_current__319, ac_voltage__318 | AC akım / gerilim | A / V (varsayım; doğrulanamadı) |
| dc_pos_current__317, dc_pos_voltage__316 | DC akım / gerilim | A / V (varsayım; doğrulanamadı) |
| poa_irradiance__313 | Eğimli yüzey ışınımı (POA) | W/m² (varsayım; doğrulanamadı) |
| ambient_temp__320 | Ortam sıcaklığı | °C (varsayım; doğrulanamadı) |
| module_temp_1__321, module_temp_2__322, module_temp_3__323 | Modül sıcaklığı | °C (varsayım; doğrulanamadı) |
| inverter_temp__324, das_temp__325 | Evirici / veri toplayıcı sıcaklığı | °C (varsayım; doğrulanamadı) |
| das_battery_voltage__326, power_factor__327 | Yardımcı kanallar | V / birimsiz (doğrulanamadı) |
| system_id | Sistem kimliği | - |

Birimler `4_system_metadata.json` içinde yer almadığı için yukarıdaki birimler PVDAQ'ın olağan kullanımına dayanan varsayımlardır; Plan 01-04'te değer aralıklarıyla (ör. POA tepe değeri ~1000-1300, güç ≤ ~1000-1200) sağlaması yapılmıştır; aşağıdaki 'Doğrulama Sonuçları' bölümüne bakın.

- **Eksik değer işareti: -7999** (sensör verisi yok demektir; örneğin 2017'de module_temp_2/3 tamamen -7999). NaN'a çevrilmeden kullanılmamalıdır.
- Veri setinde **rüzgar hızı ve bağıl nem ölçümü yoktur** (sistem 4 için); kullanılabilir meteorolojik değişkenler ışınım (POA) ve ortam/modül sıcaklıklarıdır.

## Lisans

PVDAQ gönderi sayfasında (https://data.openei.org/submissions/4568) veri seti için ayrı bir lisans adı **doğrulanamadı** (sayfada "Publicly accessible" ibaresi bulunur). OpenEI sitesinin genel alt bilgisi "Content is available under Creative Commons Attribution 4.0 unless otherwise noted" der; bu nedenle koşullar, atıf yapılması şartıyla CC BY 4.0 benzeri kabul edilmiştir (doğrulanmamış varsayım). Veri ders amaçlı kullanılmakta, atıf aşağıda verilmektedir.

## Atıf

Gönderi sayfasındaki APA biçimli atıf (birebir):

> Deline, C., Perry, K., Deceglie, M., Muller, M., Sekulic, W., & Jordan, D. (2021). Photovoltaic Data Acquisition (PVDAQ) Public Datasets. [Data set]. Open Energy Data Initiative (OEDI). NREL. https://doi.org/10.25984/1846021

## Erişim Tarihi

2026-11-01

## Doğrulama Sonuçları

Doğrulama tarihi: 2026-11-01. Kaynak: `data/raw/raw_inventory.json` (`python -I src/build_raw_parquet.py --years 2015 2016` çıktısı).

| Yıl | Gün | Beklenen gün | Eksik gün | Satır | Gün başına satır (medyan) | Zaman aralığı |
|---|---|---|---|---|---|---|
| 2015 | 365 | 365 | 0 | 525.600 | 1440 (min 1440, maks 1440) | 2015-01-01 00:00:00 – 2015-12-31 23:59:00 |
| 2016 | 366 | 366 | 0 | 527.039 | 1440 (min 1439, maks 1440) | 2016-01-01 00:00:00 – 2016-12-31 23:59:00 |

Eksik tarih: yok (her iki yıl takvimdeki tüm günleri içeriyor). 2016'da 1 dakikalık tek bir ölçüm eksik (1.052.639 satır / 2 yıl; ardışık satırlar arasında bir tane 2 dakikalık boşluk). Yinelenen zaman damgası: 2015: 0, 2016: 0 (atılan).

**Gerekli kolonların gerçek adları** (iki yılda da aynı sensör ekleri; tek ek, birleştirme gerekmiyor):

- `ac_power` -> `ac_power__315`
- `dc_power` -> `dc_power__314`
- `poa_irradiance` -> `poa_irradiance__313`
- `ambient_temp` -> `ambient_temp__320`
- `module_temp_1` -> `module_temp_1__321`

Tamamen boş (-7999/NaN) kolon: yok.

**-7999 oranları** (yalnızca sıfırdan farklı olanlar; %0.00 yüzde 0.005'ten küçük, çok az sayıda satır demektir; listelenmeyen kolonlarda hiç yok):

| Kolon | -7999 oranı |
|---|---|
| ambient_temp__320 | %0.00 |
| dc_pos_current__317 | %0.00 |
| dc_power__314 | %0.00 |
| module_temp_1__321 | %2.54 |
| module_temp_2__322 | %2.54 |
| module_temp_3__323 | %2.54 |
| poa_irradiance__313 | %0.00 |

**Birim sağlaması (değer aralıkları, -7999 hariç):**

| Kolon | min | %99 | maks |
|---|---|---|---|
| ac_power__315 | -1.7 | 881.5 | 1158.8 |
| dc_power__314 | -7.0 | 953.1 | 1251.7 |
| poa_irradiance__313 | -1078.6 | 1131.7 | 1494.4 |
| ambient_temp__320 | -21.6 | 31.1 | 68.6 |
| module_temp_1__321 | -18.9 | 51.4 | 67.5 |

Yorum: POA %99 değeri ~1132, maks ~1494 (bulut yansıması) -> W/m² ile tutarlı. AC güç %99 ~881, maks ~1159 -> W ile tutarlı (kapasite 1,0 kW ile aynı büyüklük sırası; 1000 W'ı aşan ~460 dakikalık ölçüm var, kısa süreli aşırı yüklenme/ışınım artışı olabilir). Sıcaklıklar °C ile tutarlı. Bu bir değer aralığı sağlamasıdır; birimler metadata'dan doğrulanmış değildir.

Aykırı değer notu: gece POA ortalaması yaklaşık -3 W/m² (sensör ofseti); en uç POA minimumu -1078,6 (5 ölçüm, öğle saati, sensör hatası) -> Faz 2'de temizlenmeli.

**Zaman damgası saat dilimi (çıkarım):** Dakika çözünürlüğündeki gün içi ortalama profilden (inceleme WR-03 düzeltmesi; önceki saat kutulu hesap merkezi ~0,5 saat erken, ~11,25 olarak veriyordu) POA ağırlık merkezi **≈11,74 (11:44)**, 15 dk yumuşatılmış POA tepesi **≈11:26**, AC güç tepesi **≈11:27**; gündüz yaklaşık 05:30–18:30 arasında. Bu, damgaların UTC olmadığını (UTC olsaydı Golden, CO'da tepe ~18–19 civarı çıkardı) ve yerel saat olduğunu gösterir. Golden'ın boylamı (−105,18°) MST standart meridyenine (−105°) çok yakın olduğundan beklenen ortalama güneş öğlesi **MST (UTC-7) için ≈12:01**, MDT (UTC-6) için ≈13:01'dir (zaman denklemi nedeniyle yıl içinde ±~16 dk oynar; önceki sürümdeki "≈12:41" değeri hatalıydı). Gözlenen merkez (11:44) MST ile en tutarlıdır ve ham veride DST kaynaklı 60 dk boşluk/tekrar yoktur; yine de beklenen öğleden ~17 dk (merkez) ve ~35 dk (tepe) erken kalır. Bu fark öğleden sonra bulutluluğunun profili sabaha doğru çarpıtmasından ve/veya damga konvansiyonundan (aralık başı/sonu) kaynaklanabilir; kesin ofset **doğrulanamadı**. Faz 2'de hiçbir saat kaydırması yapılmadan damgalar 'yerel standart saat (büyük olasılıkla MST, yaz saati yok), kesin ofset doğrulanmadı' olarak ele alınmalıdır.

**Parquet:** `pvdaq_sys4_2015_2016.parquet` (112.6 MB, gitignored; ham değerler, -7999 dahil, değiştirilmedi).

Kapasite: capacity_kw = 1.0 (system_info.json) — Faz 3 nRMSE paydası için kullanılabilir.

**Faz 2 için notlar:** -7999 -> NaN; gece negatif POA (~-3 W/m²) sıfıra kırpılmalı ya da ofset düzeltilmeli; uç POA aykırı değerleri temizlenmeli; module_temp_1/2/3'te %2,54 eksik; 1 dk veri 15 dk ızgaraya yeniden örneklenmeli (eksik dakikalar için reindex); POA dışında rüzgar/nem yok.

**Not (Faz 2):** 105°W meridyeni ve UTC-7 için Golden'da yerel güneş öğlesi ≈ 12:00–12:01'dir; önceki 12:41 değeri hatalıydı. UTC-7 varsayımı güneş yüksekliği>0 ↔ POA>20 uyumu %99,8 ile desteklenir. Veri 2016-12-13 00:00'da kesilmiştir (`config.DATA_END`; module_temp_1 eksik, invertör kapalı).
