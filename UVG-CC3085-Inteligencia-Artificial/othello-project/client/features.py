"""
Extracción de features estratégicos para el evaluador de Othello.
Todos los features retornan valores normalizados en [-1, +1].
"""
from __future__ import annotations
import numpy as np
from server.game_rules import (
    legal_moves, opponent, apply_move, score,
    BLACK, WHITE, EMPTY, BOARD_SIZE
)

NUM_FEATURES = 17

POSITION_WEIGHTS = np.array([
    [100, -20,  10,   5,   5,  10, -20, 100],
    [-20, -40,  -5,  -5,  -5,  -5, -40, -20],
    [ 10,  -5,   3,   1,   1,   3,  -5,  10],
    [  5,  -5,   1,   0,   0,   1,  -5,   5],
    [  5,  -5,   1,   0,   0,   1,  -5,   5],
    [ 10,  -5,   3,   1,   1,   3,  -5,  10],
    [-20, -40,  -5,  -5,  -5,  -5, -40, -20],
    [100, -20,  10,   5,   5,  10, -20, 100],
], dtype=np.float32)

CORNERS = [(0, 0), (0, 7), (7, 0), (7, 7)]
X_SQUARES = [(1, 1), (1, 6), (6, 1), (6, 6)]
C_SQUARES = [(0, 1), (1, 0), (0, 6), (1, 7), (6, 0), (7, 1), (6, 7), (7, 6)]

_DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

_CORNER_ADJACENCY = {
    (0, 0): [(1, 1), (0, 1), (1, 0)],
    (0, 7): [(1, 6), (0, 6), (1, 7)],
    (7, 0): [(6, 1), (6, 0), (7, 1)],
    (7, 7): [(6, 6), (6, 7), (7, 6)],
}


def extract_features(board: list[list[str]], my_color: str) -> np.ndarray:
    """
    Extrae 17 features del tablero desde la perspectiva de my_color.
    my_color es "B" o "W" (token, no nombre).
    Retorna np.ndarray de shape (17,) con valores en [-1, +1].
    """
    opp_color = opponent(my_color)
    features = np.zeros(NUM_FEATURES, dtype=np.float32)

    # Precompute board counts and sets
    my_cells = []
    opp_cells = []
    empty_cells = []
    for r in range(8):
        for c in range(8):
            cell = board[r][c]
            if cell == my_color:
                my_cells.append((r, c))
            elif cell == opp_color:
                opp_cells.append((r, c))
            else:
                empty_cells.append((r, c))

    my_count = len(my_cells)
    opp_count = len(opp_cells)
    empty_count = len(empty_cells)

    # Feature 0: corner_score
    corner_score = 0.0
    for r, c in CORNERS:
        if board[r][c] == my_color:
            corner_score += 1
        elif board[r][c] == opp_color:
            corner_score -= 1
    features[0] = corner_score / 4.0

    # Feature 1: x_square_penalty
    xsq_score = 0.0
    for r, c in X_SQUARES:
        if board[r][c] == my_color:
            xsq_score -= 1
        elif board[r][c] == opp_color:
            xsq_score += 1
    features[1] = xsq_score / 4.0

    # Feature 2: c_square_penalty
    csq_score = 0.0
    for r, c in C_SQUARES:
        if board[r][c] == my_color:
            csq_score -= 1
        elif board[r][c] == opp_color:
            csq_score += 1
    features[2] = csq_score / 8.0

    # Feature 3: mobility
    my_moves = legal_moves(board, my_color)
    opp_moves = legal_moves(board, opp_color)
    total_mob = len(my_moves) + len(opp_moves)
    features[3] = (len(my_moves) - len(opp_moves)) / max(total_mob, 1)

    # Feature 4: potential_mobility
    my_potential = set()
    opp_potential = set()
    for r, c in empty_cells:
        for dr, dc in _DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                if board[nr][nc] == opp_color:
                    my_potential.add((r, c))
                elif board[nr][nc] == my_color:
                    opp_potential.add((r, c))
    mp = len(my_potential)
    op = len(opp_potential)
    features[4] = (mp - op) / max(mp + op, 1)

    # Feature 5: positional_score
    pos_score = 0.0
    for r, c in my_cells:
        pos_score += POSITION_WEIGHTS[r][c]
    for r, c in opp_cells:
        pos_score -= POSITION_WEIGHTS[r][c]
    features[5] = pos_score / 1000.0

    # Feature 6: piece_count
    features[6] = (my_count - opp_count) / 64.0

    # Feature 7: frontier_discs
    my_frontier = 0
    opp_frontier = 0
    for r, c in my_cells:
        for dr, dc in _DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8 and board[nr][nc] == EMPTY:
                my_frontier += 1
                break
    for r, c in opp_cells:
        for dr, dc in _DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8 and board[nr][nc] == EMPTY:
                opp_frontier += 1
                break
    total_frontier = my_frontier + opp_frontier
    raw_frontier = (my_frontier - opp_frontier) / max(total_frontier, 1)
    features[7] = -raw_frontier  # fewer own frontier discs = better

    # Feature 8: stability (simplified)
    def count_stable(color):
        stable = set()
        for cr, cc in CORNERS:
            if board[cr][cc] == color:
                stable.add((cr, cc))
                for dc in [1, -1]:
                    col = cc + dc
                    while 0 <= col < 8 and board[cr][col] == color:
                        stable.add((cr, col))
                        col += dc
                for dr in [1, -1]:
                    row = cr + dr
                    while 0 <= row < 8 and board[row][cc] == color:
                        stable.add((row, cc))
                        row += dr
        return len(stable)

    my_stable = count_stable(my_color)
    opp_stable = count_stable(opp_color)
    total_stable = my_stable + opp_stable
    features[8] = (my_stable - opp_stable) / max(total_stable, 1)

    # Feature 9: edge_occupancy (excluding corners)
    corner_set = set(CORNERS)
    my_edge = sum(1 for r, c in my_cells if (r in (0, 7) or c in (0, 7)) and (r, c) not in corner_set)
    opp_edge = sum(1 for r, c in opp_cells if (r in (0, 7) or c in (0, 7)) and (r, c) not in corner_set)
    features[9] = (my_edge - opp_edge) / 24.0

    # Feature 10: center_control
    center = {(3, 3), (3, 4), (4, 3), (4, 4)}
    my_center = sum(1 for r, c in my_cells if (r, c) in center)
    opp_center = sum(1 for r, c in opp_cells if (r, c) in center)
    features[10] = (my_center - opp_center) / 4.0

    # Feature 11: corner_closeness
    my_penalty = 0
    opp_penalty = 0
    for corner, adj in _CORNER_ADJACENCY.items():
        cr, cc = corner
        if board[cr][cc] == EMPTY:
            for r, c in adj:
                if board[r][c] == my_color:
                    my_penalty += 1
                elif board[r][c] == opp_color:
                    opp_penalty += 1
    features[11] = (opp_penalty - my_penalty) / 12.0

    # Feature 12: parity
    if empty_count == 0:
        features[12] = 0.0
    elif empty_count % 2 == 1:
        features[12] = 1.0
    else:
        features[12] = -1.0

    # Feature 13: empty_cells (phase index)
    features[13] = empty_count / 64.0

    # Feature 14: my_corner_ratio
    my_corners = sum(1 for r, c in CORNERS if board[r][c] == my_color)
    opp_corners = sum(1 for r, c in CORNERS if board[r][c] == opp_color)
    total_corners = my_corners + opp_corners
    ratio = my_corners / max(total_corners, 1)
    features[14] = ratio * 2.0 - 1.0

    # Feature 15: move_count_log
    log_val = np.log1p(len(my_moves)) / np.log1p(20)
    features[15] = log_val * 2.0 - 1.0

    # Feature 16: phase_weight
    features[16] = 1.0 - (empty_count / 64.0)

    return np.clip(features, -1.0, 1.0)
