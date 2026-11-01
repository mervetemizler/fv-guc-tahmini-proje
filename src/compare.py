# -*- coding: utf-8 -*-
"""EVAL-07: gün-bloklu bootstrap ile DL-baseline farkları ve kesit bazında kazanan özeti.

Kazanan özetindeki her kesit (ufuk, mevsim, hava, saat, ablasyon) ilgili metrik CSV'sinin
maskesini birebir kopyalayan alt küme maskeli gün-bloklu bootstrap ile karara bağlanır (CR-01).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import analysis  # noqa: E402
from src import config  # noqa: E402

SCOPES = {"h1": [0], "h4": [3], "h8": [7], "h16": [15], "mean16": list(range(16))}
PAIRS = [("lstm", "xgboost"), ("cnn_lstm", "xgboost"), ("lstm", "linreg"), ("cnn_lstm", "linreg"),
         ("lstm", "persistence"), ("cnn_lstm", "persistence"), ("lstm", "cnn_lstm")]
B = 1000
HORIZONS = ((1, "+15 dk", "h1"), (4, "+1 saat", "h4"), (8, "+2 saat", "h8"), (16, "+4 saat", "h16"))


def day_sse(y, pred, mask, wday):
    """Pencere günü başına kare hata toplamı ve geçerli hücre sayısı."""
    m = np.asarray(mask, dtype=bool)
    e2 = ((np.asarray(pred, dtype=float) - np.asarray(y, dtype=float)) ** 2) * m
    s = pd.Series(e2.sum(axis=1)).groupby(np.asarray(wday)).sum()
    c = pd.Series(m.sum(axis=1)).groupby(np.asarray(wday)).sum()
    return s.index.to_numpy(), s.to_numpy(dtype=float), c.to_numpy(dtype=float)


def masked_day_sse(model, preds, w, cell_mask, wday):
    """Verilen (N,16) hücre maskesi için gün SSE'si (DL: seed SSE ortalaması, baseline: tek koşu)."""
    mask = np.asarray(cell_mask, dtype=bool)
    seeds = [None] if model in analysis.BASELINES else list(config.SEEDS)
    sses = []
    for s in seeds:
        days, sse, cnt = day_sse(w["y"], preds[(model, s)], mask, wday)
        sses.append(sse)
    return days, np.mean(sses, axis=0), cnt


def model_day_sse(model, preds, w, scope, wday):
    """DL için seed ortalama SSE (ensemble tahmini yok), baseline için tek koşu."""
    cols = SCOPES[scope]
    mask = np.zeros(w["y_day"].shape, dtype=bool)
    mask[:, cols] = w["y_day"][:, cols]
    return masked_day_sse(model, preds, w, mask, wday)


def bootstrap_diff(sse_a, sse_b, cnt, B, rng):
    sse_a, sse_b, cnt = (np.asarray(v, dtype=float) for v in (sse_a, sse_b, cnt))
    rmse_a = float(np.sqrt(sse_a.sum() / cnt.sum()))
    rmse_b = float(np.sqrt(sse_b.sum() / cnt.sum()))
    D = len(cnt)
    idx = rng.integers(0, D, size=(B, D))
    c = cnt[idx].sum(axis=1)
    fark = np.sqrt(sse_a[idx].sum(axis=1) / c) - np.sqrt(sse_b[idx].sum(axis=1) / c)
    lo, hi = np.percentile(fark, [2.5, 97.5])
    return dict(rmse_a=rmse_a, rmse_b=rmse_b, fark_W=rmse_a - rmse_b, ci_low=float(lo), ci_high=float(hi),
                anlamli=bool(lo > 0 or hi < 0))


def subset_bootstrap(a, b, preds, w, cell_mask, wday, rng):
    """Alt küme maskeli gün-bloklu bootstrap (a - b RMSE farkı); yalnız maskede hücresi olan günler."""
    da, sa, ca = masked_day_sse(a, preds, w, cell_mask, wday)
    db, sb, cb = masked_day_sse(b, preds, w, cell_mask, wday)
    assert (da == db).all() and (ca == cb).all()
    keep = ca > 0
    r = bootstrap_diff(sa[keep], sb[keep], ca[keep], B, rng)
    r["n_gun"] = int(keep.sum())
    return r


def verdict(dl_rmse, base_rmse, unc):
    """A-09: |fark| <= belirsizlik -> belirsiz; dl < base -> evet; aksi hayır."""
    if abs(dl_rmse - base_rmse) <= unc:
        return "belirsiz"
    return "evet" if dl_rmse < base_rmse else "hayır"


def _seed_agg(df: pd.DataFrame, col: str = "RMSE_W") -> pd.DataFrame:
    g = df.groupby("model")[col].agg(["mean", "std"]).fillna(0.0)
    return g


def _make(tur, kesit, g, ci_fn=None):
    """g: index=model, kolonlar mean/std (DL seed ort/std, baseline tek koşu).

    ci_fn(bd, bb) -> bootstrap_diff sonucu (+n_gun); None ise seed-std kuralı (karar_olcutu='seed_std')."""
    bl = g.loc[[m for m in analysis.BASELINES if m in g.index]]
    dl = g.loc[[m for m in analysis.DL_MODELS if m in g.index]]
    if bl.empty or dl.empty:
        return None
    best = g["mean"].idxmin()
    bb, bd = bl["mean"].idxmin(), dl["mean"].idxmin()
    d_r, b_r, d_s = dl.loc[bd, "mean"], bl.loc[bb, "mean"], dl.loc[bd, "std"]
    nan = float("nan")
    if ci_fn is not None:
        r = ci_fn(bd, bb)
        gec = "belirsiz" if not r["anlamli"] else ("evet" if r["fark_W"] < 0 else "hayır")
        extra = dict(karar_olcutu="bootstrap", ci_low=r["ci_low"], ci_high=r["ci_high"],
                     boot_fark_W=r["fark_W"], n_gun_boot=r["n_gun"])
    else:
        gec = verdict(d_r, b_r, d_s)
        extra = dict(karar_olcutu="seed_std", ci_low=nan, ci_high=nan, boot_fark_W=nan, n_gun_boot=nan)
    return dict(kesit_turu=tur, kesit=kesit, en_iyi_model=best, en_iyi_RMSE_W=g.loc[best, "mean"],
                en_iyi_baseline=bb, baseline_RMSE_W=b_r, en_iyi_dl=bd, dl_RMSE_W=d_r, dl_std_W=d_s,
                fark_W=d_r - b_r, dl_baseline_gecti=gec, **extra)


def _load_ablation_preds(w):
    """Ablasyon npz tahminleri: {grup: {(model, seed): (N,16)}}; eksik grup sözlükte yer almaz."""
    from src import ablation, evaluate
    out = {}
    for grup in ablation.RETRAIN_GROUPS:
        d = {}
        ok = True
        files = [((m, s), ablation.ABL_PRED_DIR / f"{m}_{grup}_seed{s}.npz")
                 for m in analysis.DL_MODELS for s in config.SEEDS]
        files += [((m, None), ablation.ABL_PRED_DIR / f"{m}_{grup}.npz") for m in ablation.TAB_MODELS]
        for key, p in files:
            if not p.exists():
                ok = False
                break
            with np.load(p, allow_pickle=False) as z:
                d[key] = evaluate.apply_night_rule(z["y_pred_W"], w["y_sun_elev"])
        if ok:
            out[grup] = d
        else:
            print(f"ABLASYON_NPZ_YOK {grup}")
    return out


def winners(ci_factory, abl_ci_factory, w) -> pd.DataFrame:
    """ci_factory(cell_mask) -> ci_fn; abl_ci_factory(grup, cell_mask) -> ci_fn | None."""
    from src import ablation, weather
    M = config.METRICS_DIR
    y_day = np.asarray(w["y_day"], dtype=bool)
    rows = []
    hz = pd.read_csv(analysis.require_file(M / "horizon_metrics.csv", "python -I src/run_all.py"))
    hz = hz[hz["mask"] == "day"]
    for step, name, scope in HORIZONS:
        m = np.zeros(y_day.shape, dtype=bool)
        m[:, SCOPES[scope]] = y_day[:, SCOPES[scope]]
        rows.append(_make("ufuk", name, _seed_agg(hz[hz.horizon_step == step]), ci_factory(m)))
    sm = pd.read_csv(analysis.require_file(M / "summary.csv", "python -I src/run_all.py"))
    sm = sm[(sm["mask"] == "day") & (sm.scope == "mean16")].set_index("model")
    g = sm[["RMSE_W_mean", "RMSE_W_std"]].rename(columns={"RMSE_W_mean": "mean", "RMSE_W_std": "std"})
    rows.append(_make("ufuk_ort", "16-ufuk ortalaması", g, ci_factory(y_day.copy())))
    se = pd.read_csv(analysis.require_file(M / "season_metrics.csv", "python -I src/run_all.py"))
    for s in ["Kış", "İlkbahar", "Yaz", "Sonbahar"]:
        k = list(config.SEASON_NAMES).index(s)
        m = (np.asarray(w["season"]) == k)[:, None] & y_day
        rows.append(_make("mevsim", s, _seed_agg(se[se.season_name == s]), ci_factory(m)))
    wm = pd.read_csv(analysis.require_file(M / "weather_metrics.csv", "python -I src/weather.py"))
    wm = wm[wm.scope == "mean16"]
    days_df = pd.read_csv(analysis.require_file(M / "weather_days.csv", "python -I src/weather.py"))
    days_df.index = pd.DatetimeIndex(days_df["gun"])
    cls = weather.cell_class(w["y_time"], days_df)
    for k, grp in wm.groupby("sinif"):
        m = y_day & (cls == int(k))
        rows.append(_make("hava", f"{grp['sinif_ad'].iloc[0]} ({int(grp['n_gun'].iloc[0])} gün)",
                          _seed_agg(grp), ci_factory(m)))
    hm = pd.read_csv(analysis.require_file(M / "hour_metrics.csv", "python -I src/figures.py"))
    hm = hm[hm["n"] >= 30]
    _, hour = analysis.target_day_hour(w["y_time"])
    h = config.MAIN_HORIZON_STEPS - 1
    for sa, grp in hm.groupby("saat"):
        m = np.zeros(y_day.shape, dtype=bool)
        m[:, h] = y_day[:, h] & (hour[:, h] == int(sa))
        rows.append(_make("saat", f"{int(sa):02d}:00", _seed_agg(grp), ci_factory(m)))
    ab = pd.read_csv(analysis.require_file(M / "ablation_summary.csv", "python -I src/ablation.py"))
    ab = ab[(ab["mask"] == "day") & (ab.scope == "mean16")]
    for gk in ablation.GROUP_ORDER:
        gg = ab[ab.grup == gk].set_index("model")[["RMSE_W_mean", "RMSE_W_std"]].rename(
            columns={"RMSE_W_mean": "mean", "RMSE_W_std": "std"})
        fn = ci_factory(y_day.copy()) if gk == "D_tam" else abl_ci_factory(gk, y_day.copy())
        r = _make("ablasyon", gk, gg, fn)
        if r is None:
            raise ValueError(f"ablasyon grubu {gk} için satır üretilemedi")
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    w = analysis.load_test()
    preds = analysis.load_all_preds(w)
    wday = analysis.window_day(w["t0_time"])
    rng = np.random.default_rng(config.SEED)
    cache = {}
    out = []
    for a, b in PAIRS:
        for scope in SCOPES:
            for m in (a, b):
                if (m, scope) not in cache:
                    cache[(m, scope)] = model_day_sse(m, preds, w, scope, wday)
            da, sa, ca = cache[(a, scope)]
            db, sb, cb = cache[(b, scope)]
            assert (da == db).all() and (ca == cb).all()
            r = bootstrap_diff(sa, sb, ca, B, rng)
            out.append(dict(model_a=a, model_b=b, kapsam=scope, **r, n_gun=int((ca > 0).sum())))
    boot = pd.DataFrame(out)
    config.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    boot.to_csv(config.METRICS_DIR / "bootstrap_fark.csv", index=False, encoding="utf-8")

    rng_k = np.random.default_rng(config.SEED + 1)  # kesit bootstrap'ları için ayrı akış
    abl = _load_ablation_preds(w)

    def ci_factory(mask):
        return lambda a, b: subset_bootstrap(a, b, preds, w, mask, wday, rng_k)

    def abl_ci_factory(grup, mask):
        if grup not in abl:
            return None
        return lambda a, b: subset_bootstrap(a, b, abl[grup], w, mask, wday, rng_k)

    win = winners(ci_factory, abl_ci_factory, w)
    win.to_csv(config.METRICS_DIR / "kazanan_ozet.csv", index=False, encoding="utf-8")
    nd = boot[(boot.fark_W < boot.ci_low) | (boot.fark_W > boot.ci_high)]
    print("ci_low>ci_high satir:", int((boot.ci_low > boot.ci_high).sum()), "| nokta tahmin CI disinda:", len(nd))
    print(win["dl_baseline_gecti"].value_counts().to_string())
    print(win["karar_olcutu"].value_counts().to_string())
    print(win[win.dl_baseline_gecti == "hayır"][["kesit_turu", "kesit", "en_iyi_baseline", "baseline_RMSE_W",
                                                  "en_iyi_dl", "dl_RMSE_W"]].to_string())
    print("KARSILASTIRMA_TAMAM")


if __name__ == "__main__":
    main()
