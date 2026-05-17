"""
Zobrist hashing y tabla de transposición para Alpha-Beta.
"""
from __future__ import annotations
import numpy as np
from server.game_rules import BLACK, WHITE, FILES

_RNG = np.random.default_rng(seed=2026)

ZOBRIST_BLACK: np.ndarray = _RNG.integers(0, 2**63 - 1, size=64).astype(np.uint64)
ZOBRIST_WHITE: np.ndarray = _RNG.integers(0, 2**63 - 1, size=64).astype(np.uint64)
ZOBRIST_TURN:  np.ndarray = _RNG.integers(0, 2**63 - 1, size=1).astype(np.uint64)


def board_hash(board: list[list[str]], is_black_turn: bool) -> int:
    """
    Calcula el hash Zobrist del estado completo.
    """
    h = np.uint64(0)
    for r in range(8):
        for c in range(8):
            idx = r * 8 + c
            cell = board[r][c]
            if cell == BLACK:
                h ^= ZOBRIST_BLACK[idx]
            elif cell == WHITE:
                h ^= ZOBRIST_WHITE[idx]
    if is_black_turn:
        h ^= ZOBRIST_TURN[0]
    return int(h)


def update_hash(
    current_hash: int,
    move: str,
    color: str,
    flipped: list[tuple[int, int]],
    is_black_turn: bool,
) -> int:
    """
    Actualiza el hash incrementalmente después de aplicar un movimiento.
    """
    h = np.uint64(current_hash)

    file_char = move[0].lower()
    rank_char = move[1]
    r = int(rank_char) - 1
    c = FILES.index(file_char)
    idx = r * 8 + c

    # Place the new piece
    if color == BLACK:
        h ^= ZOBRIST_BLACK[idx]
    else:
        h ^= ZOBRIST_WHITE[idx]

    # Flip captured pieces
    opp = WHITE if color == BLACK else BLACK
    for fr, fc in flipped:
        fidx = fr * 8 + fc
        # XOR out opponent's piece
        if opp == BLACK:
            h ^= ZOBRIST_BLACK[fidx]
        else:
            h ^= ZOBRIST_WHITE[fidx]
        # XOR in current player's piece
        if color == BLACK:
            h ^= ZOBRIST_BLACK[fidx]
        else:
            h ^= ZOBRIST_WHITE[fidx]

    # Toggle turn (equivalent to XOR out old turn + XOR in new turn)
    h ^= ZOBRIST_TURN[0]

    return int(h)


class TranspositionTable:
    """
    Tabla de transposición con límite de tamaño.
    Cada entrada: (depth, value, flag)
    flag: 'exact' | 'lower' | 'upper'
    """

    def __init__(self, max_size: int = 1_000_000):
        self._table: dict[int, tuple[int, float, str]] = {}
        self._max_size = max_size

    def get(self, h: int, depth: int, alpha: float, beta: float) -> float | None:
        entry = self._table.get(h)
        if entry is None:
            return None
        stored_depth, value, flag = entry
        if stored_depth < depth:
            return None
        if flag == 'exact':
            return value
        elif flag == 'lower':
            alpha = max(alpha, value)
            if alpha >= beta:
                return value
        elif flag == 'upper':
            beta = min(beta, value)
            if alpha >= beta:
                return value
        return None

    def put(self, h: int, depth: int, value: float, flag: str) -> None:
        if len(self._table) >= self._max_size:
            return
        existing = self._table.get(h)
        if existing is not None and existing[0] > depth:
            return
        self._table[h] = (depth, value, flag)

    def clear(self) -> None:
        self._table.clear()


TT = TranspositionTable(max_size=1_000_000)
