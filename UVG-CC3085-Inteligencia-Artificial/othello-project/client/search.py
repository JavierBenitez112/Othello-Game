"""
Alpha-Beta Pruning con Iterative Deepening y Tabla de Transposición.
"""
from __future__ import annotations
import math
import time
from server.game_rules import (
    legal_moves, apply_move, opponent, score,
    color_token, BLACK, WHITE
)
from server.game_rules import move_to_position, position_to_move
from client.features import extract_features, CORNERS, X_SQUARES, C_SQUARES, POSITION_WEIGHTS
from client.zobrist import board_hash, update_hash, TT, ZOBRIST_TURN
from client.network import OthelloMLP

_CORNERS_SET = frozenset(CORNERS)
_X_SQUARES_SET = frozenset(X_SQUARES)
_C_SQUARES_SET = frozenset(C_SQUARES)


def order_moves(board: list[list[str]], moves: list[str]) -> list[str]:
    """
    Ordena movimientos por prioridad estratégica:
      Grupo 0 (máxima prioridad): esquinas
      Grupo 1: bordes que no son X/C squares
      Grupo 2: resto
      Grupo 3 (mínima prioridad): X/C squares
    Dentro de cada grupo, ordenar por POSITION_WEIGHTS descendente.
    """
    def key(m: str):
        r, c = move_to_position(m)
        pos = (r, c)
        if pos in _CORNERS_SET:
            group = 0
        elif pos in _X_SQUARES_SET or pos in _C_SQUARES_SET:
            group = 3
        elif r in (0, 7) or c in (0, 7):
            group = 1
        else:
            group = 2
        return (group, -float(POSITION_WEIGHTS[r][c]))

    return sorted(moves, key=key)


def game_result(board: list[list[str]], my_color: str) -> float:
    """
    Para tablero terminal: +1.0 si ganó, -1.0 si perdió, 0.0 si empate.
    """
    bs, ws = score(board)
    my_s, opp_s = (bs, ws) if my_color == BLACK else (ws, bs)
    if my_s > opp_s:
        return 1.0
    if my_s < opp_s:
        return -1.0
    return 0.0


def negamax(
    board: list[list[str]],
    my_color: str,
    depth: int,
    alpha: float,
    beta: float,
    model: OthelloMLP,
    h: int,
    start_time: float,
    budget: float,
) -> float | None:
    """
    Negamax con Alpha-Beta, Transposition Table e Iterative Deepening.
    Retorna float o None si timeout.
    """
    # 1. Check timeout
    if time.time() - start_time > budget:
        return None

    # 2. TT lookup
    tt_val = TT.get(h, depth, alpha, beta)
    if tt_val is not None:
        return tt_val

    # 3. Calculate legal moves
    moves = legal_moves(board, my_color)
    opp_color = opponent(my_color)

    # 4. Handle terminal / pass / leaf
    if not moves:
        opp_moves = legal_moves(board, opp_color)
        if not opp_moves:
            return game_result(board, my_color)
        # Pass: only my_color has no moves
        val = negamax(
            board, opp_color, depth, -beta, -alpha,
            model, h ^ int(ZOBRIST_TURN[0]), start_time, budget
        )
        if val is None:
            return None
        return -val

    if depth == 0:
        return model.evaluate(extract_features(board, my_color))

    # 5-9. Alpha-Beta search
    alpha_original = alpha
    ordered = order_moves(board, moves)
    best = float('-inf')
    flag = 'upper'
    had_timeout = False

    for move in ordered:
        result = apply_move(board, move, my_color)
        new_h = update_hash(h, move, my_color, result.flipped, my_color == BLACK)
        val = negamax(
            result.board, opp_color, depth - 1,
            -beta, -alpha, model, new_h, start_time, budget
        )
        if val is None:
            had_timeout = True
            break
        val = -val
        if val > best:
            best = val
            flag = 'exact' if val > alpha_original else 'upper'
        alpha = max(alpha, val)
        if alpha >= beta:
            flag = 'lower'
            break

    if best == float('-inf'):
        return None  # timeout before any move evaluated

    TT.put(h, depth, best, flag)
    return best


ENDGAME_THRESHOLD = 14


def empty_count(board: list[list[str]]) -> int:
    return sum(1 for row in board for cell in row if cell == ".")


def should_solve_endgame(board: list[list[str]]) -> bool:
    return empty_count(board) <= ENDGAME_THRESHOLD


def best_move(
    board: list[list[str]],
    color: str,
    moves: list[str],
    model: OthelloMLP,
    budget_seconds: float = 2.8,
    max_depth: int | None = None,
) -> str:
    """
    Iterative Deepening: busca desde depth=1 hasta agotar el presupuesto.
    """
    my_color = color_token(color)
    h = board_hash(board, my_color == BLACK)

    if should_solve_endgame(board):
        depth_limit = 30
    else:
        depth_limit = max_depth if max_depth is not None else 18

    best = moves[0]
    start = time.time()

    for depth in range(1, depth_limit + 1):
        if time.time() - start > budget_seconds * 0.75:
            break

        best_val = float('-inf')
        ordered = order_moves(board, moves)
        depth_best = None
        timed_out = False

        for move in ordered:
            result = apply_move(board, move, my_color)
            new_h = update_hash(h, move, my_color, result.flipped, my_color == BLACK)
            val = negamax(
                result.board, opponent(my_color), depth - 1,
                -1.0, 1.0, model, new_h, start, budget_seconds
            )
            if val is None:
                timed_out = True
                break
            val = -val
            if val > best_val:
                best_val = val
                depth_best = move

        if timed_out:
            break
        if depth_best is not None:
            best = depth_best

    return best
