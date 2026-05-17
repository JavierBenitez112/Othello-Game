from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

BOARD_SIZE = 8
EMPTY = "."
BLACK = "B"
WHITE = "W"
DIRECTIONS = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)
FILES = "abcdefgh"

Board = list[list[str]]


@dataclass(slots=True)
class MoveResult:
    board: Board
    flipped: list[tuple[int, int]]


def create_initial_board() -> Board:
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    board[3][3] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    board[4][4] = WHITE
    return board


def clone_board(board: Board) -> Board:
    return [row[:] for row in board]


def opponent(color: str) -> str:
    if color == BLACK:
        return WHITE
    if color == WHITE:
        return BLACK
    raise ValueError(f"Unsupported color: {color}")


def color_name(color: str | None) -> str | None:
    if color == BLACK:
        return "black"
    if color == WHITE:
        return "white"
    return None


def color_token(name: str) -> str:
    normalized = name.lower()
    if normalized == "black":
        return BLACK
    if normalized == "white":
        return WHITE
    raise ValueError(f"Unsupported color name: {name}")


def inside(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def position_to_move(row: int, col: int) -> str:
    return f"{FILES[col]}{row + 1}"


def move_to_position(move: str) -> tuple[int, int]:
    if len(move) != 2:
        raise ValueError(f"Invalid move format: {move}")
    file_char = move[0].lower()
    rank_char = move[1]
    if file_char not in FILES or rank_char not in "12345678":
        raise ValueError(f"Invalid move format: {move}")
    return int(rank_char) - 1, FILES.index(file_char)


def serialize_board(board: Board) -> list[list[str]]:
    return [row[:] for row in board]


def _captures_in_direction(board: Board, row: int, col: int, color: str, dr: int, dc: int) -> list[tuple[int, int]]:
    captured: list[tuple[int, int]] = []
    current_row = row + dr
    current_col = col + dc
    other = opponent(color)

    while inside(current_row, current_col) and board[current_row][current_col] == other:
        captured.append((current_row, current_col))
        current_row += dr
        current_col += dc

    if not captured:
        return []
    if not inside(current_row, current_col):
        return []
    if board[current_row][current_col] != color:
        return []
    return captured


def captured_discs(board: Board, move: str, color: str) -> list[tuple[int, int]]:
    row, col = move_to_position(move)
    if board[row][col] != EMPTY:
        return []

    captured: list[tuple[int, int]] = []
    for dr, dc in DIRECTIONS:
        captured.extend(_captures_in_direction(board, row, col, color, dr, dc))
    return captured


def legal_moves(board: Board, color: str) -> list[str]:
    moves: list[str] = []
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != EMPTY:
                continue
            if captured_discs(board, position_to_move(row, col), color):
                moves.append(position_to_move(row, col))
    return moves


def apply_move(board: Board, move: str, color: str) -> MoveResult:
    flips = captured_discs(board, move, color)
    if not flips:
        raise ValueError(f"Illegal move {move} for color {color}")

    updated = clone_board(board)
    row, col = move_to_position(move)
    updated[row][col] = color
    for flip_row, flip_col in flips:
        updated[flip_row][flip_col] = color
    return MoveResult(board=updated, flipped=flips)


def has_any_legal_move(board: Board, color: str) -> bool:
    return any(True for _ in iter_legal_moves(board, color))


def iter_legal_moves(board: Board, color: str) -> Iterable[str]:
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if board[row][col] != EMPTY:
                continue
            move = position_to_move(row, col)
            if captured_discs(board, move, color):
                yield move


def next_turn_color(board: Board, current_color: str) -> str | None:
    other = opponent(current_color)
    if has_any_legal_move(board, other):
        return other
    if has_any_legal_move(board, current_color):
        return current_color
    return None


def game_over(board: Board) -> bool:
    return not has_any_legal_move(board, BLACK) and not has_any_legal_move(board, WHITE)


def score(board: Board) -> tuple[int, int]:
    black_score = sum(cell == BLACK for row in board for cell in row)
    white_score = sum(cell == WHITE for row in board for cell in row)
    return black_score, white_score


def winner(board: Board) -> str | None:
    black_score, white_score = score(board)
    if black_score > white_score:
        return BLACK
    if white_score > black_score:
        return WHITE
    return None
