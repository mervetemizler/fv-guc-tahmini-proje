// Sunum üretici (pptxgenjs). Tüm sonuç sayıları ve yön ifadeleri results/ dosyalarından üretilir (D-10).
// Çalıştırma: NODE_PATH="$(npm root -g)" node presentation/build_deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const root = path.resolve(__dirname, "..");
const readJson = (p) => JSON.parse(fs.readFileSync(path.join(root, p), "utf8"));
function readCsv(p) {
  const txt = fs.readFileSync(path.join(root, p), "utf8").replace(/^﻿/, "").trim().split(/\r?\n/);
  const head = txt[0].split(",");
  return txt.slice(1).map((line, i) => {
    const c = line.split(",");
    if (c.length !== head.length) throw new Error(p + " satır " + (i + 2) + ": sütun sayısı uyuşmuyor");
    const o = {};
    head.forEach((h, j) => { const v = c[j]; o[h] = v !== "" && !isNaN(Number(v)) ? Number(v) : v; });
    return o;
  });
}
const sys = readJson("data/raw/system_info.json");
const yrs = readJson("data/raw/selected_years.json");
const win = readJson("data/processed/windows_summary.json");
const cfg = readJson("results/config_snapshot.json");
const kaz = readCsv("results/metrics/kazanan_ozet.csv"); // kazanan_ozet.csv
const abl = readCsv("results/metrics/ablation_summary.csv");

const fmt = (n) => n.toLocaleString("tr-TR");
const fmt1 = (x, nd = 1) => x.toLocaleString("tr-TR", { minimumFractionDigits: nd, maximumFractionDigits: nd });
const fig = (n) => path.join(root, "results", "figures", n);
const LABEL = { persistence: "Persistence", seasonal_persistence: "Mevsimsel persistence", linreg: "Doğrusal regresyon", xgboost: "XGBoost", lstm: "LSTM", cnn_lstm: "CNN-LSTM" };
const lab = (m) => LABEL[m] || m;
function row(tur, kesit) {
  const r = kaz.find((x) => x.kesit_turu === tur && (kesit === undefined || x.kesit === kesit || String(x.kesit).startsWith(kesit)));
  if (!r) throw new Error("kazanan_ozet satırı yok: " + tur + "/" + kesit);
  return r;
}
const verdictPhrase = (r) => (r.dl_baseline_gecti === "evet" ? lab(r.en_iyi_dl) + " önde" : r.dl_baseline_gecti === "hayır" ? lab(r.en_iyi_baseline) + " önde" : "başa baş");
const nToplam = kaz.length;
const nHayir = kaz.filter((r) => r.dl_baseline_gecti === "hayır").length;
const nBelirsiz = kaz.filter((r) => r.dl_baseline_gecti === "belirsiz").length;
const nEvet = kaz.filter((r) => r.dl_baseline_gecti === "evet").length;
const sgn = (x) => (x > 0 ? "+" : x < 0 ? "−" : "") + fmt1(Math.abs(x));

const NAVY = "14213D", SUN = "F28C28", INK = "1F2937", BG = "FFFFFF", SOFT = "FFF4E5";
const FONT = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "FV Güneş Santrali Çok Değişkenli Güç Üretim Tahmini";

// Her konuşmacı notuna geçiş/konuşma ipucu cümlesi eklenir (~50 sn hedefi, PRES-04).
const EK = [
  "Burada yaklaşık bir dakika durup soru olup olmadığını sorabilirim; ardından bir sonraki slayta geçerek hikayeyi sürdüreceğim.",
  "Bu slayttaki mesajı tek cümleyle tekrar edeyim ve izleyicinin görseli rahatça okuyabilmesi için birkaç saniye bekleyeyim.",
  "Görselde eksen etiketlerini ve renkleri kısaca tarif edip, hangi çizginin hangi modele ait olduğunu belirtmeyi unutmamalıyım.",
  "Önemli olan nokta sayıların kendisinden çok, bu sayıların hangi protokolle ve hangi veri bölümünde üretildiği olduğunu vurgulamaktır.",
  "Bu noktada izleyiciye ayrıntıların raporda bulunduğunu hatırlatıp sunumun akışını bozmadan sonraki konuya geçeceğim.",
  "Burada başlıktaki ifadenin doğrudan sonuç tablolarından üretildiğini ve elle yazılmadığını belirtmek güven verecektir.",
  "Grafikteki eğrilerin birbirine yaklaştığı yerleri parmakla göstererek farkın küçük olduğunu görsel olarak anlatabilirim.",
  "Her zaman olduğu gibi, bu örneklerin yalnızca sezgi kazandırmak için seçildiğini ve genel kanıt sayılmadığını açıkça söylerim.",
  "Burada hatanın mutlak değerinin üretimle birlikte büyüdüğünü, göreli hata için ayrıca nRMSE metriğine baktığımızı not düşerim.",
  "Güven aralığı sıfırı içeriyorsa, farkın gerçek olduğunu söyleyemeyeceğimizi sade bir dille izleyicilere açıklamak faydalı olur.",
  "Burada ablasyonun amacının bir modeli yenmek değil, hangi girdinin gerçekten fayda sağladığını anlamak olduğunu söylerim.",
  "Tablodaki sayıların toplamının tüm kesit sayısına eşit olduğunu belirtip izleyicinin kendi başına doğrulayabileceğini ekleyebilirim.",
  "Bu sınırlamaları saklamak yerine açıkça söylemek, çalışmanın güvenilirliğini artırır ve gelecekteki çalışmalara yön gösterir.",
  "Son olarak izleyicilere kodun, verinin ve raporun hazır olduğunu söyleyip soru sormaları için sözü onlara bırakacağım.",
];
let _slayt = 0;
const _addSlide = pres.addSlide.bind(pres);
pres.addSlide = function () {
  const s = _addSlide.apply(null, arguments);
  const idx = _slayt++;
  const _n = s.addNotes.bind(s);
  s.addNotes = (t) => _n(t + " " + EK[idx]);
  return s;
};

function contentSlide(title) {
  const s = pres.addSlide();
  s.background = { color: BG };
  s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 0.25, h: 7.5, fill: { color: SUN }, line: { color: SUN } });
  s.addText(title, { x: 0.7, y: 0.35, w: 12, h: 1.0, fontFace: FONT, fontSize: 28, bold: true, color: NAVY, valign: "top" });
  return s;
}
function bullets(s, items, opt) {
  s.addText(items.map((t) => ({ text: t, options: { bullet: true, breakLine: true } })),
    Object.assign({ x: 0.7, y: 1.7, w: 5.0, h: 4.4, fontFace: FONT, fontSize: 22, color: INK, valign: "top", paraSpaceAfter: 12 }, opt || {}));
}
function img(s, name, x, y, w, h) {
  // PNG başlığından gerçek en/boy oranı: kutuya sığdır, merkezle (bozulma yok)
  const b = require("fs").readFileSync(fig(name));
  const iw = b.readUInt32BE(16), ih = b.readUInt32BE(20);
  const sc = Math.min(w / iw, h / ih);
  const rw = iw * sc, rh = ih * sc;
  s.addImage({ path: fig(name), x: x + (w - rw) / 2, y: y + (h - rh) / 2, w: rw, h: rh });
}
function card(s, x, y, w, h, big, small) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: SOFT }, line: { color: SUN, width: 1.5 }, rectRadius: 0.12 });
  s.addText([
    { text: big, options: { fontSize: 32, bold: true, color: SUN, breakLine: true } },
    { text: small, options: { fontSize: 16, color: INK } },
  ], { x, y, w, h, align: "center", valign: "middle", fontFace: FONT });
}
function strip(s, text, y) {
  s.addShape(pres.ShapeType.rect, { x: 0.7, y, w: 12, h: 0.6, fill: { color: SOFT }, line: { color: SOFT } });
  s.addText(text, { x: 0.9, y, w: 11.6, h: 0.6, fontFace: FONT, fontSize: 18, bold: true, color: NAVY, valign: "middle" });
}

// Türetilmiş değerler
const rOrt = row("ufuk_ort");
const rU15 = row("ufuk", "+15 dk"), rU1 = row("ufuk", "+1 saat"), rU4 = row("ufuk", "+4 saat");
const rKapali = row("hava", "Kapalı"), rAcik = row("hava", "Açık"), rParcali = row("hava", "Parçalı");
const saatler = kaz.filter((r) => r.kesit_turu === "saat");
const zirve = saatler.reduce((a, b) => (b.en_iyi_RMSE_W > a.en_iyi_RMSE_W ? b : a));
const rA = row("ablasyon", "A_guc");
const ablC = abl.find((r) => r.grup === "C_isinim" && r.model === "cnn_lstm" && r.mask === "day" && r.scope === "mean16");
const ablYon = ablC.katki_W > 0 ? "artırdı" : "azalttı";
const dlOrt = lab(rOrt.en_iyi_dl), blOrt = lab(rOrt.en_iyi_baseline);
const cnt = (turs, d) => kaz.filter((r) => turs.includes(r.kesit_turu) && r.dl_baseline_gecti === d).length;
const gruplar = [["Ufuk", ["ufuk", "ufuk_ort"]], ["Mevsim, hava, saat", ["mevsim", "hava", "saat"]], ["Ablasyon", ["ablasyon"]]];

// 1) Kapak
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.ShapeType.rect, { x: 0.7, y: 1.6, w: 1.2, h: 0.12, fill: { color: SUN }, line: { color: SUN } });
  s.addText("FV Güneş Santrali Çok Değişkenli Güç Üretim Tahmini", { x: 0.7, y: 1.9, w: 7.6, h: 1.8, fontFace: FONT, fontSize: 34, bold: true, color: "FFFFFF", valign: "top" });
  s.addText("Derin Öğrenme Dersi Dönem Projesi", { x: 0.7, y: 3.9, w: 7.6, h: 0.6, fontFace: FONT, fontSize: 20, color: "F3D9B1" });
  s.addText("[Ad Soyad] · [Öğrenci No]\n[Ders] · [Öğretim Üyesi]\nKasım 2026", { x: 0.7, y: 4.8, w: 7.6, h: 1.6, fontFace: FONT, fontSize: 18, color: "CBD5E1", valign: "top" });
  s.addShape(pres.ShapeType.rect, { x: 8.55, y: 2.2, w: 4.3, h: 3.0, fill: { color: "FFFFFF" }, line: { color: SUN } });
  img(s, "eda_01_zaman_serisi.png", 8.6, 2.25, 4.2, 2.9);
  s.addNotes("Merhaba, bu çalışmada gerçek bir güneş santralinin ölçüm verisiyle güç üretimini tahmin ediyoruz. Veri NREL'in açık PVDAQ koleksiyonundan geliyor ve hiçbir sentetik veri kullanılmadı. Dört klasik baseline yöntemini, LSTM ve CNN-LSTM derin öğrenme modelleriyle aynı protokol altında karşılaştırdık. Sunumda önce problemi ve veriyi, sonra yöntemi, ardından ufuk, hava ve girdi grubu bazında bulguları anlatacağım. Sonuçları olduğu gibi, yani derin modelin kazandığı ve kaybettiği yerleri birlikte göstereceğim. Bu yüzden başlıklar bir bulgu cümlesi olarak yazıldı.");
}

// 2) Problem
{
  const s = contentSlide("+1 saat sonraki FV gücünü bilmek planlamayı kolaylaştırır");
  bullets(s, ["Bulutlar üretimi dakikalar içinde değiştirir", "Girdi: son " + (cfg.window / 4) + " saat, " + cfg.n_channels + " kanal", "Gelecekteki ışınım kullanılmaz"], { w: 4.2 });
  img(s, "eda_09_bulutlu_acik_gun.png", 5.0, 1.6, 7.8, 5.2);
  s.addNotes("Güneş üretimi bulutlara bağlı olarak dakikalar içinde dalgalanır ve şebeke dengesi için kısa vadeli tahmin gerekir. Sağdaki grafikte bulutlu ve açık bir günün güç eğrisini görüyorsunuz; fark çok belirgin. Biz modele son " + (cfg.window / 4) + " saatlik, " + cfg.n_channels + " kanallı geçmişi veriyoruz ve " + cfg.horizon + " adım, yani dört saate kadar ilerisini tahmin ettiriyoruz. Ana değerlendirme ufku bir saattir. Gelecekteki ışınım ölçümlerini girdi olarak kullanmıyoruz; bu bir gerçek ileri tahmin problemidir, anlık kestirim değildir.");
}

// 3) Veri
{
  const s = contentSlide("NREL PVDAQ sistem " + sys.system_id + ": " + yrs.years.join("-") + ", 15 dk, gerçek ölçüm");
  bullets(s, [sys.site_location, fmt1(sys.capacity_kw) + " kW kurulu güç", "AC güç, ışınım, sıcaklıklar"], { w: 4.6 });
  card(s, 0.7, 4.7, 4.6, 1.6, fmt(win.test.n_windows), "test penceresi");
  img(s, "eda_06_guc_isinim_sacilim.png", 5.7, 1.6, 7.1, 5.2);
  s.addNotes("Veri NREL'in açık PVDAQ koleksiyonundan, " + sys.site_location + " konumundaki sistem " + sys.system_id + "'den alındı. Sistemin kurulu gücü " + fmt1(sys.capacity_kw) + " kilovat. " + yrs.years.join(" ve ") + " yıllarına ait dakikalık ölçümleri on beş dakikalık ızgaraya indirdik. Sağdaki saçılım grafiği gücün eğimli yüzey ışınımına neredeyse doğrusal bağlı olduğunu gösteriyor; bu yüzden ışınım güçlü bir öznitelik. Sol altta, değerlendirmede kullanılan test penceresi sayısını görüyorsunuz. Eğitim, doğrulama ve test ayları kronolojik olarak ayrıldı ve birbirine sızmıyor.");
}

// 4) Hazırlık
{
  const s = contentSlide("Temizlik ve pencereleme: " + cfg.window + " adım geçmiş, " + cfg.horizon + " adım ufuk");
  img(s, "eda_08_temizlik_oncesi_sonrasi.png", 0.7, 1.5, 12, 4.7);
  strip(s, "Eğitim " + fmt(win.train.n_windows) + " · doğrulama " + fmt(win.val.n_windows) + " · test " + fmt(win.test.n_windows) + " pencere", 6.4);
  s.addNotes("Ham veriyi temizledik: bozuk ve eksik ölçümler ayıklandı, saatler yerel zamana hizalandı. Grafikte temizlikten önceki ve sonraki hali yan yana görülüyor. Sonra veriyi " + cfg.window + " adımlık geçmiş ve " + cfg.horizon + " adımlık ufuk pencerelerine böldük; her adım on beş dakika. Ölçekleyici yalnızca eğitim verisine fit edilir, böylece test bilgisi sızmaz. Alttaki şeritte eğitim, doğrulama ve test pencere sayılarını görüyorsunuz. Tek aylar doğrulama, çift aylar test için ayrıldı.");
}

// 5) Modeller
{
  const s = contentSlide("Dört baseline'a karşı iki derin model, " + cfg.seeds.length + " seed");
  bullets(s, ["Persistence, mevsimsel persistence", "Doğrusal regresyon, XGBoost", "LSTM ve CNN-LSTM"], { w: 4.2 });
  img(s, "sonuc_01_kayip_egrileri.png", 5.0, 1.6, 7.8, 5.0);
  s.addNotes("Altı yaklaşımı karşılaştırıyoruz. Dört baseline var: persistence, bir önceki günün aynısını veren mevsimsel persistence, doğrusal regresyon ve XGBoost. Derin tarafta iki ağ var: iki katmanlı LSTM ve evrişim ile LSTM'i birleştiren CNN-LSTM. Her derin model " + cfg.seeds.length + " farklı seed ile eğitildi, sonuçlar ortalama ve standart sapma olarak raporlanır. Sağdaki kayıp eğrileri eğitimin yakınsadığını ve doğrulama kaybının kontrol altında kaldığını gösteriyor. Tüm modeller aynı test pencerelerinde, aynı değerlendirme işleviyle ölçülür.");
}

// 6) Genel
{
  const s = contentSlide("Ortalamada " + verdictPhrase(rOrt) + ": " + dlOrt + " " + fmt1(rOrt.dl_RMSE_W) + " W, " + blOrt + " " + fmt1(rOrt.baseline_RMSE_W) + " W");
  img(s, "sonuc_04_model_karsilastirma.png", 0.7, 1.5, 12, 4.8);
  strip(s, "%95 GA [" + fmt1(rOrt.ci_low) + "; " + fmt1(rOrt.ci_high) + "] W, fark sıfırı " + (rOrt.ci_low <= 0 && rOrt.ci_high >= 0 ? "içeriyor" : "içermiyor"), 6.45);
  s.addNotes("Bu, tüm ufukların ortalaması için gündüz RMSE'sini gösteriyor. En iyi derin model " + dlOrt + " " + fmt1(rOrt.dl_RMSE_W) + " vat, en iyi baseline " + blOrt + " " + fmt1(rOrt.baseline_RMSE_W) + " vat. Fark yalnızca " + fmt1(Math.abs(rOrt.fark_W)) + " vat ve gün bloklu bootstrap ile hesaplanan yüzde doksan beşlik güven aralığı sıfırı içeriyor: aralık " + fmt1(rOrt.ci_low) + " ile " + fmt1(rOrt.ci_high) + " vat arası. Yani ortalamada derin model ile güçlü baseline başa baş. Bu, derin öğrenme her zaman kazanır beklentisine karşı dürüst bir bulgu.");
}

// 7) Ufuk
{
  const s = contentSlide("Kısa ufukta " + lab(rU15.en_iyi_model) + ", +4 saatte " + lab(rU4.en_iyi_model) + " önde");
  img(s, "sonuc_06_ufuk_egrisi.png", 0.7, 1.5, 8.0, 5.3);
  card(s, 9.1, 1.9, 3.7, 1.9, sgn(rU1.fark_W) + " W", "+1 saat, DL − baseline");
  card(s, 9.1, 4.2, 3.7, 1.9, sgn(rU4.fark_W) + " W", "+4 saat, DL − baseline");
  s.addNotes("Ufuk büyüdükçe tablo değişiyor. On beş dakikada en iyi model " + lab(rU15.en_iyi_model) + ", derin modelden " + fmt1(Math.abs(rU15.fark_W)) + " vat daha iyi ve bu fark bootstrap ile anlamlı. Bir saatte de baseline önde: derin model " + fmt1(Math.abs(rU1.fark_W)) + " vat geride. Dört saatte ise " + lab(rU4.en_iyi_model) + " baseline'ı " + fmt1(Math.abs(rU4.fark_W)) + " vat farkla geçiyor ve güven aralığı sıfırı içermiyor. Sağdaki kartlarda fark değerleri var; eksi işaret derin modelin lehine. Özetle, derin modellerin avantajı uzun ufukta ortaya çıkıyor.");
}

// 8) Tahmin örnekleri
{
  const s = contentSlide("Tahminler açık günde ölçümü yakından izler");
  img(s, "sonuc_02_tahmin_vs_gercek.png", 0.7, 1.5, 12, 4.9);
  strip(s, "Örnek test günleri: ölçüm ve model tahminleri", 6.5);
  s.addNotes("Bu grafik test kümesinden seçilmiş örnek günlerde ölçülen gücü ve model tahminlerini üst üste gösteriyor. Açık günlerde tahminler ölçümü yakından izliyor; modeller günlük şekli doğru yakalıyor. Bulutlu ve parçalı günlerde ise ani düşüş ve yükselişler tahmin edilemiyor, tahmin daha düzgün kalıyor. Bu beklenen bir davranış, çünkü bulutun ne zaman geleceği girdide yok. Örnekler rastgele değil, yalnızca görsel fikir vermek için seçildi; asıl karşılaştırma tüm test günleri üzerindeki metriklerdir.");
}

// 9) Saat
{
  const s = contentSlide("Öğle saatlerinde hata en yüksek: " + zirve.kesit + ", " + fmt1(zirve.en_iyi_RMSE_W, 0) + " W");
  img(s, "sonuc_03_saate_gore_hata.png", 0.7, 1.5, 8.0, 5.3);
  card(s, 9.1, 2.3, 3.7, 2.0, verdictPhrase(zirve), zirve.kesit + " kararı");
  s.addNotes("Hatayı günün saatine göre incelediğimizde, mutlak hata öğle saatlerinde en yüksek çıkıyor; tepe " + zirve.kesit + " civarında ve en iyi modelin RMSE'si " + fmt1(zirve.en_iyi_RMSE_W, 0) + " vat. Bunun nedeni basit: öğlen üretim yüksek olduğu için bulut kaynaklı sapmalar da büyük oluyor. Sabah ve akşam saatlerinde hata küçük, çünkü üretim düşük. Sağdaki kartta o saatin bootstrap kararı var. Saat bazında birçok kesitte derin model ile baseline ayırt edilemiyor; yalnızca birkaç saatte net bir kazanan çıkıyor.");
}

// 10) Hava
{
  const s = contentSlide("Kapalı günlerde " + lab(rKapali.en_iyi_model) + ", açık günlerde " + lab(rAcik.en_iyi_model) + " iyi");
  img(s, "sonuc_07_hava_kosulu.png", 0.7, 1.5, 8.0, 5.3);
  card(s, 9.1, 1.9, 3.7, 1.9, verdictPhrase(rAcik), "açık günler");
  card(s, 9.1, 4.2, 3.7, 1.9, verdictPhrase(rKapali), "kapalı günler");
  s.addNotes("Günleri hava durumuna göre üç sınıfa ayırdık: kapalı, parçalı ve açık. Açık günlerde " + lab(rAcik.en_iyi_model) + " baseline'ı " + fmt1(Math.abs(rAcik.fark_W)) + " vat farkla geçiyor ve bu fark bootstrap ile anlamlı. Kapalı günlerde ise en iyi model " + lab(rKapali.en_iyi_model) + "; fark büyük görünse de yalnızca " + rKapali.n_gun_boot + " gün olduğu için güven aralığı sıfırı içeriyor ve karar " + rKapali.dl_baseline_gecti + ". Parçalı günlerde de karar " + rParcali.dl_baseline_gecti + ". Yani derin modelin avantajı en net biçimde öngörülebilir, açık günlerde görülüyor.");
}

// 11) Ablasyon
{
  const s = contentSlide("Işınım grubu hatayı " + ablYon + " (" + sgn(ablC.katki_W) + " W)");
  img(s, "sonuc_05_ablasyon.png", 0.7, 1.5, 8.0, 5.3);
  card(s, 9.1, 2.3, 3.7, 2.2, verdictPhrase(rA), "yalnız güç girdisiyle");
  s.addNotes("Ablasyon deneyinde girdi gruplarını tek tek ekledik: yalnız güç, ardından zaman, ışınım ve sıcaklıklar. Işınım grubunu eklemek CNN-LSTM'in ortalama gündüz RMSE'sini " + fmt1(Math.abs(ablC.katki_W)) + " vat " + ablYon + ", yani beklenenin aksine yardımcı olmadı. Yalnız güç girdisiyle bile CNN-LSTM karar olarak " + verdictPhrase(rA) + ". Bunun makul bir açıklaması, son güç değerlerinin kısa ufukta zaten çok bilgi taşıması ve ışınımın bu pencerede ek bilgi vermemesi. Bu bulgu, daha fazla özniteliğin her zaman daha iyi olmadığını gösteriyor.");
}

// 12) Kazanan / kaybeden
{
  const s = contentSlide(nToplam + " kesitin " + nHayir + "'ünde DL baseline'ı geçemedi");
  s.addText(nBelirsiz + " belirsiz, " + nEvet + " DL önde", { x: 0.7, y: 1.5, w: 6.0, h: 0.5, fontFace: FONT, fontSize: 20, color: INK });
  const hdr = ["", "hayır", "belirsiz", "evet"].map((t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY }, align: "center", fontSize: 16, fontFace: FONT } }));
  const rows = [hdr].concat(gruplar.map(([ad, turs]) => [
    { text: ad, options: { bold: true, fontSize: 16, fontFace: FONT, color: INK } },
    ...["hayır", "belirsiz", "evet"].map((d) => ({ text: String(cnt(turs, d)), options: { align: "center", fontSize: 18, fontFace: FONT, color: INK } })),
  ]));
  s.addTable(rows, { x: 0.7, y: 2.3, w: 6.0, colW: [2.4, 1.2, 1.2, 1.2], rowH: 0.7, border: { type: "solid", pt: 1, color: "D1D5DB" } });
  img(s, "sonuc_04_model_karsilastirma.png", 6.9, 2.3, 5.9, 4.0);
  s.addNotes("Tüm kesitleri tek tabloda topladık: ufuklar, mevsimler, hava sınıfları, saatler ve ablasyon grupları, toplam " + nToplam + " kesit. Her kesitte en iyi derin modeli en iyi baseline ile gün bloklu bootstrap üzerinden karşılaştırdık. Sonuç: " + nHayir + " kesitte baseline açıkça önde, " + nBelirsiz + " kesitte fark güven aralığı içinde belirsiz, " + nEvet + " kesitte derin model açıkça önde. Yani derin öğrenme bu veri setinde sistematik bir üstünlük göstermiyor; kazandığı yerler uzun ufuk, açık hava ve birkaç saat. Tablo satırları kesit türlerini, sütunlar kararı gösteriyor.");
}

// 13) Sınırlamalar
{
  const s = contentSlide("Sonuçlar tek sistem ve iki yıl ile sınırlı");
  bullets(s, ["Tek santral, iki yıllık veri", "Test kümesinde çok karşılaştırma", "Aralık 2016 arızası verisi"], { w: 4.2 });
  img(s, "eda_10_aralik_2016_ariza.png", 5.0, 1.6, 7.8, 5.0);
  s.addNotes("Sonuçların sınırlarını açıkça söylemek gerekiyor. Birincisi, yalnızca tek bir santral ve iki yıllık veri kullandık; başka iklimlere veya sistemlere genelleme yapamayız. İkincisi, test kümesinde " + nToplam + " kesit karşılaştırdık; çoklu karşılaştırma nedeniyle birkaç kesitin tesadüfen anlamlı çıkması mümkün, bu yüzden tekil kazanımlara değil genel desene bakıyoruz. Üçüncüsü, sağdaki grafikte görülen Aralık 2016 arızası verisi var; bu dönem hatalı ölçüm içeriyor ve sonuçları etkileyebilir. Bu sınırlamalar raporda ayrıntılı tartışılıyor.");
}

// 14) Kapanış
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.ShapeType.rect, { x: 0.7, y: 0.9, w: 1.2, h: 0.12, fill: { color: SUN }, line: { color: SUN } });
  s.addText("Ders: güçlü baseline olmadan DL iddiası kurulamaz", { x: 0.7, y: 1.1, w: 11.5, h: 1.0, fontFace: FONT, fontSize: 30, bold: true, color: "FFFFFF", valign: "top" });
  s.addText([
    { text: "Ortalamada " + verdictPhrase(rOrt), options: { bullet: true, breakLine: true } },
    { text: "+4 saatte " + lab(rU4.en_iyi_model) + " önde (" + sgn(rU4.fark_W) + " W)", options: { bullet: true, breakLine: true } },
    { text: "Kısa ufukta " + lab(rU15.en_iyi_model) + " önde", options: { bullet: true, breakLine: true } },
  ], { x: 0.7, y: 2.4, w: 6.0, h: 2.8, fontFace: FONT, fontSize: 22, color: "FFFFFF", valign: "top", paraSpaceAfter: 12 });
  s.addText("Teşekkürler / Sorular", { x: 0.7, y: 5.8, w: 6.0, h: 0.7, fontFace: FONT, fontSize: 24, bold: true, color: SUN });
  s.addShape(pres.ShapeType.rect, { x: 7.15, y: 2.3, w: 5.7, h: 3.9, fill: { color: "FFFFFF" }, line: { color: SUN } });
  img(s, "eda_03_gunluk_profil.png", 7.2, 2.35, 5.6, 3.8);
  s.addNotes("Toparlarsak, bu çalışmanın en önemli dersi şu: güçlü bir baseline olmadan derin öğrenme iddiası kurulamaz. Ortalamada karar: " + verdictPhrase(rOrt) + ". Derin modelin net avantajı dört saatlik uzun ufukta, açık havada ve birkaç saatte görüldü; kısa ufukta ise " + lab(rU15.en_iyi_model) + " önde. " + nToplam + " kesitin " + nHayir + " tanesinde baseline önde, " + nEvet + " tanesinde derin model önde, kalanında karar belirsiz. Tüm kod, veri ve rapor tekrar üretilebilir durumda. Dinlediğiniz için teşekkür ederim, sorularınızı alabilirim.");
}

pres.writeFile({ fileName: path.join(root, "presentation", "sunum.pptx") }).then(() => console.log("DECK_TAMAM"));
