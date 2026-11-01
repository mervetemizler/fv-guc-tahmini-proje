"""Sunum içerik QA: slayt sayısı, kelime, görsel, not, sayı tutarlılığı, figür DPI.

Çalıştırma: .venv/Scripts/python.exe -I presentation/check_deck.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from src import config

PPTX = ROOT / "presentation" / "sunum.pptx"
YASAK = ["Taslak", "TODO", "lorem", "xxxx"]


def words(text: str) -> int:
    return sum(1 for w in text.split() if re.search(r"[^\W_]", w))


def shape_texts(shapes):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from shape_texts(sh.shapes)
        if sh.has_text_frame:
            yield sh.text_frame.text
        if getattr(sh, "has_table", False) and sh.has_table:
            for r in sh.table.rows:
                for c in r.cells:
                    yield c.text


def pictures(shapes):
    n = 0
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            n += 1
        elif sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            n += pictures(sh.shapes)
    return n


def fmt1(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


prs = Presentation(str(PPTX))
slides = list(prs.slides)
assert len(slides) in (13, 14), f"slayt sayısı {len(slides)}"

kaz = pd.read_csv(ROOT / "results" / "metrics" / "kazanan_ozet.csv")
n_toplam = len(kaz)
n_hayir = int((kaz["dl_baseline_gecti"] == "hayır").sum())
ort = kaz[kaz["kesit_turu"] == "ufuk_ort"].iloc[0]

texts = []
for i, sl in enumerate(slides, 1):
    vis = "\n".join(shape_texts(sl.shapes))
    texts.append(vis)
    notes = sl.notes_slide.notes_text_frame.text if sl.has_notes_slide else ""
    k, m, r = words(vis), words(notes), pictures(sl.shapes)
    print(f"slayt {i}: kelime={k}, not={m}, resim={r}")
    assert r >= 1, f"slayt {i}: resim yok"
    assert m >= 70, f"slayt {i}: not {m} kelime (<70)"
    assert k <= 40, f"slayt {i}: görünen metin {k} kelime (>40)"
    for y in YASAK:
        assert y.lower() not in (vis + notes).lower(), f"slayt {i}: yasak ifade {y}"

assert "[Ad Soyad]" in texts[0] and "Kasım 2026" in texts[0], "kapak yer tutucuları"
assert str(n_hayir) in texts[11] and str(n_toplam) in texts[11], "slayt 12 n_hayir/n_toplam"
assert fmt1(ort["dl_RMSE_W"]) in texts[5], "slayt 6 ufuk_ort dl_RMSE_W"

for p in sorted((ROOT / "results" / "figures").glob("*.png")):
    if "tr_karakter_testi" in p.name:
        continue
    with Image.open(p) as im:
        dpi = im.info.get("dpi", (0, 0))[0]
    assert dpi >= 199, f"{p.name}: dpi {dpi}"
assert config.FIG_FONT_SIZE >= 14, "FIG_FONT_SIZE < 14"

print("DECK_KONTROL_TAMAM")
