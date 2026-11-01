# -*- coding: utf-8 -*-
"""notebooks/03_baseline.ipynb dosyasını üretir (nbformat)."""
import sys
from pathlib import Path

import nbformat as nbf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {"name": "pv-forecast", "display_name": "pv-forecast", "language": "python"}
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
SETUP = ("import sys, json, subprocess\nfrom pathlib import Path\n"
         "PROJECT_ROOT = Path.cwd().resolve()\n"
         "if not (PROJECT_ROOT / 'src').exists():\n    PROJECT_ROOT = PROJECT_ROOT.parent\n"
         "sys.path.insert(0, str(PROJECT_ROOT))\n"
         "import numpy as np, pandas as pd\n"
         "from src import config\n"
         "config.apply_plot_style()\nprint(config.summary())")
nb.cells = [
    md("# Faz 3 - Baseline Modeller\n\nPersistence, mevsimsel persistence, Doğrusal Regresyon ve XGBoost; hepsi aynı test "
       "penceresi kümesinde ve tek `evaluate()` ile ölçülmüştür. Bu notebook eğitimi tekrarlamaz; "
       "`results/` altındaki kayıtlı çıktıları okur."),
    code(SETUP),
    md("## 1. Baseline tanımları\n"
       "- **Persistence:** tahmin ufkundaki her adım için son gözlenen AC güç değeri.\n"
       "- **Mevsimsel persistence:** dün aynı saatin gözlemi (pencere indeksi h-1).\n"
       "- **Gece kuralı:** hedef zamanında güneş yüksekliği <= 0 ise tahmin 0 yapılır. Bu, deterministik astronomik "
       "bilgidir ve tüm modellere aynı şekilde uygulanır.\n"
       "- **Doğrusal Regresyon ve XGBoost:** 16 adım çıktıyı tablo öznitelikleri üzerinden tahmin eder."),
    md("## 2. Öznitelikler ve XGBoost ayarları"),
    code("info = json.load(open(config.MODELS_DIR / 'baselines_info.json', encoding='utf-8'))\n"
         "names = info['tabular_feature_names']\nprint(len(names), 'öznitelik')\nprint(names)\n"
         "print('XGBoost:', info['xgboost'])\nprint('LinReg:', info['linreg'])"),
    md("## 3. Metrikler\nnRMSE = RMSE / kurulu kapasite (`config.CAPACITY_W`); kW sütunları W değerlerinin /1000 halidir. "
       "Birincil metrik gündüz-yalnız hesaplanır (gece tahmini kural gereği 0'dır, 'tüm saat' metrikleri gece örnekleriyle sulanır)."),
    code("print('capacity_W =', config.CAPACITY_W)\n"
         "a = pd.read_csv(config.METRICS_DIR / 'all_metrics.csv')\n"
         "b = a[a['model'].isin(['persistence','seasonal_persistence','linreg','xgboost'])]\n"
         "print(b.pivot_table(index='model', columns=['mask','scope'], values='RMSE_W').round(1).to_string())\n"
         "print()\nprint(b.pivot_table(index='model', columns=['mask','scope'], values='nRMSE').round(4).to_string())\n"
         "print()\nprint(b[(b['mask']=='day')&(b['scope']=='h4')][['model','MAE_kW','RMSE_kW','R2']].round(4).to_string(index=False))"),
    md("## 4. Birim testleri"),
    code("for t in ('test_evaluate.py', 'test_baselines.py'):\n"
         "    r = subprocess.run([sys.executable, '-I', str(PROJECT_ROOT/'tests'/t)], capture_output=True, text=True, encoding='utf-8', cwd=PROJECT_ROOT)\n"
         "    print(t); print(r.stdout); print(r.stderr[-500:])"),
]
out = Path(__file__).resolve().parent / "03_baseline.ipynb"
nbf.write(nb, out)
print("YAZILDI", out)
