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
    intermediate_rewards: list[float] | None = None,
) -> list[float]:
    """
    Calcula los λ-returns para una trayectoria con recompensas intermedias.

    G_{T-1} = z  (resultado final con forma)
    G_t = r_t + (1-λ) * V(s_{t+1}) + λ * G_{t+1}

    donde r_t es la recompensa inmediata en el paso t
    (ej: bonus por capturar esquinas).
    """
    T = len(values)
    if T == 0:
        return []
    rewards = intermediate_rewards if intermediate_rewards is not None else [0.0] * T
    targets = [0.0] * T
    targets[T - 1] = final_result
    for t in range(T - 2, -1, -1):
        targets[t] = rewards[t] + (1 - lam) * values[t + 1] + lam * targets[t + 1]
    return targets


def train_step(
    model: OthelloMLP,
    optimizer: optim.Optimizer,
    trajectories: list[list[tuple[np.ndarray, str, float]]],
    lam: float = 0.7,
    batch_size: int = 256,
    grad_clip: float = 1.0,
    n_epochs: int = 5,
) -> float:
    """
    Realiza N épocas de entrenamiento con TD(λ) sobre las trayectorias.
    Los targets se calculan UNA vez con el modelo actual (targets fijos),
    luego se entrena n_epochs sobre esos targets para extraer más señal.
    """
    all_samples: list[tuple[np.ndarray, float]] = []

    # Calcular targets con el modelo actual ANTES de entrenar
    # Formato de trayectoria: (features, color, final_outcome, inter_reward)
    model.eval()
    for game in trajectories:
        black_traj = [(f, out, ir) for f, c, out, ir in game if c == BLACK]
        white_traj = [(f, out, ir) for f, c, out, ir in game if c == WHITE]

        for sub_traj in [black_traj, white_traj]:
            if not sub_traj:
                continue
            features_list = [f for f, _, _ in sub_traj]
            inter_rewards = [ir for _, _, ir in sub_traj]
            final_result = sub_traj[-1][1]

            values = [model.evaluate(f) for f in features_list]
            targets = compute_td_targets(
                values, final_result, lam,
                intermediate_rewards=inter_rewards,
            )

            for f, t in zip(features_list, targets):
                all_samples.append((f, t))

    if not all_samples:
        return 0.0

    # Convertir a tensores una sola vez
    device = next(model.parameters()).device
    features_all = torch.tensor(
        np.array([f for f, _ in all_samples], dtype=np.float32)
    ).to(device)
    targets_all = torch.tensor(
        np.array([t for _, t in all_samples], dtype=np.float32)
    ).unsqueeze(1).to(device)

    criterion = nn.MSELoss()
    model.train()
    total_loss = 0.0
    n_batches = 0
    indices = list(range(len(all_samples)))

    # Entrenar n_epochs sobre los mismos targets fijos
    for _ in range(n_epochs):
        random.shuffle(indices)
        for i in range(0, len(indices), batch_size):
            batch_idx = torch.tensor(indices[i : i + batch_size])
            features_tensor = features_all[batch_idx]
            targets_tensor = targets_all[batch_idx]

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
