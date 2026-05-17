"""
Entry point principal del entrenamiento.
Ejecutar desde othello-project/:
  python -m training.train
"""
from __future__ import annotations
import copy
import logging
import time
from pathlib import Path
import torch
import torch.optim as optim
from client.network import OthelloMLP
from training.self_play import play_game, play_evaluation_games
from training.td_train import train_step

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CHECKPOINTS_DIR = Path("training/checkpoints")
MODEL_OUTPUT = Path("client/model_weights.pt")


def run_phase(
    champion: OthelloMLP,
    device: torch.device,
    n_iterations: int,
    games_per_iter: int,
    search_depth: int,
    temperature: float,
    lam: float,
    lr: float,
    eval_every: int,
    eval_games: int,
    promote_threshold: float,
    phase_name: str,
) -> None:
    """
    Corre N iteraciones de self-play + entrenamiento + evaluación.
    """
    for i in range(n_iterations):
        t0 = time.time()

        # Create challenger as deep copy of champion
        challenger = OthelloMLP().to(device)
        challenger.load_state_dict(copy.deepcopy(champion.state_dict()))
        challenger.eval()
        optimizer = optim.Adam(challenger.parameters(), lr=lr)

        # Generate games with champion vs champion
        trajectories = []
        for _ in range(games_per_iter):
            traj = play_game(champion, champion, search_depth=search_depth, temperature=temperature)
            trajectories.append(traj)

        # Train challenger on champion's games
        loss = train_step(challenger, optimizer, trajectories, lam=lam)

        elapsed = time.time() - t0

        if (i + 1) % eval_every == 0:
            win_rate = play_evaluation_games(champion, challenger, eval_games)
            logger.info(
                "%s iter %d/%d: loss=%.4f, win_rate=%.3f, t=%.1fs",
                phase_name, i + 1, n_iterations, loss, win_rate, elapsed
            )
            if win_rate > promote_threshold:
                champion.load_state_dict(challenger.state_dict())
                champion.eval()
                logger.info("  → Challenger promoted (win_rate=%.3f)", win_rate)
            champion.save(CHECKPOINTS_DIR / f"{phase_name}_champion.pt")
        else:
            logger.info(
                "%s iter %d/%d: loss=%.4f, t=%.1fs",
                phase_name, i + 1, n_iterations, loss, elapsed
            )


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info("Usando device: %s", device)

    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

    champion = OthelloMLP().to(device)
    champion.eval()

    logger.info("=== FASE 1: Bootstrap (2,000 partidas, depth=2) ===")
    run_phase(
        champion=champion,
        device=device,
        n_iterations=10,
        games_per_iter=200,
        search_depth=2,
        temperature=1.5,
        lam=0.7,
        lr=0.001,
        eval_every=5,
        eval_games=100,
        promote_threshold=0.52,
        phase_name="Fase1",
    )
    champion.save(CHECKPOINTS_DIR / "phase1_final.pt")

    logger.info("=== FASE 2 Early: self-play (depth=4) ===")
    run_phase(
        champion=champion, device=device, n_iterations=20, games_per_iter=300,
        search_depth=4, temperature=1.0, lam=0.7, lr=0.001,
        eval_every=5, eval_games=150, promote_threshold=0.55,
        phase_name="Fase2Early",
    )

    logger.info("=== FASE 2 Mid: self-play (depth=5) ===")
    run_phase(
        champion=champion, device=device, n_iterations=30, games_per_iter=400,
        search_depth=5, temperature=0.7, lam=0.7, lr=0.0005,
        eval_every=5, eval_games=150, promote_threshold=0.55,
        phase_name="Fase2Mid",
    )

    logger.info("=== FASE 2 Late: self-play (depth=6) ===")
    run_phase(
        champion=champion, device=device, n_iterations=30, games_per_iter=500,
        search_depth=6, temperature=0.5, lam=0.7, lr=0.0002,
        eval_every=5, eval_games=200, promote_threshold=0.55,
        phase_name="Fase2Late",
    )

    logger.info("=== FASE 3: Refinamiento (depth=7, λ=0.8) ===")
    run_phase(
        champion=champion, device=device, n_iterations=20, games_per_iter=400,
        search_depth=7, temperature=0.3, lam=0.8, lr=0.0001,
        eval_every=5, eval_games=200, promote_threshold=0.55,
        phase_name="Fase3",
    )

    champion.save(MODEL_OUTPUT)
    logger.info("Modelo final guardado en %s", MODEL_OUTPUT)


if __name__ == "__main__":
    main()
