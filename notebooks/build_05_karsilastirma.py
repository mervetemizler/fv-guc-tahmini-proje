# -*- coding: utf-8 -*-
"""notebooks/05_karsilastirma.ipynb dosyasını üretir (nbformat). Eğitim veya yeniden hesap yok; yalnızca kayıtlı çıktıları okur."""
import sys
from pathlib import Path

import nbformat as nbf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {"name": "pv-forecast", "display_name": "pv-forecast", "language": "python"}
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
SETUP = ("import sys, json, glob, subprocess\nfrom pathlib import Path\n"
         "PROJECT_ROOT = Path.cwd().resolve()\n"
         "if not (PROJECT_ROOT / 'src').exists():\n    PROJECT_ROOT = PROJECT_ROOT.parent\n"
         "sys.path.insert(0, str(PROJECT_ROOT))\n"
         "import numpy as np, pandas as pd\nimport matplotlib.pyplot as plt\n"
         "from IPython.display import Image, Markdown, display\n"
         "from src import config, analysis\n"
         "config.apply_plot_style()\nprint(config.summary())\n"
         "M = config.METRICS_DIR\n"
         "def fig(key):\n    display(Image(filename=str(config.FIGURES_DIR / analysis.FIGURES[key])))")

nb.cells = [
    md("# 05 — Karşılaştırma ve Hata Analizi\n\nBu notebook Faz 4 bulgularını (EVAL-03..07) tek yerde toplar: "
       "standart sonuç figürleri, model karşılaştırması, ufuk eğrisi, öznitelik ablasyonu, hava koşulu analizi, "
       "gün-bloklu bootstrap anlamlılığı ve dürüst yorum. **Eğitim veya yeniden hesaplama yapılmaz**; "
       "yalnızca kayıtlı CSV/PNG dosyaları okunur."),
    code(SETUP),
    md("## 1. Standart figürler"),
    md("### Kayıp eğrileri"),
    code("fig('kayip')"),
    md("Eğitim kaybı düşmeye devam ederken doğrulama kaybı erken düzleşir; erken durdurma bu yüzden kullanılmıştır."),
    md("### Örnek günlerde tahmin ve gerçek"),
    code("fig('tahmin')"),
    md("Açık, parçalı ve kapalı birer örnek gün (KT medyanına en yakın test günleri; model hatasına bakılarak seçilmemiştir). "
       "Parçalı günde modeller ani düşüşleri geriden izler."),
    md("### Saate göre hata"),
    code("fig('saat')"),
    code(r'''h = pd.read_csv(M / 'hour_metrics.csv'); h = h[h['n'] >= 30]
hm = h.groupby(['saat', 'model'])['RMSE_W'].mean().unstack()
zs = hm.mean(axis=1).idxmax()
dl = hm.loc[zs, ['lstm', 'cnn_lstm']].idxmin()
display(Markdown(f"Model ortalaması hatası en yüksek saat {int(zs):02d}:00'dır. Bu saatte XGBoost RMSE {hm.loc[zs, 'xgboost']:.1f} W, en iyi DL ({analysis.label(dl)}) {hm.loc[zs, dl]:.1f} W; fark {hm.loc[zs, dl] - hm.loc[zs, 'xgboost']:+.1f} W (DL - XGBoost)."))'''),
    md("### Model karşılaştırması"),
    code("fig('karsilastirma')"),
    code(r'''_s = pd.read_csv(M / 'summary.csv'); _s = _s[(_s['mask'] == 'day') & (_s['scope'] == 'mean16')].set_index('model')['RMSE_W_mean']
k = pd.read_csv(M / 'kazanan_ozet.csv'); _r = k[k['kesit_turu'] == 'ufuk_ort'].iloc[0]
display(Markdown(f"16-ufuk ortalamasında RMSE: LSTM {_s['lstm']:.1f} W, CNN-LSTM {_s['cnn_lstm']:.1f} W, XGBoost {_s['xgboost']:.1f} W, Doğrusal regresyon {_s['linreg']:.1f} W, persistence {_s['persistence']:.1f} W. "
                 f"En iyi DL ile en iyi baseline farkı {_r['fark_W']:+.1f} W; %95 GA [{_r['ci_low']:.1f}, {_r['ci_high']:.1f}]; karar: {_r['dl_baseline_gecti']} ({_r['karar_olcutu']})."))'''),
    md("## 2. Model karşılaştırma tablosu (gündüz, RMSE W / nRMSE)"),
    code("s = pd.read_csv(M / 'summary.csv')\n"
         "d = s[s['mask'] == 'day'].copy()\n"
         "order = [m for m in analysis.MODEL_ORDER if m in set(d['model'])]\n"
         "rm = d.pivot(index='model', columns='scope', values='RMSE_W_mean').loc[order].round(1)\n"
         "sd = d.pivot(index='model', columns='scope', values='RMSE_W_std').loc[order].round(1)\n"
         "nr = d.pivot(index='model', columns='scope', values='nRMSE_mean').loc[order].round(4)\n"
         "print('RMSE_W (ortalama)'); print(rm.to_string()); print('\\nRMSE_W (seed std; baseline tek koşu = 0)'); print(sd.to_string())\n"
         "print('\\nnRMSE (ortalama)'); print(nr.to_string())"),
    md("## 3. Ufuk eğrisi"),
    code("fig('ufuk')"),
    code("print(pd.read_csv(M / 'ufuk_tablosu.csv').round(1).to_string(index=False))"),
    code(r'''_u = k[k['kesit_turu'] == 'ufuk']
_satir = [f"- {r.kesit}: kazanan {analysis.label(r.en_iyi_model)}, DL baseline'ı geçti mi: {r.dl_baseline_gecti} (fark {r.fark_W:+.1f} W, GA [{r.ci_low:.1f}, {r.ci_high:.1f}])" for r in _u.itertuples()]
_nl = chr(10)
display(Markdown(f"Ufuk bazında kazananlar:{_nl}{_nl}{_nl.join(_satir)}"))'''),
    md("## 4. Öznitelik ablasyonu"),
    code("fig('ablasyon')"),
    code("a = pd.read_csv(M / 'ablation_summary.csv')\n"
         "a = a[(a['mask'] == 'day') & (a['scope'] == 'mean16')]\n"
         "print(a.pivot(index='grup', columns='model', values='RMSE_W_mean').round(1).to_string())\n"
         "print('\\nkatki_W (bir önceki gruba göre; negatif = iyileşme)')\n"
         "print(a.pivot(index='grup', columns='model', values='katki_W').round(2).to_string())"),
    code(r'''_c = a[a['grup'] == 'C_isinim'].set_index('model')['katki_W']
_ab = k[k['kesit_turu'] == 'ablasyon'].set_index('kesit')['dl_baseline_gecti']
_kat = ', '.join(f"{analysis.label(m)} {_c[m]:+.1f} W" for m in ('lstm', 'cnn_lstm') if m in _c.index)
display(Markdown(f"Işınım grubu (C) katkısı (bir önceki gruba göre): {_kat}. Ablasyon kesit kararları: " + '; '.join(f'{g} = {v}' for g, v in _ab.items()) + ". XGBoost ve Doğrusal regresyon tek koşudur; bu modeller için seed std yoktur."))'''),
    md("## 5. Hava koşuluna göre hata"),
    code("fig('hava')"),
    code("wd = pd.read_csv(M / 'weather_days.csv')\n"
         "print('Tüm günler:'); print(wd['sinif_ad'].value_counts().to_string())\n"
         "print('\\nTest günleri:'); print(wd[wd['test_gunu']]['sinif_ad'].value_counts().to_string())\n"
         "w = pd.read_csv(M / 'weather_metrics.csv')\n"
         "w = w[w['scope'] == 'mean16']\n"
         "pv = w.groupby(['sinif_ad', 'model'])['RMSE_W'].mean().unstack().reindex(columns=analysis.MODEL_ORDER).round(1)\n"
         "print('\\nRMSE_W (16-ufuk ortalaması)'); print(pv.to_string())"),
    code(r'''_tc = wd[wd['test_gunu']]['sinif_ad'].value_counts()
_hv = k[k['kesit_turu'] == 'hava']
_sat = '; '.join(f"{r.kesit}: kazanan {analysis.label(r.en_iyi_model)}, karar {r.dl_baseline_gecti}" for r in _hv.itertuples())
display(Markdown(f"Test günü sayıları: " + ', '.join(f'{i} {n}' for i, n in _tc.items()) + '. ' + _sat + '.'))'''),
    md("## 6. Anlamlılık: gün-bloklu bootstrap (B = 1000)\nFark = model_a - model_b (negatif: model_a daha iyi)."),
    code("b = pd.read_csv(M / 'bootstrap_fark.csv')\nprint(b.round(2).to_string(index=False))"),
    md("## 7. Dürüstlük: kesit bazında kazanan\n\nKazanan seçimi test kümesinde yapılmıştır, çoklu karşılaştırma düzeltmesi yoktur "
       "(bkz. yorum.md Yöntem Notu). Karar tüm kesitlerde gün-bloklu bootstrap ile verilir (karar_olcutu sütunu)."),
    code("k = pd.read_csv(M / 'kazanan_ozet.csv')\n"
         "print(k['karar_olcutu'].value_counts().to_string())\n"
         "print(k['dl_baseline_gecti'].value_counts().to_string())\n"
         "print()\nprint(k.round(2).to_string(index=False))"),
    code("print('DL baseline\\'ı geçemedi (hayır):')\n"
         "print(k[k['dl_baseline_gecti'] == 'hayır'][['kesit_turu', 'kesit', 'en_iyi_baseline', 'baseline_RMSE_W', 'en_iyi_dl', 'dl_RMSE_W', 'fark_W']].round(1).to_string(index=False))"),
    md("## 8. Yorum"),
    code("display(Markdown((PROJECT_ROOT / 'results' / 'yorum.md').read_text(encoding='utf-8')))"),
    md("## 9. Birim testleri"),
    code("for t in ('test_weather.py', 'test_ablation.py', 'test_compare.py', 'test_yorum.py'):\n"
         "    r = subprocess.run([sys.executable, '-I', str(PROJECT_ROOT / 'tests' / t)], capture_output=True, text=True, encoding='utf-8', cwd=PROJECT_ROOT)\n"
         "    print(t, '->', r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])\n"
         "    assert 'TESTLER_TAMAM' in r.stdout, r.stderr[-500:]"),
]
out = Path(__file__).resolve().parent / "05_karsilastirma.ipynb"
nbf.write(nb, out)
print("YAZILDI", out)
