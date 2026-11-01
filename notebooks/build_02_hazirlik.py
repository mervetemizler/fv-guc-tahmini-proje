# -*- coding: utf-8 -*-
"""notebooks/02_hazirlik.ipynb dosyasını üretir (nbformat)."""
import sys
from pathlib import Path

import nbformat as nbf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {"name": "pv-forecast", "display_name": "pv-forecast", "language": "python"}

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb.cells = [
    md("# Faz 2 - Ön İşleme: Bölme, Ölçekleme ve Pencereleme\n\n"
       "Bu notebook, 15 dk ızgaradan sızıntısız train/val/test bölmesini, train-only ölçeklemeyi ve "
       "96 adım girdi / 16 adım çıktı pencerelerini özetler. Mantık `src/` altındadır."),
    code("import sys, json, subprocess\nfrom pathlib import Path\n"
         "PROJECT_ROOT = Path.cwd().resolve()\n"
         "if not (PROJECT_ROOT / 'src').exists():\n    PROJECT_ROOT = PROJECT_ROOT.parent\n"
         "sys.path.insert(0, str(PROJECT_ROOT))\n"
         "import numpy as np, pandas as pd, joblib\n"
         "from src import config, data, windows\n"
         "config.apply_plot_style()\nprint(config.summary())"),
    md("## 1. Izgara\n15 dk, right-label ızgara yüklenir ve veri sözleşmesi doğrulanır."),
    code("grid = data.load_grid()\nprint(data.validate_grid(grid))\nprint(grid.index.min(), '->', grid.index.max())"),
    md("## 2. Bölme\nBölme bin başlangıcına göre yapılır: train 2015, val 2016 tek aylar, test 2016 çift aylar. "
       "Veri `DATA_END` = 2016-12-13 00:00'da kesilmiştir (Aralık test segmenti 12 gün)."),
    code("split, seg = windows.assign_segments(grid.index)\n"
         "tbl = pd.DataFrame({'split': split, 'segment': seg}).groupby(['split','segment']).size().rename('adım')\n"
         "print(tbl.to_string())\nprint(config.DATA_END_REASON)"),
    md("## 3. Ölçekleyiciler (yalnızca train)\nGirdi (9 kanal) ve hedef için ayrı `StandardScaler`, yalnızca train ızgara satırlarına fit edilir."),
    code("sc = joblib.load(config.SCALERS_FILE)  # yalnızca kendi ürettiğimiz dosya\n"
         "print(pd.DataFrame({'ortalama': sc['x'].mean_, 'std': sc['x'].scale_}, index=sc['features']).round(3))\n"
         "print('hedef (W):', sc['y'].mean_, sc['y'].scale_)\nprint('n_train_rows =', sc['n_train_rows'])"),
    md("## 4. Pencereler"),
    code("for s in ('train','val','test'):\n    w = windows.load_windows(s)\n"
         "    print(s, 'X', w['X'].shape, 'y', w['y'].shape, 'tamamı-gece:', int((~w['y_day'].any(axis=1)).sum()))\n"
         "w = windows.load_windows('test')\n"
         "print({config.SEASON_NAMES[k]: int((w['season']==k).sum()) for k in range(4)})\n"
         "print(open(config.WINDOWS_SUMMARY, encoding='utf-8').read()[:600])"),
    md("## 5. Birim testi\nŞekil, hizalama, segment sınırı, NaN atma, gece filtresi, right-label resample ve train-only scaler."),
    code("r = subprocess.run([sys.executable, '-I', str(PROJECT_ROOT/'tests'/'test_windows.py')], capture_output=True, text=True, encoding='utf-8', cwd=PROJECT_ROOT)\n"
         "print(r.stdout); print(r.stderr[-500:])"),
    md("## 6. Özet\nProblem tanımı: `docs/PROBLEM_TANIMI.md`. Hedef AC güç (W), ana ufuk +1 saat (4. adım), "
       "gelecek ışınım verisi kullanılmaz (gerçek tahmin, nowcasting değil)."),
]
out = Path(__file__).resolve().parent / "02_hazirlik.ipynb"
nbf.write(nb, out)
print("YAZILDI", out)
