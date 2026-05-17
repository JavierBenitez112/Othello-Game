from __future__ import annotations

import asyncio
import logging
import sys
import time
import random
from pathlib import Path
from client.network import OthelloMLP
from client.search import best_move as _ml_best_move

# Ensure project root is in path so server.game_rules is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from server.game_rules import (
    apply_move,
    legal_moves as _legal_moves_for,
    opponent,
    color_token,
    game_over,
    position_to_move,
    score,
)

from client.bot_client import BotClient, build_arg_parser

# ── MLP Value Network (loaded once at startup) ────────────────────────────────
_MODEL_PATH = Path(__file__).resolve().parent / "model_weights.pt"
if _MODEL_PATH.exists():
    _MODEL = OthelloMLP.load(_MODEL_PATH)
else:
    _MODEL = None  # fallback: random

# ── CNN Value Network (optional — needs torch + model_weights.pt) ─────────────
_WEIGHTS_PATH = Path(__file__).resolve().parent / "model_weights.pt"
_CNN_MODEL = None

try:
    import torch
    import torch.nn as nn

    class _OthelloNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(3, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
                nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.Conv2d(128, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
            )
            self.head = nn.Sequential(
                nn.Flatten(),
                nn.Linear(128 * 8 * 8, 256), nn.ReLU(), nn.Dropout(0.3),
                nn.Linear(256, 64), nn.ReLU(),
                nn.Linear(64, 1), nn.Tanh(),
            )

        def forward(self, x):
            return self.head(self.conv(x)).squeeze(-1)

except ImportError:
    pass


def _board_to_tensor(board, color):
    """Returns (1, 3, 8, 8) torch tensor: [my_pieces, opp_pieces, my_legal_moves]."""
    import torch
    my  = color_token(color)
    opp = opponent(my)
    moves = set(_legal_moves_for(board, my))
    t = torch.zeros(1, 3, 8, 8)
    for r in range(8):
        for c in range(8):
            cell = board[r][c]
            if cell == my:
                t[0, 0, r, c] = 1.0
            elif cell == opp:
                t[0, 1, r, c] = 1.0
            if position_to_move(r, c) in moves:
                t[0, 2, r, c] = 1.0
    return t


# ── Positional weights table for heuristic evaluation ────────────────────────
_POS_W = [
    [100, -20, 10,  5,  5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [ 10,  -2,  8,  3,  3,  8,  -2,  10],
    [  5,  -2,  3,  1,  1,  3,  -2,   5],
    [  5,  -2,  3,  1,  1,  3,  -2,   5],
    [ 10,  -2,  8,  3,  3,  8,  -2,  10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10,  5,  5, 10, -20, 100],
]

# Move-ordering categories (worst squares kept last in search to maximize pruning)
_CORNERS = {"a1", "a8", "h1", "h8"}
_C_SQ    = {"a2", "b1", "a7", "b8", "h2", "g1", "h7", "g8"}   # edge-adjacent to corners
_X_SQ    = {"b2", "b7", "g2", "g7"}                             # diagonally adjacent to corners
_EDGES   = (
    {f"{f}{r}" for f in "abcdefgh" for r in ("1", "8")} |
    {f"{f}{r}" for f in ("a", "h") for r in "12345678"}
) - _CORNERS - _C_SQ


def _move_priority(m: str) -> int:
    if m in _CORNERS: return 0   # best: always consider first
    if m in _EDGES:   return 1   # safe edges
    if m in _C_SQ:    return 3   # risky: adjacent to corner on edge
    if m in _X_SQ:    return 4   # worst: diagonal to corner
    return 2                      # normal interior


def _heuristic(board, my: str, opp: str) -> float:
    pos = my_n = opp_n = 0
    for r in range(8):
        for c in range(8):
            cell = board[r][c]
            if cell == my:
                pos += _POS_W[r][c]; my_n += 1
            elif cell == opp:
                pos -= _POS_W[r][c]; opp_n += 1

    total = my_n + opp_n
    disc  = (my_n - opp_n) / total if total else 0.0

    my_mob  = len(_legal_moves_for(board, my))
    opp_mob = len(_legal_moves_for(board, opp))
    mob = (my_mob - opp_mob) / (my_mob + opp_mob) if (my_mob + opp_mob) else 0.0

    raw = 0.5 * (pos / 1000.0) + 0.35 * mob + 0.15 * disc
    return max(-1.0, min(1.0, raw))


def _leaf_eval(board, color: str) -> float:
    """Evaluate board from `color`'s perspective: +1 win, -1 loss, 0 draw."""
    my  = color_token(color)
    opp = opponent(my)

    if game_over(board):
        bs, ws = score(board)
        my_s, opp_s = (bs, ws) if my == "B" else (ws, bs)
        if my_s > opp_s: return  1.0
        if my_s < opp_s: return -1.0
        return 0.0

    if _MODEL is not None:
        try:
            import torch
            with torch.no_grad():
                return float(_MODEL(_board_to_tensor(board, color)).item())
        except Exception:
            pass

    return _heuristic(board, my, opp)


_OPP_COLOR = {"black": "white", "white": "black"}
# Server timeout is 3s; we use 2.8s to leave a 200ms safety margin.
_TIME_BUDGET = 2.8


def _negamax(board, color: str, depth: int, alpha: float, beta: float, deadline: float):
    """Negamax with alpha-beta pruning. Returns (value, best_move) from `color`'s POV."""
    if time.time() >= deadline or game_over(board) or depth == 0:
        return _leaf_eval(board, color), None

    my    = color_token(color)
    opp_c = _OPP_COLOR[color]
    moves = _legal_moves_for(board, my)

    if not moves:
        # Current player must pass; negate because we switch perspective
        val, _ = _negamax(board, opp_c, depth - 1, -beta, -alpha, deadline)
        return -val, None

    best_val, best_mv = -2.0, moves[0]

    for mv in sorted(moves, key=_move_priority):
        if time.time() >= deadline:
            break
        nb      = apply_move(board, mv, my).board
        val, _  = _negamax(nb, opp_c, depth - 1, -beta, -alpha, deadline)
        val     = -val          # flip to current player's perspective
        if val > best_val:
            best_val, best_mv = val, mv
        alpha = max(alpha, val)
        if alpha >= beta:
            break               # beta cut-off

    return best_val, best_mv


def _choose_move_impl(board, color: str, legal_moves_list: list[str]) -> str:
    """Iterative-deepening alpha-beta within the remaining time budget."""
    deadline  = time.time() + _TIME_BUDGET
    best_move = legal_moves_list[0]   # safe fallback

    for depth in range(1, 15):
        if time.time() >= deadline - 0.05:   # reserve 50 ms for overhead
            break
        _, candidate = _negamax(board, color, depth, -2.0, 2.0, deadline)
        if candidate is not None and candidate in legal_moves_list:
            best_move = candidate

    # Safety guard: never send an illegal move
    return best_move if best_move in legal_moves_list else legal_moves_list[0]


def choose_move(board: list[list[str]], color: str, legal_moves: list[str]) -> str:
    if not legal_moves:
        return "pass"
    if _MODEL is None:
        return random.choice(legal_moves)
    return _ml_best_move(board, color, legal_moves, _MODEL, budget_seconds=2.8)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_arg_parser().parse_args()
    client = BotClient(
        server_url=args.server_url,
        tournament_name=args.tournament_name,
        username=args.username,
        choose_move=choose_move,
    )
    asyncio.run(client.run_forever())


if __name__ == "__main__":
    main()
