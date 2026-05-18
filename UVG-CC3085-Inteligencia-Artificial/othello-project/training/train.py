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
from training.self_play import play_games_parallel, play_evaluation_games
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
    phase_name: str,
    n_epochs: int = 5,
) -> None:
    """
    Corre N iteraciones de self-play + entrenamiento + evaluación.
    El champion siempre se actualiza con el challenger entrenado.
    El win_rate se usa solo para monitoreo.
    """
    for i in range(n_iterations):
        t0 = time.time()

        # Create challenger as deep copy of champion
        challenger = OthelloMLP().to(device)
        challenger.load_state_dict(copy.deepcopy(champion.state_dict()))
        challenger.eval()
        optimizer = optim.Adam(challenger.parameters(), lr=lr)

        # Generate games with champion vs champion (en paralelo)
        trajectories = play_games_parallel(
            champion, games_per_iter, search_depth, temperature
        )

        # Train challenger on champion's games (n_epochs épocas)
        loss = train_step(challenger, optimizer, trajectories, lam=lam, n_epochs=n_epochs)

        elapsed = time.time() - t0

        if (i + 1) % eval_every == 0:
            # Evaluar ANTES de promover: champion (viejo) vs challenger (entrenado)
            # Usar depth=2 para que la evaluación sea rápida (~2 min)
            win_rate = play_evaluation_games(
                champion, challenger, n_games=eval_games, search_depth=2
            )
            logger.info(
                "%s iter %d/%d: loss=%.4f, win_rate=%.3f, t=%.1fs",
                phase_name, i + 1, n_iterations, loss, win_rate, elapsed
            )
            # Promover siempre — el modelo siempre evoluciona
            champion.load_state_dict(challenger.state_dict())
            champion.eval()
            champion.save(CHECKPOINTS_DIR / f"{phase_name}_champion.pt")
        else:
            logger.info(
                "%s iter %d/%d: loss=%.4f, t=%.1fs",
                phase_name, i + 1, n_iterations, loss, elapsed
            )
            # Promover en iteraciones sin evaluación también
            champion.load_state_dict(challenger.state_dict())
            champion.eval()


def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info("Usando device: %s", device)

    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

    champion = OthelloMLP().to(device)
    champion.eval()

    # Fase 1: Bootstrap rápido — exploración amplia a baja profundidad
    logger.info("=== FASE 1: Bootstrap (depth=2, 150 partidas) ===")
    run_phase(
        champion=champion, device=device,
        n_iterations=10, games_per_iter=150,
        search_depth=2, temperature=1.5,
        lam=0.7, lr=0.001,
        eval_every=5, eval_games=40,
        phase_name="Fase1", n_epochs=3,
    )
    champion.save(CHECKPOINTS_DIR / "phase1_final.pt")

    # Fase 2a: Profundidad moderada — el modelo empieza a ver táctica
    logger.info("=== FASE 2 Early: self-play (depth=3, 150 partidas) ===")
    run_phase(
        champion=champion, device=device,
        n_iterations=15, games_per_iter=150,
        search_depth=3, temperature=1.0,
        lam=0.7, lr=0.001,
        eval_every=5, eval_games=40,
        phase_name="Fase2Early", n_epochs=3,
    )
    champion.save(CHECKPOINTS_DIR / "phase2early_final.pt")

    # Fase 2b: Más profundidad — aprender estrategia de medio juego
    logger.info("=== FASE 2 Mid: self-play (depth=4, 120 partidas) ===")
    run_phase(
        champion=champion, device=device,
        n_iterations=12, games_per_iter=120,
        search_depth=4, temperature=0.7,
        lam=0.7, lr=0.0005,
        eval_every=4, eval_games=40,
        phase_name="Fase2Mid", n_epochs=3,
    )
    champion.save(CHECKPOINTS_DIR / "phase2mid_final.pt")

    # Fase 3: Refinamiento fino — temperatura baja, aprender endgame
    logger.info("=== FASE 3: Refinamiento (depth=5, λ=0.8) ===")
    run_phase(
        champion=champion, device=device,
        n_iterations=10, games_per_iter=100,
        search_depth=5, temperature=0.3,
        lam=0.8, lr=0.0002,
        eval_every=5, eval_games=40,
        phase_name="Fase3", n_epochs=3,
    )

    champion.save(MODEL_OUTPUT)
    logger.info("Modelo final guardado en %s", MODEL_OUTPUT)


if __name__ == "__main__":
    main()
