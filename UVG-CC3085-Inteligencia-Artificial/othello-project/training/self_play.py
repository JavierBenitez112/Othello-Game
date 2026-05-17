"""
Generación de partidas de self-play entre dos instancias del modelo.
"""
from __future__ import annotations
import random
import numpy as np
from server.game_rules import (
    create_initial_board, legal_moves, apply_move,
    opponent, winner, BLACK, WHITE, color_token, color_name
)
from client.features import extract_features
from client.network import OthelloMLP
from client.search import best_move


def play_game(
    black_model: OthelloMLP,
    white_model: OthelloMLP,
    search_depth: int = 4,
    temperature: float = 1.0,
) -> list[tuple[np.ndarray, str, float]]:
    """
    Juega una partida completa entre black_model y white_model.
    Retorna lista de (features, color_que_movio, resultado_final).
    """
    board = create_initial_board()
    current_color = BLACK
    trajectory: list[tuple[np.ndarray, str]] = []

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
        trajectory.append((features, current_color))

        if temperature > 0.5 and random.random() < 0.1:
            move = random.choice(moves)
        else:
            move = best_move(
                board, color_name(current_color), moves, model,
                budget_seconds=1.5, max_depth=search_depth
            )

        board = apply_move(board, move, current_color).board
        current_color = opponent(current_color)

    w = winner(board)
    result: list[tuple[np.ndarray, str, float]] = []
    for features, color in trajectory:
        if w is None:
            outcome = 0.0
        elif color == w:
            outcome = 1.0
        else:
            outcome = -1.0
        result.append((features, color, outcome))

    return result


def play_evaluation_games(
    champion: OthelloMLP,
    challenger: OthelloMLP,
    n_games: int = 100,
) -> float:
    """
    Juega n_games partidas de evaluación (sin exploración).
    Retorna win rate del challenger (wins + 0.5*draws) / n_games.
    """
    wins = 0.0
    half = n_games // 2

    for i in range(n_games):
        if i < half:
            traj = play_game(challenger, champion, search_depth=4, temperature=0.0)
            challenger_color = BLACK
        else:
            traj = play_game(champion, challenger, search_depth=4, temperature=0.0)
            challenger_color = WHITE

        for _, color, outcome in traj:
            if color == challenger_color:
                if outcome > 0:
                    wins += 1.0
                elif outcome == 0.0:
                    wins += 0.5
                break

    return wins / n_games
