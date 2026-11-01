# -*- coding: utf-8 -*-
"""notebooks/04_derin_ogrenme.ipynb dosyasını üretir (nbformat)."""
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
         "from src import config, models\n"
         "config.apply_plot_style()\nprint(config.summary())")
nb.cells = [
    md("# Faz 3 - Derin Öğrenme Modelleri (LSTM ve CNN-LSTM)\n\nİki model, 3 seed ile GPU'da eğitilmiştir. "
       "Bu notebook eğitimi tekrarlamaz; kayıtlı kayıp geçmişlerini ve metrik tablolarını okur."),
    code(SETUP),
    md("## 1. Mimari ve parametre sayısı"),
    code("rows = []\nfor n in ('lstm', 'cnn_lstm'):\n    m = models.build_model(n)\n    print(m)\n"
         "    rows.append({'model': n, 'parametre': models.count_params(m)})\nprint(pd.DataFrame(rows).to_string(index=False))"),
    md("## 2. Eğitim ayarları\nAMP ve `torch.compile` kullanılmamıştır; `cudnn.deterministic` açıktır "
       "(bit-bit aynı sonuç garanti edilmez). Seed'ler `config.SEEDS`."),
    code("hist = {}\nfor f in sorted(glob.glob(str(config.MODELS_DIR / '*_seed*_history.json'))):\n"
         "    h = json.load(open(f, encoding='utf-8')); hist[(h['model'], h['seed'])] = h\n"
         "h0 = next(iter(hist.values()))\nprint('seed:', config.SEEDS, '| cihaz:', h0['device_name'], '| max_epochs:', h0['max_epochs'])\n"
         "print(h0['hparams'])"),
    md("## 3. Eğitim özeti ve kayıp eğrileri"),
    code("t = pd.DataFrame([{'model': k[0], 'seed': k[1], 'best_epoch': h['best_epoch'], 'stopped_epoch': h['stopped_epoch'],\n"
         "  'best_val_loss': round(h['best_val_loss'], 4), 'total_sec': round(h['total_sec'], 1)} for k, h in hist.items()])\n"
         "print(t.to_string(index=False))\n"
         "fig, ax = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)\n"
         "for a, name in zip(ax, ('lstm', 'cnn_lstm')):\n"
         "    for (m, s), h in hist.items():\n"
         "        if m != name: continue\n"
         "        e = [x['epoch'] for x in h['epochs']]\n"
         "        a.plot(e, [x['train_loss'] for x in h['epochs']], label=f'train s{s}')\n"
         "        a.plot(e, [x['val_loss'] for x in h['epochs']], '--', label=f'val s{s}')\n"
         "    a.set_title(name); a.set_xlabel('epoch'); a.legend(fontsize=7)\n"
         "ax[0].set_ylabel('kayıp'); plt.tight_layout(); plt.show()"),
    md("## 4. Test sonuçları (ortalama ± std)\nBaseline'lar tek koşudur (std = 0); DL için 3 seed. "
       "Birincil metrik gündüz-yalnız RMSE (W)."),
    code("s = pd.read_csv(config.METRICS_DIR / 'summary.csv')\n"
         "d = s[s['mask'] == 'day'].copy()\n"
         "d['RMSE_W'] = d.apply(lambda r: f\"{r['RMSE_W_mean']:.1f} ± {r['RMSE_W_std']:.1f}\", axis=1)\n"
         "d['nRMSE'] = d.apply(lambda r: f\"{r['nRMSE_mean']:.4f} ± {r['nRMSE_std']:.4f}\", axis=1)\n"
         "print(d.pivot(index='model', columns='scope', values='RMSE_W').to_string())\nprint()\n"
         "print(d.pivot(index='model', columns='scope', values='nRMSE').to_string())"),
    md("## 5. Dürüstlük kontrolü\nSonuç ne olursa olsun gizlenmez; ayrıntılı yorum Faz 4'te yapılacaktır."),
    code("g = s[(s['mask']=='day')&(s['scope']=='h4')].set_index('model')['RMSE_W_mean']\n"
         "best_dl = g[['lstm','cnn_lstm']].idxmin()\n"
         "print('En iyi DL modeli:', best_dl, round(g[best_dl], 1), 'W')\n"
         "print('Persistence RMSE (day/h4):', round(g['persistence'], 1), 'W')\n"
         "print('DL persistence geçiyor mu?', bool(g[best_dl] < g['persistence']), '| fark (W):', round(g['persistence'] - g[best_dl], 1))\n"
         "print('XGBoost - en iyi DL farkı (W, + = DL daha iyi):', round(g['xgboost'] - g[best_dl], 1))"),
    md("## 6. Birim testi"),
    code("r = subprocess.run([sys.executable, '-I', str(PROJECT_ROOT/'tests'/'test_models.py')], capture_output=True, text=True, encoding='utf-8', cwd=PROJECT_ROOT)\n"
         "print(r.stdout); print(r.stderr[-500:])"),
]
out = Path(__file__).resolve().parent / "04_derin_ogrenme.ipynb"
nbf.write(nb, out)
print("YAZILDI", out)
