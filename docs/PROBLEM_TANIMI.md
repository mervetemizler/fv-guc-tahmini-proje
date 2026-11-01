# Problem Tanımı

## Amaç
Golden, CO'daki bir fotovoltaik (FV) sistemin (PVDAQ sistem 4) gerçek ölçüm verisiyle, geçmiş 24 saatlik çok değişkenli gözlemden gelecekteki AC güç üretimini tahmin etmek. Sahte/sentetik veri kullanılmaz.

## Hedef değişken
- Hedef: AC güç (`ac_power`), birim **W**.
- Kurulu kapasite `CAPACITY_W` = 1000 W (system_info.json: 1,0 kW). nRMSE = RMSE[W] / `CAPACITY_W`.

## Ufuk
- Çok çıkışlı tahmin: **1–16 adım** (her adım 15 dk, yani 15 dk – 4 saat).
- **Ana ufuk: +1 saat = 4. adım** (`MAIN_HORIZON_STEPS` = 4). Tüm ufuk adımları ayrıca raporlanır.

## Girdiler
- Son **96 adım = 24 saat** geçmiş pencere (`WINDOW` = 96), 9 kanal:
  - 4 ölçüm kanalı (D-06): `ac_power`, `poa_irradiance`, `ambient_temp`, `module_temp_1`.
  - 5 önceden bilinen zaman/güneş özniteliği (D-07): `hour_sin`, `hour_cos`, `doy_sin`, `doy_cos`, `sun_elevation`.
- Öznitelikler yalnızca geçmiş pencere adımları için verilir; **gelecek ufuk adımlarının öznitelikleri modele verilmez** (D-08).

## Temel kural: gerçek tahmin, nowcasting değil
**Gelecek ışınım/hava verisi kullanılmaz.** Model, tahmin anında yalnızca geçmiş gözlemleri görür; bu nedenle bu çalışma gerçek bir tahmindir (forecasting), **nowcasting değildir**.

## Veri dönemi
2015-01-01 – 2016-12-13 00:00 (`DATA_END`). Gerekçe: 2016-12-13 10:13'ten itibaren `module_temp_1` sürekli eksik ve 2016-12-14'ten itibaren invertör kapalı (POA 1000+ W/m² iken AC ≈ 3 W); bu günler fiziksel olarak tahmin edilemez. Veri 2016-12-13 00:00'da kesilmiştir; Aralık test segmenti 12 gündür. Izgara: 15 dk, 68.352 satır.

## Bölme ve sızıntı önlemleri
- D-01: Train = 2015 tamamı; 2016'da tek aylar (Oca, Mar, May, Tem, Eyl, Kas) = val, çift aylar (Şub, Nis, Haz, Ağu, Eki, Ara) = test. Her mevsim hem val hem test'te temsil edilir.
- D-02: Pencereler yalnızca ay-segmenti içinde üretilir; hiçbir pencere iki segmente yayılmaz. NaN içeren pencereler atılır (`MAX_GAP_IN_WINDOW` = 0).
- D-03: `check_split_integrity` assert'leri: test hedefleri train'den sonra, val ∩ test = ∅, segment-içi pencere, NaN yok.
- Dürüstlük notu: val ve test komşu aylardır; erken durdurma val'den gelir, hiperparametre testte ayarlanmaz.
- Right-closed/right-label 15 dk resample (t damgası yalnızca (t-15 dk, t] verisini içerir).
- Girdi ve hedef scaler'ları yalnızca train ızgara satırlarına fit edilir (35.040 satır).

## Gece kuralları
- D-10: Hedefleri tamamen geceye düşen pencereler train ve val'den atılır, test'te tutulur.
- D-11: Faz 3'te güneş yüksekliği ≤ 0 olan hedef adımlarında tahmin 0'a çekilir (tüm modellere aynı).

## Metrikler
Gündüz-yalnız metrikler birincil (POA > 20 W/m²), tüm saatler ikincil; ayrıca mevsim bazında ek tablo (D-05).

## Pencere sayıları (windows_summary.json)

| Split | Pencere sayısı | Tamamı-gece atılan |
|-------|----------------|--------------------|
| Train | 21.581 | 13.348 |
| Val   | 10.608 | 6.390 |
| Test  | 14.982 | 0 (tutuldu: 5.387 tamamı-gece pencere) |

Test mevsim dağılımı: Kış 3.714, İlkbahar 2.769, Yaz 5.634, Sonbahar 2.865.
Girdi tensörü X: (N, 96, 9); hedef y: (N, 16), W cinsinden.
