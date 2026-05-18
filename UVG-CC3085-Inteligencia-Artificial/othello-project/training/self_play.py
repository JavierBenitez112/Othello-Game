"""
Generación de partidas de self-play entre dos instancias del modelo.
"""
from __future__ import annotations
import os
import random
import numpy as np
from multiprocessing import Pool
import torch
from server.game_rules import (
    create_initial_board, legal_moves, apply_move,
    opponent, winner, score, BLACK, WHITE, color_token, color_name
)
from client.features import CORNERS
from client.features import extract_features
from client.network import OthelloMLP
from client.search import best_move


def play_game(
    black_model: OthelloMLP,
    white_model: OthelloMLP,
    search_depth: int = 4,
    temperature: float = 1.0,
) -> list[tuple[np.ndarray, str, float, float]]:
    """
    Juega una partida completa entre black_model y white_model.
    Retorna lista de (features, color_que_movio, resultado_final, recompensa_intermedia).

    Sistema de recompensas:
      - Resultado final: mezcla de win/loss (70%) + margen de puntuación (30%)
        Así ganar 60-4 genera más gradiente que ganar 33-31.
      - Recompensa intermedia: +0.15 por cada esquina capturada en ese movimiento.
        Las esquinas son permanentes y estratégicamente decisivas en Othello.
    """
    board = create_initial_board()
    current_color = BLACK
    # trajectory: (features, color, corner_bonus_en_este_paso)
    trajectory: list[tuple[np.ndarray, str, float]] = []

    while True:
        moves = legal_moves(board, current_color)
        if not moves:
            opp_moves = legal_moves(board, opponent(current_color))
            if not opp_moves:
                break  # game over
            current_color = opponent(current_color)
            continue  # pass

        model = black_model if current_color == BLACK else white_model
        features = extract_features(board, current_color)

        if temperature > 0.5 and random.random() < 0.1:
            move = random.choice(moves)
        else:
            move = best_move(
                board, color_name(current_color), moves, model,
                budget_seconds=1.5, max_depth=search_depth
            )

        new_board = apply_move(board, move, current_color).board

        # Recompensa intermedia: bonus por cada esquina nueva capturada
        corner_bonus = 0.0
        for r, c in CORNERS:
            if board[r][c] != current_color and new_board[r][c] == current_color:
                corner_bonus += 0.15

        trajectory.append((features, current_color, corner_bonus))
        board = new_board
        current_color = opponent(current_color)

    # Recompensa final con forma: win/loss + margen de puntuación
    w = winner(board)
    bs, ws = score(board)

    result: list[tuple[np.ndarray, str, float, float]] = []
    for features, color, inter_reward in trajectory:
        my_s, opp_s = (bs, ws) if color == BLACK else (ws, bs)

        if w is None:
            win_signal = 0.0
        elif color == w:
            win_signal = 1.0
        else:
            win_signal = -1.0

        # Margen normalizado a [-1, +1]
        score_margin = (my_s - opp_s) / 64.0

        # Resultado final: mayoría del win/loss, con refuerzo del margen
        final_outcome = 0.7 * win_signal + 0.3 * score_margin

        result.append((features, color, final_outcome, inter_reward))

    return result


def _worker_play_games(args: tuple) -> list:
    """
    Worker para multiprocessing: crea un modelo CPU, juega N partidas y devuelve trayectorias.
    """
    state_dict, n_games, search_depth, temperature = args
    torch.set_num_threads(1)  # Evitar contención de hilos entre workers

    model = OthelloMLP()  # CPU por defecto
    model.load_state_dict(state_dict)
    model.eval()

    trajectories = []
    for _ in range(n_games):
        traj = play_game(model, model, search_depth=search_depth, temperature=temperature)
        trajectories.append(traj)
    return trajectories


def play_games_parallel(
    model: OthelloMLP,
    n_games: int,
    search_depth: int,
    temperature: float,
    n_workers: int | None = None,
) -> list:
    """
    Genera n_games partidas en paralelo usando múltiples procesos CPU.
    """
    if n_workers is None:
        n_workers = min(os.cpu_count() or 4, n_games, 8)

    # Convertir pesos a CPU para que sean picklables entre procesos
    cpu_state_dict = {k: v.cpu() for k, v in model.state_dict().items()}

    # Distribuir partidas entre workers
    games_per_worker = n_games // n_workers
    remainder = n_games % n_workers
    args_list = [
        (cpu_state_dict, games_per_worker + (1 if i < remainder else 0), search_depth, temperature)
        for i in range(n_workers)
    ]

    all_trajectories: list = []
    with Pool(processes=n_workers) as pool:
        for worker_result in pool.map(_worker_play_games, args_list):
            all_trajectories.extend(worker_result)

    return all_trajectories


def _eval_worker(args: tuple) -> float:
    """Worker para evaluación paralela. Retorna 1.0 win, 0.5 draw, 0.0 loss del challenger."""
    chall_state, champ_state, challenger_is_black, search_depth = args
    torch.set_num_threads(1)

    challenger = OthelloMLP()
    challenger.load_state_dict(chall_state)
    challenger.eval()

    champion = OthelloMLP()
    champion.load_state_dict(champ_state)
    champion.eval()

    if challenger_is_black:
        traj = play_game(challenger, champion, search_depth=search_depth, temperature=0.0)
        challenger_color = BLACK
    else:
        traj = play_game(champion, challenger, search_depth=search_depth, temperature=0.0)
        challenger_color = WHITE

    for _, color, outcome, _inter in traj:
        if color == challenger_color:
            if outcome > 0:
                return 1.0
            elif outcome == 0.0:
                return 0.5
            else:
                return 0.0
    return 0.0


def play_evaluation_games(
    champion: OthelloMLP,
    challenger: OthelloMLP,
    n_games: int = 40,
    search_depth: int = 2,
) -> float:
    """
    Juega n_games partidas de evaluación en paralelo.
    Retorna win rate del challenger (wins + 0.5*draws) / n_games.
    """
    chall_state = {k: v.cpu() for k, v in challenger.state_dict().items()}
    champ_state = {k: v.cpu() for k, v in champion.state_dict().items()}

    args_list = [
        (chall_state, champ_state, i < n_games // 2, search_depth)
        for i in range(n_games)
    ]

    n_workers = min(os.cpu_count() or 4, n_games, 8)
    with Pool(processes=n_workers) as pool:
        results = pool.map(_eval_worker, args_list)

    return sum(results) / n_games
