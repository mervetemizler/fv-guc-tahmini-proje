# -*- coding: utf-8 -*-
"""NREL PVDAQ sistem 4 verisini OEDI S3'ten indirir (yalnızca standart kütüphane).

Alt komutlar:
  probe    : yıl envanteri çıkarır, en iyi ardışık 2 yılı seçer
  download : seçilen yılların günlük CSV'lerini paralel indirir
"""
import argparse
import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://oedi-data-lake.s3.amazonaws.com"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
KEY_RE = re.compile(
    r"^pvdaq/csv/pvdata/system_id=4/year=(\d{4})/month=(\d{1,2})/day=(\d{1,2})/"
    r"system_4__date_(\d{4})_(\d{2})_(\d{2})\.csv$"
)
REQUIRED = ["ac_power", "poa_irradiance", "ambient_temp", "module_temp_1"]


def http_get(url):
    """GET; 5xx/429/ağ hatasında üstel bekleme ile 5 deneme; 404 -> None."""
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pv-forecast-course-project"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if not (e.code >= 500 or e.code == 429):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            pass
        if attempt < 4:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"İndirme başarısız: {url}")


def list_keys(prefix):
    out, token = [], None
    while True:
        url = f"{BASE}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
        if token:
            url += "&continuation-token=" + urllib.parse.quote(token, safe="")
        root = ET.fromstring(http_get(url))
        for c in root.findall(NS + "Contents"):
            out.append((c.find(NS + "Key").text, int(c.find(NS + "Size").text)))
        if root.findtext(NS + "IsTruncated") == "true":
            token = root.findtext(NS + "NextContinuationToken")
        else:
            return out


def parse_key(key):
    m = KEY_RE.match(key)
    if not m:
        return None
    y, mo, d = int(m.group(4)), int(m.group(5)), int(m.group(6))
    return y, mo, d


def local_path(root, y, mo, d):
    return root / "pvdaq_csv" / f"{y}" / f"system_4_{y}_{mo:02d}_{d:02d}.csv"


def probe(args):
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    inv = {}
    for y in range(args.start, args.end + 1):
        items = {}
        for key, size in list_keys(f"pvdaq/csv/pvdata/system_id=4/year={y}/"):
            p = parse_key(key)
            if p and p[0] == y:
                items[p] = (key, size)
        cols, sample = [], None
        if items:
            target = datetime(y, 7, 15).toordinal()
            best = min(items, key=lambda p: abs(datetime(*p).toordinal() - target))
            sample = items[best][0]
            data = http_get(f"{BASE}/{sample}")
            if data:
                cols = data.decode("utf-8", errors="replace").splitlines()[0].strip().split(",")
        has = bool(cols) and all(any(c.startswith(r) for c in cols) for r in REQUIRED)
        inv[str(y)] = {"days": len(items), "total_bytes": sum(s for _, s in items.values()),
                       "sample_key": sample, "columns": cols, "has_required": has}
        print(f"{y}: {len(items)} gün, has_required={has}", flush=True)
    (root / "year_inventory.json").write_text(json.dumps(inv, indent=2, ensure_ascii=False), encoding="utf-8")

    pairs = []
    for y in range(args.start, args.end):
        a, b = inv[str(y)], inv[str(y + 1)]
        if a["has_required"] and b["has_required"]:
            pairs.append((y, min(a["days"], b["days"]), a["days"] + b["days"]))
    if not pairs:
        sys.exit("Uygun çift yok")
    good = [p for p in pairs if p[1] >= 350]
    pool = good or pairs
    best = max(pool, key=lambda p: (p[1], p[2], p[0]))
    y = best[0]
    crit = (f"Her iki yılı da gerekli kolonlara sahip, en az 350 günlük ardışık çiftler arasından en küçük gün sayısı "
            f"en büyük olan çift seçildi ({y}: {inv[str(y)]['days']} gün, {y+1}: {inv[str(y+1)]['days']} gün)."
            if good else
            f"Hiçbir çift 350 gün eşiğini geçmedi; en küçük gün sayısı en büyük olan çift seçildi.")
    sel = {"system_id": 4, "years": [y, y + 1],
           "days": {str(y): inv[str(y)]["days"], str(y + 1): inv[str(y + 1)]["days"]},
           "criterion": crit, "selected_on": "2026-11-01"}
    (root / "selected_years.json").write_text(json.dumps(sel, indent=2, ensure_ascii=False), encoding="utf-8")
    print("SEÇİLEN:", sel, flush=True)


def fetch_one(root, key, size):
    y, mo, d = parse_key(key)
    dest = local_path(root, y, mo, d)
    if dest.exists() and dest.stat().st_size == size:
        return key, "skip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".part")
    try:
        data = http_get(f"{BASE}/{urllib.parse.quote(key)}")
        if data is None:
            return key, "404"
        part.write_bytes(data)
        with open(part, "rb") as f:
            first = f.readline()
        if not first.startswith(b"measured_on") or len(data) != size:
            part.unlink(missing_ok=True)
            return key, "bad"
        part.replace(dest)
        return key, "ok"
    except Exception as e:
        part.unlink(missing_ok=True)
        return key, f"err:{e}"


def download(args):
    root = Path(args.root)
    todo, expected = [], {}
    for y in args.years:
        ks = [(k, s) for k, s in list_keys(f"pvdaq/csv/pvdata/system_id=4/year={y}/")
              if (p := parse_key(k)) and p[0] == y]
        expected[str(y)] = len(ks)
        todo += ks
    print(f"Başlangıç: {len(todo)} dosya, yıllar={args.years}", flush=True)
    failed, n = [], 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for key, st in ex.map(lambda t: fetch_one(root, *t), todo):
            n += 1
            if st not in ("ok", "skip"):
                failed.append(key)
            if n % 50 == 0:
                print(f"{n}/{len(todo)} işlendi, başarısız={len(failed)}", flush=True)
    downloaded = {}
    for y in args.years:
        d = root / "pvdaq_csv" / str(y)
        downloaded[str(y)] = len(list(d.glob("*.csv"))) if d.exists() else 0
    done = {"years": args.years, "expected": expected, "downloaded": downloaded,
            "failed": failed, "finished_at": datetime.now().isoformat()}
    (root / "pvdaq_csv").mkdir(parents=True, exist_ok=True)
    (root / "pvdaq_csv" / "_DONE.json").write_text(json.dumps(done, indent=2), encoding="utf-8")
    print("BİTTİ", done, flush=True)
    if failed:
        sys.exit(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1] / "data" / "raw"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--start", type=int, default=2010)
    p.add_argument("--end", type=int, default=2024)
    d = sub.add_parser("download")
    d.add_argument("--years", type=int, nargs="+", required=True)
    d.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    probe(a) if a.cmd == "probe" else download(a)


if __name__ == "__main__":
    main()
