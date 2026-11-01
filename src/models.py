# -*- coding: utf-8 -*-
"""Faz 3 derin öğrenme modelleri: LSTMNet ve CNNLSTM (D-06).

Girdi (B, 96, 9) -> çıktı (B, 16) (ölçekli kapasite-normalize AC güç, 16 adım ufuk).
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch
from torch import nn

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config  # noqa: E402

MODEL_NAMES = ("lstm", "cnn_lstm")


class LSTMNet(nn.Module):
    """2 katmanlı LSTM; son gizli durum -> Linear(hidden, 16)."""

    def __init__(self, n_in=len(config.INPUT_FEATURES), hidden=config.LSTM_HIDDEN,
                 layers=config.LSTM_LAYERS, dropout=config.DROPOUT, n_out=config.HORIZON):
        super().__init__()
        self.rnn = nn.LSTM(n_in, hidden, layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden, n_out)

    def forward(self, x):
        o, _ = self.rnn(x)
        return self.fc(o[:, -1])


class CNNLSTM(nn.Module):
    """Conv1d(9->32->64, k=3, ReLU) + MaxPool1d(2) + LSTM(64, 1 katman) + Linear."""

    def __init__(self, n_in=len(config.INPUT_FEATURES), channels=config.CNN_CHANNELS,
                 kernel=config.CNN_KERNEL, hidden=config.LSTM_HIDDEN, n_out=config.HORIZON):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(n_in, channels[0], kernel), nn.ReLU(),
            nn.Conv1d(channels[0], channels[1], kernel), nn.ReLU(),
            nn.MaxPool1d(2),
        )
        self.rnn = nn.LSTM(channels[1], hidden, 1, batch_first=True)
        self.fc = nn.Linear(hidden, n_out)

    def forward(self, x):
        z = self.conv(x.transpose(1, 2)).transpose(1, 2)
        o, _ = self.rnn(z)
        return self.fc(o[:, -1])


def build_model(name: str, n_in: int | None = None) -> nn.Module:
    if name == "lstm":
        return LSTMNet() if n_in is None else LSTMNet(n_in=n_in)
    if name == "cnn_lstm":
        return CNNLSTM() if n_in is None else CNNLSTM(n_in=n_in)
    raise ValueError(f"Bilinmeyen model adı: {name!r} (beklenen: {MODEL_NAMES})")


def count_params(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters() if p.requires_grad)


def main() -> None:
    a, b = count_params(LSTMNet()), count_params(CNNLSTM())
    print(f"LSTMNet parametre sayısı: {a}")
    print(f"CNNLSTM parametre sayısı: {b}")
    print(f"Oran (büyük/küçük): {max(a, b) / min(a, b):.2f}")
    print("MODELLER_TAMAM")


if __name__ == "__main__":
    main()
