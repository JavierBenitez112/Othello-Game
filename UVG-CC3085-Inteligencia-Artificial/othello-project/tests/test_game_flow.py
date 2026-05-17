from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from server.main import create_app


def _make_client(tmp_path, timeout: float = 0.2) -> TestClient:
    app = create_app(database_url=f"sqlite:///{tmp_path}/test.db", move_timeout_seconds=timeout)
    return TestClient(app)


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _create_started_tournament(client: TestClient) -> tuple[int, int, dict[str, str]]:
    headers = _admin_headers(client)
    create_response = client.post("/admin/tournaments", json={"name": "Flow Cup", "total_rounds": 2}, headers=headers)
    assert create_response.status_code == 200
    tournament_id = create_response.json()["id"]

    open_response = client.post(f"/admin/tournaments/{tournament_id}/start-registration", headers=headers)
    assert open_response.status_code == 200
    return tournament_id, create_response.json()["totalRounds"], headers


def _enroll_player(client: TestClient, tournament_id: int, name: str) -> tuple[int, str]:
    response = client.post("/players", json={"tournament_id": tournament_id, "name": name})
    assert response.status_code == 200
    return response.json()["player_id"], response.json()["client_token"]


def _wait_for_message_of_type(websocket, message_type: str) -> dict:
    while True:
        payload = websocket.receive_json()
        if payload["type"] == message_type:
            return payload


def _play_round_with_two_players(client: TestClient, black_ws_handler: Callable[[dict, any], None] | None = None) -> tuple[str, dict, dict]:
    tournament_id, _, headers = _create_started_tournament(client)
    black_id, black_token = _enroll_player(client, tournament_id, "black")
    white_id, white_token = _enroll_player(client, tournament_id, "white")
    start_tournament_response = client.post(f"/admin/tournaments/{tournament_id}/start", headers=headers)
    assert start_tournament_response.status_code == 200
    round_id = start_tournament_response.json()["rounds"][0]["id"]

    with client.websocket_connect(f"/ws/{black_id}?token={black_token}") as black_ws, client.websocket_connect(
        f"/ws/{white_id}?token={white_token}"
    ) as white_ws:
        round_response = client.post(f"/admin/rounds/{round_id}/start", headers=headers)
        assert round_response.status_code == 200
        game_id = round_response.json()["gameIds"][0]

        black_turn = _wait_for_message_of_type(black_ws, "your_turn")
        if black_ws_handler is not None:
            black_ws_handler(black_turn, black_ws)

        black_game_over = _wait_for_message_of_type(black_ws, "game_over")
        white_game_over = _wait_for_message_of_type(white_ws, "game_over")
        return game_id, black_game_over, white_game_over


def test_illegal_move_causes_loss(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        game_id, black_game_over, white_game_over = _play_round_with_two_players(
            client,
            black_ws_handler=lambda turn, ws: ws.send_json(
                {"type": "move", "game_id": turn["game_id"], "move": "a1"}
            ),
        )

        assert black_game_over["result"] == "white_win"
        assert white_game_over["result"] == "white_win"

        game_response = client.get(f"/games/{game_id}")
        assert game_response.status_code == 200
        assert game_response.json()["forfeit_reason"] == "illegal_move"


def test_timeout_causes_loss(tmp_path) -> None:
    with _make_client(tmp_path, timeout=0.1) as client:
        game_id, black_game_over, white_game_over = _play_round_with_two_players(client)

        assert black_game_over["result"] == "white_win"
        assert white_game_over["result"] == "white_win"

        game_response = client.get(f"/games/{game_id}")
        assert game_response.status_code == 200
        assert game_response.json()["forfeit_reason"] == "timeout"
