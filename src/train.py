# -*- coding: utf-8 -*-
"""Faz 3 ortak eğitim döngüsü (LSTM / CNN-LSTM), GPU, elle batch (D-07, D-08).

Güvenlik notu: joblib yalnızca proje içi SCALERS_FILE için yüklenir (Faz 2 ürünü);
torch.load kullanılırsa weights_only=True ile.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import torch
import torch.nn.functional as F

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402
from src import models  # noqa: E402
from src import windows  # noqa: E402

LR_FACTOR = 0.5


def set_seed(seed: int) -> None:
    """Tüm tohumları ayarlar. Bit-bit aynı sonuç garanti değil, sapma çok küçüktür."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_device() -> torch.device:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA bulunamadı; MODEL-03 GPU eğitimi gerektirir")
    return torch.device("cuda")


def load_split_tensors(split: str, device):
    raw = windows.load_windows(split)
    X_t = torch.from_numpy(raw["X"]).float().to(device)
    y_t = torch.from_numpy(raw["y_scaled"]).float().to(device)
    return X_t, y_t, raw


def predict_scaled(model, X_t, batch: int = 4096) -> np.ndarray:
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, X_t.shape[0], batch):
            out.append(model(X_t[i:i + batch]).cpu().numpy())
    return np.concatenate(out, axis=0)


def _val_loss(model, X_t, y_t, batch: int = 4096) -> float:
    model.eval()
    tot = 0.0
    with torch.no_grad():
        for i in range(0, X_t.shape[0], batch):
            tot += F.mse_loss(model(X_t[i:i + batch]), y_t[i:i + batch], reduction="sum").item()
    return tot / y_t.numel()


def train_one(name: str, seed: int, max_epochs: int | None = None, smoke: bool = False,
              feature_idx: list[int] | None = None):
    device = get_device()
    set_seed(seed)
    model = models.build_model(
        name, n_in=len(feature_idx) if feature_idx is not None else None).to(device)
    X_tr, y_tr, _ = load_split_tensors("train", device)
    X_va, y_va, _ = load_split_tensors("val", device)
    if feature_idx is not None:
        X_tr = X_tr[:, :, feature_idx]
        X_va = X_va[:, :, feature_idx]
    n_epochs = 2 if smoke else (max_epochs or config.MAX_EPOCHS)

    opt = torch.optim.Adam(model.parameters(), lr=config.LR, weight_decay=config.WEIGHT_DECAY)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(
        opt, mode="min", factor=LR_FACTOR, patience=config.LR_PATIENCE)
    g = torch.Generator(device=device)
    g.manual_seed(seed)

    N = X_tr.shape[0]
    epochs, best_val, best_epoch, best_state, bad = [], float("inf"), 0, None, 0
    t_all = time.perf_counter()
    for e in range(1, n_epochs + 1):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        model.train()
        perm = torch.randperm(N, device=device, generator=g)
        tot = 0.0
        for i in range(0, N, config.BATCH_SIZE):
            idx = perm[i:i + config.BATCH_SIZE]
            xb, yb = X_tr[idx], y_tr[idx]
            opt.zero_grad(set_to_none=True)
            loss = F.mse_loss(model(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.GRAD_CLIP)
            opt.step()
            tot += loss.item() * xb.shape[0]
        tr_loss = tot / N
        va_loss = _val_loss(model, X_va, y_va)
        if not np.isfinite(va_loss):
            raise RuntimeError(f"{name} s{seed}: val loss sonlu degil (epoch {e})")
        sched.step(va_loss)
        torch.cuda.synchronize()
        sec = time.perf_counter() - t0
        lr = opt.param_groups[0]["lr"]
        epochs.append(dict(epoch=e, train_loss=tr_loss, val_loss=va_loss, lr=lr, sec=sec))
        print(f"[{name} s{seed}] epoch {e} train {tr_loss:.5f} val {va_loss:.5f} lr {lr:.2e} {sec:.1f}s",
              flush=True)
        if va_loss < best_val:
            best_val, best_epoch, bad = va_loss, e, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= config.EARLY_STOP_PATIENCE:
                break
    model.load_state_dict(best_state)
    history = dict(
        model=name, seed=seed, n_params=models.count_params(model),
        device_name=torch.cuda.get_device_name(0), max_epochs=n_epochs,
        best_epoch=best_epoch, best_val_loss=best_val, stopped_epoch=epochs[-1]["epoch"],
        total_sec=time.perf_counter() - t_all,
        hparams=dict(batch_size=config.BATCH_SIZE, lr=config.LR, weight_decay=config.WEIGHT_DECAY,
                     early_stop_patience=config.EARLY_STOP_PATIENCE, lr_patience=config.LR_PATIENCE,
                     lr_factor=LR_FACTOR, grad_clip=config.GRAD_CLIP),
        epochs=epochs,
    )
    if feature_idx is not None:
        history["feature_idx"] = list(feature_idx)
    return model, history


def save_run(name, seed, model, history, te_raw, y_scaler):
    from src.evaluate import apply_night_rule  # tembel import (smoke kullanmaz)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    pred_dir = getattr(config, "PREDICTIONS_DIR", config.RESULTS_DIR / "predictions")
    pred_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), config.MODELS_DIR / f"{name}_seed{seed}.pt")
    with open(config.MODELS_DIR / f"{name}_seed{seed}_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    X_te = torch.from_numpy(te_raw["X"]).float().to(next(model.parameters()).device)
    p = predict_scaled(model, X_te)
    p_w = y_scaler.inverse_transform(p.reshape(-1, 1)).reshape(p.shape)
    p_w = apply_night_rule(p_w, te_raw["y_sun_elev"])
    np.savez_compressed(pred_dir / f"{name}_seed{seed}.npz", y_pred_W=p_w.astype(np.float32))


def _smoke() -> None:
    out = {}
    for name in models.MODEL_NAMES:
        _, h = train_one(name, 42, smoke=True)
        secs = [e["sec"] for e in h["epochs"]]
        out[name] = dict(epoch_sec=float(np.mean(secs[1:])) if len(secs) > 1 else float(secs[0]),
                         n_params=h["n_params"])
        out["device_name"] = h["device_name"]
    out["max_epochs_config"] = config.MAX_EPOCHS
    out["estimated_worst_case_min"] = (
        6 * config.MAX_EPOCHS * max(out[n]["epoch_sec"] for n in models.MODEL_NAMES) / 60)
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.MODELS_DIR / "epoch_timing.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("SMOKE_TAMAM")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=models.MODEL_NAMES)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--max-epochs", type=int, default=None)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        _smoke()
        return
    if a.all:
        jobs = [(n, s) for n in models.MODEL_NAMES for s in config.SEEDS]
    elif a.model:
        jobs = [(a.model, a.seed)]
    else:
        ap.error("--model, --all veya --smoke gerekli")
    sc = joblib.load(config.SCALERS_FILE)
    te_raw = windows.load_windows("test")
    for name, seed in jobs:
        model, h = train_one(name, seed, a.max_epochs)
        save_run(name, seed, model, h, te_raw, sc["y"])
        print(f"EGITIM_TAMAM {name} seed{seed} best_epoch={h['best_epoch']} sure={h['total_sec']:.0f}s",
              flush=True)
    if a.all:
        print("TUM_EGITIMLER_TAMAM")


if __name__ == "__main__":
    main()
