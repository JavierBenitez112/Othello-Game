"""
Entrenamiento con TD(λ) sobre trayectorias de self-play.
"""
from __future__ import annotations
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from client.network import OthelloMLP
from client.features import NUM_FEATURES
from server.game_rules import BLACK, WHITE


def compute_td_targets(
    values: list[float],
    final_result: float,
    lam: float = 0.7,
) -> list[float]:
    """
    Calcula los λ-returns para una trayectoria.
    G_{T-1} = z
    G_t = (1-λ) * V(s_{t+1}) + λ * G_{t+1}
    """
    T = len(values)
    if T == 0:
        return []
    targets = [0.0] * T
    targets[T - 1] = final_result
    for t in range(T - 2, -1, -1):
        targets[t] = (1 - lam) * values[t + 1] + lam * targets[t + 1]
    return targets


def train_step(
    model: OthelloMLP,
    optimizer: optim.Optimizer,
    trajectories: list[list[tuple[np.ndarray, str, float]]],
    lam: float = 0.7,
    batch_size: int = 256,
    grad_clip: float = 1.0,
) -> float:
    """
    Realiza un paso de entrenamiento con TD(λ) sobre las trayectorias.
    """
    all_samples: list[tuple[np.ndarray, float]] = []

    for game in trajectories:
        black_traj = [(f, r) for f, c, r in game if c == BLACK]
        white_traj = [(f, r) for f, c, r in game if c == WHITE]

        for sub_traj in [black_traj, white_traj]:
            if not sub_traj:
                continue
            features_list = [f for f, _ in sub_traj]
            final_result = sub_traj[-1][1]

            values = [model.evaluate(f) for f in features_list]
            targets = compute_td_targets(values, final_result, lam)

            for f, t in zip(features_list, targets):
                all_samples.append((f, t))

    if not all_samples:
        return 0.0

    random.shuffle(all_samples)

    device = next(model.parameters()).device
    criterion = nn.MSELoss()
    model.train()
    total_loss = 0.0
    n_batches = 0

    for i in range(0, len(all_samples), batch_size):
        batch = all_samples[i : i + batch_size]
        features_np = np.array([f for f, _ in batch], dtype=np.float32)
        targets_np = np.array([t for _, t in batch], dtype=np.float32)

        features_tensor = torch.tensor(features_np).to(device)
        targets_tensor = torch.tensor(targets_np).unsqueeze(1).to(device)

        optimizer.zero_grad()
        pred = model(features_tensor)
        loss = criterion(pred, targets_tensor)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()

        total_loss += loss.item()
        n_batches += 1

    model.eval()
    return total_loss / max(n_batches, 1)
