from server.game_rules import BLACK, WHITE, apply_move, create_initial_board, game_over, legal_moves, next_turn_color, score


def test_initial_legal_moves_for_black() -> None:
    board = create_initial_board()
    assert legal_moves(board, BLACK) == ["d3", "c4", "f5", "e6"]


def test_move_application_flips_captured_disc() -> None:
    board = create_initial_board()
    result = apply_move(board, "d3", BLACK)

    assert result.board[2][3] == BLACK
    assert result.board[3][3] == BLACK
    assert result.board[3][4] == BLACK


def test_pass_behavior_when_only_opponent_can_move() -> None:
    board = [["." for _ in range(8)] for _ in range(8)]
    board[0][0] = BLACK
    board[0][1] = WHITE

    assert legal_moves(board, WHITE) == []
    assert legal_moves(board, BLACK) == ["c1"]
    assert next_turn_color(board, WHITE) == BLACK


def test_game_over_and_final_scoring() -> None:
    board = [[BLACK for _ in range(8)] for _ in range(8)]
    board[7][7] = WHITE

    assert game_over(board) is True
    assert score(board) == (63, 1)
