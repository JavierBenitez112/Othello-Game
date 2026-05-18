"""
MLP para evaluación de posiciones de Othello.
Input: 17 features. Output: valor en (-1, +1).
"""
from __future__ import annotations
from pathlib import Path
import torch
import torch.nn as nn
import numpy as np
from client.features import NUM_FEATURES


class OthelloMLP(nn.Module):
    """
    MLP: 17 → 128 → 64 → 32 → 1  (más capacidad para aprender estrategia)
    """

    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(NUM_FEATURES, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    def evaluate(self, features: np.ndarray) -> float:
        """
        Evalúa un vector de features numpy y retorna escalar float en (-1, +1).
        """
        device = next(self.parameters()).device
        with torch.no_grad():
            t = torch.tensor(features, dtype=torch.float32).to(device)
            return float(self.net(t).item())

    def save(self, path: Path) -> None:
        torch.save(self.state_dict(), path)

    @classmethod
    def load(cls, path: Path) -> "OthelloMLP":
        model = cls()
        model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
        model.eval()
        return model
