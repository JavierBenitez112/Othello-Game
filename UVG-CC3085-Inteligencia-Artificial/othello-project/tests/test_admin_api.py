from __future__ import annotations

from fastapi.testclient import TestClient

from server.main import create_app


def _make_client(tmp_path, timeout: float = 0.2) -> TestClient:
    app = create_app(database_url=f"sqlite:///{tmp_path}/admin-test.db", move_timeout_seconds=timeout)
    return TestClient(app)


def _admin_headers(client: TestClient) -> dict[str, str]:
    login_response = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert login_response.status_code == 200
    token = login_response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _register_player(client: TestClient, tournament_id: int, name: str) -> int:
    response = client.post("/players", json={"tournament_id": tournament_id, "name": name})
    assert response.status_code == 200
    return response.json()["player_id"]


def test_admin_login_and_default_credentials(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        login = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
        assert login.status_code == 200
        assert "token" in login.json()


def test_admin_tournament_lifecycle_and_queries(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        headers = _admin_headers(client)

        create_response = client.post(
            "/admin/tournaments",
            json={"name": "Spring Cup", "total_rounds": 3},
            headers=headers,
        )
        assert create_response.status_code == 200
        tournament_id = create_response.json()["id"]

        start_registration = client.post(f"/admin/tournaments/{tournament_id}/start-registration", headers=headers)
        assert start_registration.status_code == 200
        assert start_registration.json()["registrationStatus"] == "open"

        _register_player(client, tournament_id, "alpha")
        _register_player(client, tournament_id, "beta")

        close_registration = client.post(f"/admin/tournaments/{tournament_id}/close-registration", headers=headers)
        assert close_registration.status_code == 200
        assert close_registration.json()["registrationStatus"] == "closed"

        start_tournament = client.post(f"/admin/tournaments/{tournament_id}/start", headers=headers)
        assert start_tournament.status_code == 200
        assert start_tournament.json()["status"] == "active"
        assert len(start_tournament.json()["rounds"]) == 3

        tournaments = client.get("/admin/tournaments", headers=headers)
        assert tournaments.status_code == 200
        assert tournaments.json()[0]["name"] == "Spring Cup"

        tournament_detail = client.get(f"/admin/tournaments/{tournament_id}", headers=headers)
        assert tournament_detail.status_code == 200
        assert {player["name"] for player in tournament_detail.json()["players"]} == {"alpha", "beta"}
        first_round_id = tournament_detail.json()["rounds"][0]["id"]

        round_start = client.post(f"/admin/rounds/{first_round_id}/start", headers=headers)
        assert round_start.status_code == 200

        round_detail = client.get(f"/admin/rounds/{first_round_id}", headers=headers)
        assert round_detail.status_code == 200
        assert len(round_detail.json()["pairings"]) == 1

        players = client.get("/admin/players", headers=headers)
        assert players.status_code == 200
        assert len(players.json()) == 2

        live_games = client.get("/admin/live-games", headers=headers)
        assert live_games.status_code == 200
        assert len(live_games.json()["games"]) == 1

        game_id = live_games.json()["games"][0]["id"]
        game_detail = client.get(f"/admin/games/{game_id}", headers=headers)
        assert game_detail.status_code == 200
        assert game_detail.json()["blackPlayerName"] in {"alpha", "beta"}

        standings = client.get("/admin/standings", headers=headers)
        assert standings.status_code == 200


def test_admin_can_start_multiple_tournaments_simultaneously(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        headers = _admin_headers(client)

        tournament_one = client.post(
            "/admin/tournaments",
            json={"name": "Morning Cup", "total_rounds": 2},
            headers=headers,
        ).json()["id"]
        tournament_two = client.post(
            "/admin/tournaments",
            json={"name": "Evening Cup", "total_rounds": 2},
            headers=headers,
        ).json()["id"]

        for tournament_id, first_name, second_name in (
            (tournament_one, "alpha", "beta"),
            (tournament_two, "gamma", "delta"),
        ):
            client.post(f"/admin/tournaments/{tournament_id}/start-registration", headers=headers)
            _register_player(client, tournament_id, first_name)
            _register_player(client, tournament_id, second_name)
            response = client.post(f"/admin/tournaments/{tournament_id}/start", headers=headers)
            assert response.status_code == 200
            assert response.json()["status"] == "active"

        tournaments = client.get("/admin/tournaments", headers=headers)
        assert tournaments.status_code == 200
        active_ids = {row["id"] for row in tournaments.json() if row["status"] == "active"}
        assert active_ids == {tournament_one, tournament_two}


def test_admin_can_update_and_delete_tournament(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        headers = _admin_headers(client)
        tournament_id = client.post(
            "/admin/tournaments",
            json={"name": "Editable Cup", "total_rounds": 4},
            headers=headers,
        ).json()["id"]

        update_response = client.patch(
            f"/admin/tournaments/{tournament_id}",
            json={"name": "Edited Cup", "total_rounds": 6},
            headers=headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Edited Cup"
        assert update_response.json()["totalRounds"] == 6

        delete_response = client.delete(f"/admin/tournaments/{tournament_id}", headers=headers)
        assert delete_response.status_code == 204

        missing_response = client.get(f"/admin/tournaments/{tournament_id}", headers=headers)
        assert missing_response.status_code == 404


def test_admin_player_crud(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        headers = _admin_headers(client)
        tournament_id = client.post(
            "/admin/tournaments",
            json={"name": "Players Cup", "total_rounds": 2},
            headers=headers,
        ).json()["id"]

        create_response = client.post(
            "/admin/players",
            json={"tournament_id": tournament_id, "name": "alpha"},
            headers=headers,
        )
        assert create_response.status_code == 200
        player_id = create_response.json()["id"]

        update_response = client.patch(
            f"/admin/players/{player_id}",
            json={"name": "alpha-prime"},
            headers=headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "alpha-prime"

        players_response = client.get("/admin/players", headers=headers)
        assert players_response.status_code == 200
        assert players_response.json()[0]["name"] == "alpha-prime"

        delete_response = client.delete(f"/admin/players/{player_id}", headers=headers)
        assert delete_response.status_code == 204
        assert client.get("/admin/players", headers=headers).json() == []


def test_admin_game_crud(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        headers = _admin_headers(client)
        tournament_id = client.post(
            "/admin/tournaments",
            json={"name": "Games Cup", "total_rounds": 2},
            headers=headers,
        ).json()["id"]
        client.post(f"/admin/tournaments/{tournament_id}/start-registration", headers=headers)
        first_player_id = _register_player(client, tournament_id, "alpha")
        second_player_id = _register_player(client, tournament_id, "beta")
        client.post(f"/admin/tournaments/{tournament_id}/start", headers=headers)
        round_id = client.get(f"/admin/tournaments/{tournament_id}", headers=headers).json()["rounds"][0]["id"]

        create_response = client.post(
            "/admin/games",
            json={
                "round_id": round_id,
                "black_player_id": first_player_id,
                "white_player_id": second_player_id,
            },
            headers=headers,
        )
        assert create_response.status_code == 200
        game_id = create_response.json()["id"]
        assert create_response.json()["status"] == "pending"

        update_response = client.patch(
            f"/admin/games/{game_id}",
            json={"status": "active"},
            headers=headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "active"

        delete_response = client.delete(f"/admin/games/{game_id}", headers=headers)
        assert delete_response.status_code == 204

        game_response = client.get(f"/admin/games/{game_id}", headers=headers)
        assert game_response.status_code == 404


def test_admin_player_forfeit(tmp_path) -> None:
    with _make_client(tmp_path) as client:
        headers = _admin_headers(client)

        tournament_id = client.post(
            "/admin/tournaments",
            json={"name": "Forfeit Cup", "total_rounds": 1},
            headers=headers,
        ).json()["id"]
        client.post(f"/admin/tournaments/{tournament_id}/start-registration", headers=headers)
        first_player_id = _register_player(client, tournament_id, "alpha")
        _register_player(client, tournament_id, "beta")
        client.post(f"/admin/tournaments/{tournament_id}/start", headers=headers)
        round_id = client.get(f"/admin/tournaments/{tournament_id}", headers=headers).json()["rounds"][0]["id"]
        client.post(f"/admin/rounds/{round_id}/start", headers=headers)

        response = client.post(f"/admin/players/{first_player_id}/forfeit", headers=headers)
        assert response.status_code == 200

        live_games = client.get("/admin/live-games", headers=headers)
        assert live_games.status_code == 200
        assert live_games.json()["games"] == []
