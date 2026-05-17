from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, WebSocket, WebSocketException
from sqlmodel import Session, select
from starlette import status

from server.game_rules import (
    BLACK,
    WHITE,
    apply_move,
    color_name,
    create_initial_board,
    legal_moves,
    next_turn_color,
    opponent,
    score,
    winner,
)
from server.models import Game, MoveLog, Player, Round, RoundResult, Standing, Tournament, utc_now
from server.pairing import SwissPlayer, swiss_pair
from server.schemas import IncomingMove

logger = logging.getLogger(__name__)

FINAL_GAME_STATUSES = {"completed", "forfeit", "forced_end"}


@dataclass(slots=True)
class TurnContext:
    game_id: str
    player_id: int
    color: str
    legal_moves: list[str]
    future: asyncio.Future[str]
    deadline: float


@dataclass(slots=True)
class RuntimeGame:
    game_id: str
    black_player_id: int
    white_player_id: int
    board: list[list[str]]
    next_color: str | None

    def player_for_color(self, color: str) -> int:
        return self.black_player_id if color == BLACK else self.white_player_id


class TournamentManager:
    def __init__(self, session_factory, move_timeout_seconds: float | None = None) -> None:
        self.session_factory = session_factory
        self.move_timeout_seconds = move_timeout_seconds or float(os.getenv("MOVE_TIMEOUT_SECONDS", "3"))
        self.connections: dict[int, WebSocket] = {}
        self.admin_connections: set[WebSocket] = set()
        self.turns_by_player: dict[int, TurnContext] = {}
        self.runtime_games: dict[str, RuntimeGame] = {}
        self.game_tasks: dict[str, asyncio.Task] = {}

    async def register_connection(self, player_id: int, token: str, websocket: WebSocket) -> None:
        with self.session_factory() as session:
            player = session.get(Player, player_id)
            if player is None or player.client_token != token:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid player_id or token",
                )
            player.connected = True
            session.add(player)
            session.commit()

        await websocket.accept()
        self.connections[player_id] = websocket
        logger.info("Player %s connected", player_id)
        await self._broadcast_admin_event(
            {
                "type": "player_connected",
                "playerId": player_id,
                "timestamp": utc_now().isoformat(),
            }
        )
        await self._send_turn_if_active(player_id)

    def unregister_connection(self, player_id: int) -> None:
        self.connections.pop(player_id, None)
        with self.session_factory() as session:
            player = session.get(Player, player_id)
            if player is not None:
                player.connected = False
                session.add(player)
                session.commit()
        logger.info("Player %s disconnected", player_id)
        self._schedule_admin_event(
            {
                "type": "player_disconnected",
                "playerId": player_id,
                "timestamp": utc_now().isoformat(),
            }
        )

    async def register_admin_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.admin_connections.add(websocket)
        await websocket.send_json({"type": "tournament_update", "timestamp": utc_now().isoformat()})

    def unregister_admin_connection(self, websocket: WebSocket) -> None:
        self.admin_connections.discard(websocket)

    async def handle_client_message(self, player_id: int, payload: dict) -> None:
        try:
            message = IncomingMove.model_validate(payload)
        except Exception:
            logger.warning("Ignoring invalid payload from player %s: %s", player_id, payload)
            return

        turn = self.turns_by_player.get(player_id)
        if turn is None:
            logger.info("Ignoring move from player %s because it is not their turn", player_id)
            return
        if turn.game_id != message.game_id:
            logger.info("Ignoring move from player %s for inactive game %s", player_id, message.game_id)
            return
        if turn.future.done():
            return

        turn.future.set_result(message.move.lower())

    def enroll_player(self, tournament_name: str, username: str) -> dict[str, Any]:
        normalized_tournament_name = tournament_name.strip()
        normalized_name = username.strip()
        if not normalized_tournament_name:
            raise HTTPException(status_code=400, detail="Tournament name is required")
        if not normalized_name:
            raise HTTPException(status_code=400, detail="Username is required")

        with self.session_factory() as session:
            tournaments = session.exec(select(Tournament).where(Tournament.name == normalized_tournament_name)).all()
            if not tournaments:
                raise HTTPException(status_code=404, detail="Tournament not found")
            if len(tournaments) > 1:
                raise HTTPException(status_code=409, detail="Tournament name is ambiguous")

            tournament = tournaments[0]
            tournament_id = tournament.id
            if tournament.registration_status != "open":
                raise HTTPException(status_code=400, detail="Tournament registration is closed")

            existing = session.exec(
                select(Player).where(Player.tournament_id == tournament_id, Player.name == normalized_name)
            ).first()
            if existing is not None:
                raise HTTPException(status_code=409, detail="Username is already taken in this tournament")

            player = Player(
                tournament_id=tournament_id,
                name=normalized_name,
                client_token=secrets.token_urlsafe(24),
            )
            session.add(player)
            session.commit()
            session.refresh(player)
            payload = {
                "tournament_id": tournament_id,
                "tournament_name": tournament.name,
                "player_id": player.id,
                "name": player.name,
                "client_token": player.client_token,
            }

        self._schedule_admin_event(
            {
                "type": "tournament_update",
                "tournamentId": tournament_id,
                "status": tournament.status,
                "timestamp": utc_now().isoformat(),
            }
        )
        return payload

    def create_tournament(self, name: str, total_rounds: int = 10) -> dict[str, Any]:
        with self.session_factory() as session:
            tournament = Tournament(name=name, total_rounds=total_rounds, status="pending", registration_status="closed")
            session.add(tournament)
            session.commit()
            session.refresh(tournament)
            payload = self._serialize_tournament_summary(session, tournament)
        self._schedule_admin_event({"type": "tournament_update", "tournamentId": payload["id"], "status": payload["status"]})
        return payload

    def update_tournament(self, tournament_id: int, *, name: str | None = None, total_rounds: int | None = None) -> dict[str, Any]:
        with self.session_factory() as session:
            tournament = self._get_tournament_or_404(session, tournament_id)
            if name is not None:
                normalized_name = name.strip()
                if not normalized_name:
                    raise HTTPException(status_code=400, detail="Tournament name is required")
                tournament.name = normalized_name
            if total_rounds is not None:
                if total_rounds < 1:
                    raise HTTPException(status_code=400, detail="Tournament must have at least one round")
                rounds = session.exec(select(Round).where(Round.tournament_id == tournament_id)).all()
                if rounds and total_rounds != tournament.total_rounds:
                    raise HTTPException(status_code=400, detail="Cannot change total rounds after the tournament has been started")
                tournament.total_rounds = total_rounds
            session.add(tournament)
            session.commit()
            payload = self._serialize_tournament_detail(session, tournament_id)
        self._schedule_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": payload["status"]})
        return payload

    def delete_tournament(self, tournament_id: int) -> None:
        with self.session_factory() as session:
            tournament = self._get_tournament_or_404(session, tournament_id)
            games = session.exec(select(Game).where(Game.tournament_id == tournament_id)).all()
            for game in games:
                self._cancel_game_task(game.id)
                self.runtime_games.pop(game.id, None)
                self._delete_game_records(session, game.id)

            for round_result in session.exec(select(RoundResult).where(RoundResult.tournament_id == tournament_id)).all():
                session.delete(round_result)
            for standing in session.exec(select(Standing).where(Standing.tournament_id == tournament_id)).all():
                session.delete(standing)
            for round_row in session.exec(select(Round).where(Round.tournament_id == tournament_id)).all():
                session.delete(round_row)
            for player in session.exec(select(Player).where(Player.tournament_id == tournament_id)).all():
                self.connections.pop(player.id, None)
                player.connected = False
                session.add(player)
                session.delete(player)

            session.delete(tournament)
            session.commit()

        self._schedule_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": "deleted"})

    def start_registration(self, tournament_id: int) -> dict[str, Any]:
        with self.session_factory() as session:
            tournament = self._get_tournament_or_404(session, tournament_id)
            tournament.registration_status = "open"
            if tournament.status == "pending":
                tournament.status = "registration"
            session.add(tournament)
            session.commit()
            payload = self._serialize_tournament_summary(session, tournament)
        self._schedule_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": payload["status"]})
        return payload

    def close_registration(self, tournament_id: int) -> dict[str, Any]:
        with self.session_factory() as session:
            tournament = self._get_tournament_or_404(session, tournament_id)
            tournament.registration_status = "closed"
            if tournament.status == "registration":
                tournament.status = "pending"
            session.add(tournament)
            session.commit()
            payload = self._serialize_tournament_summary(session, tournament)
        self._schedule_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": payload["status"]})
        return payload

    def start_tournament(self, total_rounds: int = 10) -> Tournament:
        payload = self.start_tournament_by_id(None, total_rounds=total_rounds, name=f"Tournament {utc_now().strftime('%Y%m%d%H%M%S')}")
        return payload["__model__"]

    def start_tournament_by_id(
        self,
        tournament_id: int | None,
        *,
        total_rounds: int | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            if tournament_id is None:
                if total_rounds is None:
                    total_rounds = 10
                tournament = Tournament(
                    name=name or f"Tournament {utc_now().strftime('%Y%m%d%H%M%S')}",
                    status="pending",
                    registration_status="closed",
                    total_rounds=total_rounds,
                )
                session.add(tournament)
                session.commit()
                session.refresh(tournament)
            else:
                tournament = self._get_tournament_or_404(session, tournament_id)
                if total_rounds is not None:
                    tournament.total_rounds = total_rounds
                if name:
                    tournament.name = name

            players = session.exec(select(Player).where(Player.tournament_id == tournament.id).order_by(Player.id)).all()
            if len(players) < 2:
                raise HTTPException(status_code=400, detail="At least two enrolled players are required")

            standings = session.exec(select(Standing).where(Standing.tournament_id == tournament.id)).all()
            if standings:
                raise HTTPException(status_code=400, detail="Tournament has already been started")

            tournament.status = "active"
            tournament.registration_status = "closed"
            tournament.started_at = utc_now()
            session.add(tournament)

            for player in players:
                session.add(Standing(tournament_id=tournament.id, player_id=player.id))

            for round_number in range(1, tournament.total_rounds + 1):
                session.add(Round(tournament_id=tournament.id, number=round_number, status="pending"))

            session.commit()
            payload = self._serialize_tournament_detail(session, tournament.id)
            payload["__model__"] = tournament

        self._schedule_admin_event({"type": "tournament_update", "tournamentId": payload["id"], "status": "active"})
        return payload

    async def start_round(self, round_number: int) -> tuple[Tournament, Round, list[Game], int | None]:
        with self.session_factory() as session:
            tournament = self._get_default_tournament(session)
            if tournament is None:
                raise HTTPException(status_code=404, detail="No active tournament")
            round_row = session.exec(
                select(Round).where(Round.tournament_id == tournament.id, Round.number == round_number)
            ).first()
            if round_row is None:
                round_row = Round(tournament_id=tournament.id, number=round_number, status="pending")
                session.add(round_row)
                session.commit()
                session.refresh(round_row)
        return await self.start_round_by_id(round_row.id)

    async def start_round_by_id(self, round_id: int) -> tuple[Tournament, Round, list[Game], int | None]:
        with self.session_factory() as session:
            round_row = session.get(Round, round_id)
            if round_row is None:
                raise HTTPException(status_code=404, detail="Round not found")
            tournament = session.get(Tournament, round_row.tournament_id)
            if tournament is None:
                raise HTTPException(status_code=404, detail="Tournament not found")
            if tournament.status != "active":
                raise HTTPException(status_code=400, detail="Tournament is not active")
            if round_row.status == "completed":
                raise HTTPException(status_code=400, detail="Round already completed")
            if session.exec(select(Game).where(Game.round_id == round_row.id)).first():
                raise HTTPException(status_code=400, detail="Round already has pairings")

            round_row.status = "active"
            round_row.started_at = utc_now()
            session.add(round_row)
            session.commit()
            session.refresh(round_row)

            standings = session.exec(
                select(Standing).where(Standing.tournament_id == tournament.id).order_by(Standing.points.desc(), Standing.player_id)
            ).all()
            previous_opponents = self._load_previous_opponents(session, tournament.id)
            swiss_players = [
                SwissPlayer(player_id=standing.player_id, points=standing.points, had_bye=standing.byes > 0)
                for standing in standings
            ]
            pairing = swiss_pair(swiss_players, previous_opponents)

            games: list[Game] = []
            for index, (first_player_id, second_player_id) in enumerate(pairing.pairs):
                black_player_id, white_player_id = (
                    (first_player_id, second_player_id)
                    if (round_row.number + index) % 2 == 1
                    else (second_player_id, first_player_id)
                )
                game = Game(
                    id=str(uuid.uuid4()),
                    tournament_id=tournament.id,
                    round_id=round_row.id,
                    round_number=round_row.number,
                    black_player_id=black_player_id,
                    white_player_id=white_player_id,
                    status="pending",
                    current_board=json.dumps(create_initial_board()),
                    next_turn="black",
                )
                session.add(game)
                games.append(game)

            if pairing.bye_player_id is not None:
                self._award_bye(session, tournament.id, round_row.number, pairing.bye_player_id)

            session.commit()
            for game in games:
                session.refresh(game)

        for game in games:
            task = asyncio.create_task(self.run_game(game.id))
            self.game_tasks[game.id] = task

        await self._broadcast_admin_event(
            {
                "type": "round_started",
                "tournamentId": tournament.id,
                "roundId": round_row.id,
                "roundNumber": round_row.number,
                "timestamp": utc_now().isoformat(),
            }
        )
        logger.info("Round %s started with %s games", round_row.number, len(games))
        return tournament, round_row, games, pairing.bye_player_id

    async def run_game(self, game_id: str) -> None:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None:
                return
            board = json.loads(game.current_board)
            runtime = RuntimeGame(
                game_id=game.id,
                black_player_id=game.black_player_id,
                white_player_id=game.white_player_id,
                board=board,
                next_color=BLACK,
            )
            self.runtime_games[game.id] = runtime
            game.status = "active"
            game.started_at = utc_now()
            session.add(game)
            session.commit()

        await self._broadcast_admin_event(self._build_game_started_event(game_id))
        await self._broadcast_game_update(runtime, last_move=None)
        turn_number = 1

        try:
            while runtime.next_color is not None:
                if self._game_is_finished(game_id):
                    return

                current_color = runtime.next_color
                assert current_color is not None
                current_player_id = runtime.player_for_color(current_color)
                possible_moves = legal_moves(runtime.board, current_color)

                if not possible_moves:
                    other_color = opponent(current_color)
                    if not legal_moves(runtime.board, other_color):
                        break

                    logger.info("Game %s auto-pass for player %s", game_id, current_player_id)
                    self._persist_move(game_id, current_player_id, turn_number, "pass", runtime.board, other_color)
                    runtime.next_color = other_color
                    await self._broadcast_admin_event(self._build_move_recorded_event(game_id, "pass", current_player_id))
                    await self._broadcast_game_update(runtime, last_move=None)
                    turn_number += 1
                    continue

                loop = asyncio.get_running_loop()
                turn = TurnContext(
                    game_id=game_id,
                    player_id=current_player_id,
                    color=current_color,
                    legal_moves=possible_moves,
                    future=loop.create_future(),
                    deadline=loop.time() + self.move_timeout_seconds,
                )
                # The deadline lives on the server so reconnects do not reset the clock.
                self.turns_by_player[current_player_id] = turn
                await self._send_turn(turn, runtime.board)

                try:
                    move = await asyncio.wait_for(turn.future, timeout=self.move_timeout_seconds)
                except asyncio.TimeoutError:
                    await self._finish_forfeit(game_id, loser_player_id=current_player_id, reason="timeout")
                    return
                except asyncio.CancelledError:
                    return
                finally:
                    self.turns_by_player.pop(current_player_id, None)

                if move == "__admin_stop__":
                    return
                if self._game_is_finished(game_id):
                    return
                if move not in possible_moves:
                    await self._finish_forfeit(game_id, loser_player_id=current_player_id, reason="illegal_move")
                    return

                result = apply_move(runtime.board, move, current_color)
                runtime.board = result.board
                runtime.next_color = next_turn_color(runtime.board, current_color)
                next_turn = color_name(runtime.next_color)
                self._persist_move(game_id, current_player_id, turn_number, move, runtime.board, next_turn)
                await self._update_game_state(game_id, runtime.board, move, next_turn)
                await self._broadcast_admin_event(self._build_move_recorded_event(game_id, move, current_player_id))
                await self._broadcast_game_update(runtime, last_move=move)
                turn_number += 1

            await self._finish_normal_game(game_id, runtime.board)
        finally:
            self.runtime_games.pop(game_id, None)
            self.game_tasks.pop(game_id, None)

    def get_standings(self, tournament_id: int | None = None) -> tuple[int, list[dict]]:
        with self.session_factory() as session:
            if tournament_id is not None:
                tournament = self._get_tournament_or_404(session, tournament_id)
            else:
                tournament = self._get_default_tournament(session)
                if tournament is None:
                    completed = session.exec(select(Tournament).order_by(Tournament.id.desc())).first()
                    if completed is None:
                        raise HTTPException(status_code=404, detail="No tournament found")
                    tournament = completed

            standings = session.exec(
                select(Standing, Player)
                .join(Player, Player.id == Standing.player_id)
                .where(Standing.tournament_id == tournament.id)
                .order_by(Standing.points.desc(), Standing.player_id)
            ).all()
            return tournament.id, [
                {
                    "player_id": standing.player_id,
                    "player_name": player.name,
                    "points": standing.points,
                    "wins": standing.wins,
                    "losses": standing.losses,
                    "draws": standing.draws,
                    "byes": standing.byes,
                }
                for standing, player in standings
            ]

    def get_game(self, game_id: str) -> dict:
        with self.session_factory() as session:
            return self._build_legacy_game_payload(session, game_id)

    def list_tournaments(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            tournaments = session.exec(select(Tournament).order_by(Tournament.created_at.desc())).all()
            return [self._serialize_tournament_summary(session, tournament) for tournament in tournaments]

    def get_tournament_detail(self, tournament_id: int) -> dict[str, Any]:
        with self.session_factory() as session:
            return self._serialize_tournament_detail(session, tournament_id)

    def get_round_detail(self, round_id: int) -> dict[str, Any]:
        with self.session_factory() as session:
            round_row = session.get(Round, round_id)
            if round_row is None:
                raise HTTPException(status_code=404, detail="Round not found")

            games = session.exec(select(Game).where(Game.round_id == round_id).order_by(Game.id)).all()
            return {
                "id": round_row.id,
                "tournamentId": round_row.tournament_id,
                "number": round_row.number,
                "status": round_row.status,
                "pairings": [self._serialize_pairing(session, game) for game in games],
                "results": [self._serialize_round_result(game) for game in games if game.result],
                "activeGames": [self._serialize_game_summary(session, game) for game in games if game.status == "active"],
            }

    def get_admin_game(self, game_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None:
                raise HTTPException(status_code=404, detail="Game not found")

            black_player = session.get(Player, game.black_player_id)
            white_player = session.get(Player, game.white_player_id)
            move_rows = session.exec(select(MoveLog).where(MoveLog.game_id == game_id).order_by(MoveLog.turn_number)).all()
            legal = []
            if game.next_turn in {"black", "white"}:
                legal = legal_moves(json.loads(game.current_board), BLACK if game.next_turn == "black" else WHITE)
            return {
                "id": game.id,
                "tournamentId": game.tournament_id,
                "roundId": game.round_id,
                "roundNumber": game.round_number,
                "status": game.status,
                "blackPlayerId": game.black_player_id,
                "whitePlayerId": game.white_player_id,
                "blackPlayerName": black_player.name if black_player else f"Player {game.black_player_id}",
                "whitePlayerName": white_player.name if white_player else f"Player {game.white_player_id}",
                "board": json.loads(game.current_board),
                "currentTurn": game.next_turn,
                "countdownMs": self._remaining_ms_for_game(game.id),
                "lastMove": game.last_move,
                "legalMoves": legal,
                "blackScore": game.black_score,
                "whiteScore": game.white_score,
                "winner": self._winner_name_from_game(game),
                "result": game.result,
                "forfeitReason": game.forfeit_reason,
                "moveHistory": [self._serialize_move(session, row, game) for row in move_rows],
                "finalScore": {"black": game.black_score, "white": game.white_score},
            }

    def create_admin_player(self, tournament_id: int, username: str) -> dict[str, Any]:
        normalized_name = username.strip()
        if not normalized_name:
            raise HTTPException(status_code=400, detail="Player name is required")

        with self.session_factory() as session:
            tournament = self._get_tournament_or_404(session, tournament_id)
            if tournament.status == "completed":
                raise HTTPException(status_code=400, detail="Cannot add players to a completed tournament")
            if session.exec(
                select(Player).where(Player.tournament_id == tournament_id, Player.name == normalized_name)
            ).first():
                raise HTTPException(status_code=409, detail="Username is already taken in this tournament")

            player = Player(
                tournament_id=tournament_id,
                name=normalized_name,
                client_token=secrets.token_urlsafe(24),
            )
            session.add(player)
            session.commit()
            session.refresh(player)

            existing_standings = session.exec(select(Standing).where(Standing.tournament_id == tournament_id)).first()
            if existing_standings is not None:
                session.add(Standing(tournament_id=tournament_id, player_id=player.id))
                session.commit()
                self._recalculate_standings(session, tournament_id)
                session.commit()

            payload = self._serialize_player_row(session, player)

        self._schedule_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": tournament.status})
        return payload

    def update_player(self, player_id: int, *, name: str | None = None) -> dict[str, Any]:
        with self.session_factory() as session:
            player = session.get(Player, player_id)
            if player is None:
                raise HTTPException(status_code=404, detail="Player not found")
            if name is not None:
                normalized_name = name.strip()
                if not normalized_name:
                    raise HTTPException(status_code=400, detail="Player name is required")
                duplicate = session.exec(
                    select(Player).where(
                        Player.tournament_id == player.tournament_id,
                        Player.name == normalized_name,
                        Player.id != player_id,
                    )
                ).first()
                if duplicate is not None:
                    raise HTTPException(status_code=409, detail="Username is already taken in this tournament")
                player.name = normalized_name
            session.add(player)
            session.commit()
            payload = self._serialize_player_row(session, player)
        self._schedule_admin_event({"type": "tournament_update", "tournamentId": payload["tournamentId"], "status": "active"})
        return payload

    def delete_player(self, player_id: int) -> None:
        with self.session_factory() as session:
            player = session.get(Player, player_id)
            if player is None:
                raise HTTPException(status_code=404, detail="Player not found")
            tournament_id = player.tournament_id

            games = session.exec(
                select(Game).where((Game.black_player_id == player_id) | (Game.white_player_id == player_id))
            ).all()
            for game in games:
                self._cancel_game_task(game.id)
                self.runtime_games.pop(game.id, None)
                self._delete_game_records(session, game.id)

            for round_result in session.exec(select(RoundResult).where(RoundResult.player_id == player_id)).all():
                session.delete(round_result)
            standing = session.exec(
                select(Standing).where(Standing.tournament_id == tournament_id, Standing.player_id == player_id)
            ).first()
            if standing is not None:
                session.delete(standing)

            self.connections.pop(player_id, None)
            player.connected = False
            session.add(player)
            session.delete(player)

            self._recalculate_standings(session, tournament_id)
            self._refresh_competition_state(session, tournament_id)
            session.commit()

        self._schedule_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": "active"})

    def list_players(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            active_tournament = self._get_default_tournament(session)
            tournament_id = active_tournament.id if active_tournament is not None else None
            return self._list_players_for_tournament(session, tournament_id)

    def list_admin_standings(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            tournament = self._get_default_tournament(session)
            if tournament is None:
                tournament = session.exec(select(Tournament).order_by(Tournament.id.desc())).first()
            if tournament is None:
                return []

            standings = session.exec(
                select(Standing, Player)
                .join(Player, Player.id == Standing.player_id)
                .where(Standing.tournament_id == tournament.id)
                .order_by(Standing.points.desc(), Standing.player_id)
            ).all()
            differential = self._disc_differential_for_tournament(session, tournament.id)
            return [
                {
                    "rank": index + 1,
                    "playerId": standing.player_id,
                    "playerName": player.name,
                    "score": standing.points,
                    "wins": standing.wins,
                    "losses": standing.losses,
                    "draws": standing.draws,
                    "byes": standing.byes,
                    "discDifferential": differential.get(standing.player_id),
                }
                for index, (standing, player) in enumerate(standings)
            ]

    def list_live_games(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            games = session.exec(
                select(Game).where(Game.status.in_(["pending", "active"])).order_by(Game.round_number, Game.id)
            ).all()
            return [self._serialize_game_summary(session, game) for game in games]

    async def create_game(self, round_id: int, black_player_id: int, white_player_id: int) -> dict[str, Any]:
        if black_player_id == white_player_id:
            raise HTTPException(status_code=400, detail="A player cannot play against themselves")

        with self.session_factory() as session:
            round_row = session.get(Round, round_id)
            if round_row is None:
                raise HTTPException(status_code=404, detail="Round not found")
            tournament = self._get_tournament_or_404(session, round_row.tournament_id)
            if round_row.status == "completed":
                raise HTTPException(status_code=400, detail="Cannot add games to a completed round")

            black_player = session.get(Player, black_player_id)
            white_player = session.get(Player, white_player_id)
            if black_player is None or white_player is None:
                raise HTTPException(status_code=404, detail="One or more players were not found")
            if black_player.tournament_id != tournament.id or white_player.tournament_id != tournament.id:
                raise HTTPException(status_code=400, detail="Players must belong to the same tournament as the round")

            active_conflict = session.exec(
                select(Game).where(
                    Game.status.in_(["pending", "active"]),
                    (
                        (Game.black_player_id == black_player_id)
                        | (Game.white_player_id == black_player_id)
                        | (Game.black_player_id == white_player_id)
                        | (Game.white_player_id == white_player_id)
                    ),
                )
            ).first()
            if active_conflict is not None:
                raise HTTPException(status_code=400, detail="One or more selected players already have a pending or active game")

            game = Game(
                id=str(uuid.uuid4()),
                tournament_id=tournament.id,
                round_id=round_row.id,
                round_number=round_row.number,
                black_player_id=black_player_id,
                white_player_id=white_player_id,
                status="pending",
                current_board=json.dumps(create_initial_board()),
                next_turn="black",
            )
            session.add(game)
            if round_row.status == "pending":
                round_row.status = "active"
                session.add(round_row)
            session.commit()
            payload = self.get_admin_game(game.id)

        self._schedule_admin_event({"type": "tournament_update", "tournamentId": payload["tournamentId"], "status": tournament.status})
        return payload

    async def update_game(
        self,
        game_id: str,
        *,
        round_id: int | None = None,
        black_player_id: int | None = None,
        white_player_id: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        start_now = False
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None:
                raise HTTPException(status_code=404, detail="Game not found")
            if game.status in FINAL_GAME_STATUSES:
                raise HTTPException(status_code=400, detail="Completed games cannot be edited")

            if round_id is not None:
                if game.status != "pending":
                    raise HTTPException(status_code=400, detail="Only pending games can be reassigned to a different round")
                round_row = session.get(Round, round_id)
                if round_row is None:
                    raise HTTPException(status_code=404, detail="Round not found")
                if round_row.tournament_id != game.tournament_id:
                    raise HTTPException(status_code=400, detail="Game can only be moved within the same tournament")
                game.round_id = round_row.id
                game.round_number = round_row.number

            next_black = black_player_id or game.black_player_id
            next_white = white_player_id or game.white_player_id
            if black_player_id is not None or white_player_id is not None:
                if game.status != "pending":
                    raise HTTPException(status_code=400, detail="Only pending games can change players")
                if next_black == next_white:
                    raise HTTPException(status_code=400, detail="A player cannot play against themselves")
                black_player = session.get(Player, next_black)
                white_player = session.get(Player, next_white)
                if black_player is None or white_player is None:
                    raise HTTPException(status_code=404, detail="One or more players were not found")
                if black_player.tournament_id != game.tournament_id or white_player.tournament_id != game.tournament_id:
                    raise HTTPException(status_code=400, detail="Players must belong to the same tournament as the game")
                game.black_player_id = next_black
                game.white_player_id = next_white

            if status is not None:
                if status == "active":
                    if game.status != "pending":
                        raise HTTPException(status_code=400, detail="Only pending games can be started")
                    game.status = "active"
                    start_now = True
                elif status != "pending":
                    raise HTTPException(status_code=400, detail="Unsupported game status update")

            session.add(game)
            session.commit()

        if start_now:
            task = asyncio.create_task(self.run_game(game_id))
            self.game_tasks[game_id] = task
        return self.get_admin_game(game_id)

    def delete_game(self, game_id: str) -> None:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None:
                raise HTTPException(status_code=404, detail="Game not found")
            tournament_id = game.tournament_id
            self._cancel_game_task(game_id)
            self.runtime_games.pop(game_id, None)
            self._delete_game_records(session, game_id)
            self._recalculate_standings(session, tournament_id)
            self._refresh_competition_state(session, tournament_id)
            session.commit()

        self._schedule_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": "active"})

    async def force_end_game(self, game_id: str) -> dict[str, Any]:
        board = self.runtime_games.get(game_id).board if game_id in self.runtime_games else None
        if board is None:
            with self.session_factory() as session:
                game = session.get(Game, game_id)
                if game is None:
                    raise HTTPException(status_code=404, detail="Game not found")
                board = json.loads(game.current_board)
        await self._finish_normal_game(game_id, board, forced=True)
        self._cancel_game_task(game_id)
        return self.get_admin_game(game_id)

    async def forfeit_player(self, player_id: int) -> dict[str, Any]:
        with self.session_factory() as session:
            active_game = session.exec(
                select(Game).where(
                    Game.status == "active",
                    ((Game.black_player_id == player_id) | (Game.white_player_id == player_id)),
                )
            ).first()
            if active_game is None:
                raise HTTPException(status_code=404, detail="Player has no active game")
            game_id = active_game.id

        await self._finish_forfeit(game_id, loser_player_id=player_id, reason="forfeit")
        self._cancel_game_task(game_id)
        with self.session_factory() as session:
            player = session.get(Player, player_id)
            return {
                "id": player.id,
                "name": player.name,
                "connected": player.connected,
            }

    async def _send_turn_if_active(self, player_id: int) -> None:
        turn = self.turns_by_player.get(player_id)
        if turn is None:
            return
        runtime = self.runtime_games.get(turn.game_id)
        if runtime is None:
            return
        await self._send_turn(turn, runtime.board)

    async def _send_turn(self, turn: TurnContext, board: list[list[str]]) -> None:
        websocket = self.connections.get(turn.player_id)
        if websocket is None:
            return
        remaining_ms = max(0, int((turn.deadline - asyncio.get_running_loop().time()) * 1000))
        payload = {
            "type": "your_turn",
            "game_id": turn.game_id,
            "color": color_name(turn.color),
            "board": [row[:] for row in board],
            "legal_moves": turn.legal_moves,
            "deadline_ms": remaining_ms,
        }
        try:
            await websocket.send_json(payload)
        except Exception:
            logger.warning("Failed to send your_turn to player %s", turn.player_id)

    async def _broadcast_game_update(self, runtime: RuntimeGame, last_move: str | None) -> None:
        remaining_ms = self._remaining_ms_for_game(runtime.game_id)
        black_score, white_score = score(runtime.board)
        payload = {
            "type": "game_update",
            "game_id": runtime.game_id,
            "board": [row[:] for row in runtime.board],
            "next_player": color_name(runtime.next_color),
            "last_move": last_move,
        }
        await self._broadcast_to_players(runtime.black_player_id, runtime.white_player_id, payload)
        await self._broadcast_admin_event(
            {
                "type": "game_update",
                "gameId": runtime.game_id,
                "board": [row[:] for row in runtime.board],
                "nextPlayer": color_name(runtime.next_color),
                "currentTurn": color_name(runtime.next_color),
                "lastMove": last_move,
                "blackScore": black_score,
                "whiteScore": white_score,
                "deadlineMs": remaining_ms,
                "timestamp": utc_now().isoformat(),
            }
        )

    async def _broadcast_game_over(
        self,
        game_id: str,
        black_player_id: int,
        white_player_id: int,
        board: list[list[str]],
        result: str,
        *,
        event_type: str = "game_over",
        reason: str | None = None,
    ) -> None:
        black_score, white_score = score(board)
        payload = {
            "type": "game_over",
            "game_id": game_id,
            "black_score": black_score,
            "white_score": white_score,
            "result": result,
        }
        await self._broadcast_to_players(black_player_id, white_player_id, payload)
        admin_payload = {
            "type": event_type,
            "gameId": game_id,
            "blackScore": black_score,
            "whiteScore": white_score,
            "result": result,
            "timestamp": utc_now().isoformat(),
        }
        if reason:
            admin_payload["reason"] = reason
        await self._broadcast_admin_event(admin_payload)

    async def _broadcast_to_players(self, first_player_id: int, second_player_id: int, payload: dict) -> None:
        for player_id in (first_player_id, second_player_id):
            websocket = self.connections.get(player_id)
            if websocket is None:
                continue
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.warning("Failed to deliver message to player %s", player_id)

    async def _broadcast_admin_event(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self.admin_connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.admin_connections.discard(websocket)

    def _schedule_admin_event(self, payload: dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._broadcast_admin_event(payload))

    def _persist_move(self, game_id: str, player_id: int, turn_number: int, move: str, board: list[list[str]], next_turn: str | None) -> None:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None:
                return

            black_score, white_score = score(board)
            game.current_board = json.dumps(board)
            game.last_move = None if move == "pass" else move
            game.next_turn = next_turn
            game.black_score = black_score
            game.white_score = white_score
            session.add(game)
            session.add(
                MoveLog(
                    game_id=game_id,
                    player_id=player_id,
                    turn_number=turn_number,
                    move=move,
                    board_after=json.dumps(board),
                )
            )
            session.commit()

    def _load_previous_opponents(self, session: Session, tournament_id: int) -> dict[int, set[int]]:
        rows = session.exec(select(RoundResult).where(RoundResult.tournament_id == tournament_id)).all()
        opponents: dict[int, set[int]] = {}
        for row in rows:
            if row.opponent_player_id is None:
                continue
            opponents.setdefault(row.player_id, set()).add(row.opponent_player_id)
        return opponents

    def _award_bye(self, session: Session, tournament_id: int, round_number: int, player_id: int) -> None:
        standing = session.exec(
            select(Standing).where(Standing.tournament_id == tournament_id, Standing.player_id == player_id)
        ).first()
        if standing is None:
            return
        standing.points += 1.0
        standing.byes += 1
        session.add(standing)
        session.add(
            RoundResult(
                tournament_id=tournament_id,
                round_number=round_number,
                player_id=player_id,
                opponent_player_id=None,
                game_id=None,
                points_awarded=1.0,
                outcome="bye",
            )
        )

    def _update_round_if_complete(self, tournament_id: int, round_number: int) -> None:
        with self.session_factory() as session:
            games = session.exec(
                select(Game).where(Game.tournament_id == tournament_id, Game.round_number == round_number)
            ).all()
            if any(game.status not in FINAL_GAME_STATUSES for game in games):
                return
            round_row = session.exec(
                select(Round).where(Round.tournament_id == tournament_id, Round.number == round_number)
            ).first()
            if round_row is not None:
                round_row.status = "completed"
                round_row.completed_at = utc_now()
                session.add(round_row)
                tournament = session.get(Tournament, tournament_id)
                if tournament is not None:
                    remaining = session.exec(
                        select(Round).where(Round.tournament_id == tournament_id, Round.status != "completed")
                    ).all()
                    if not remaining:
                        tournament.status = "completed"
                        tournament.completed_at = utc_now()
                        session.add(tournament)
                session.commit()

    async def _finish_normal_game(self, game_id: str, board: list[list[str]], forced: bool = False) -> None:
        black_score, white_score = score(board)
        game_winner = winner(board)
        if game_winner == BLACK:
            result = "black_win"
        elif game_winner == WHITE:
            result = "white_win"
        else:
            result = "draw"

        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None or game.status in FINAL_GAME_STATUSES:
                return

            game.status = "forced_end" if forced else "completed"
            game.current_board = json.dumps(board)
            game.next_turn = None
            game.black_score = black_score
            game.white_score = white_score
            game.result = result
            game.finished_at = utc_now()
            if result == "black_win":
                game.winner_player_id = game.black_player_id
                game.loser_player_id = game.white_player_id
            elif result == "white_win":
                game.winner_player_id = game.white_player_id
                game.loser_player_id = game.black_player_id

            session.add(game)
            self._apply_result_to_standings(session, game, result)
            session.commit()

            tournament_id = game.tournament_id
            round_number = game.round_number
            black_player_id = game.black_player_id
            white_player_id = game.white_player_id

        await self._broadcast_game_over(
            game_id,
            black_player_id,
            white_player_id,
            board,
            result,
            event_type="game_over" if not forced else "game_over",
        )
        self._update_round_if_complete(tournament_id, round_number)
        await self._broadcast_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": "active"})

    async def _finish_forfeit(self, game_id: str, loser_player_id: int, reason: str) -> None:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None or game.status in FINAL_GAME_STATUSES:
                return

            if loser_player_id == game.black_player_id:
                result = "white_win"
                winner_player_id = game.white_player_id
                loser_color = BLACK
            else:
                result = "black_win"
                winner_player_id = game.black_player_id
                loser_color = WHITE

            board = json.loads(game.current_board)
            black_score, white_score = score(board)
            game.status = "forfeit"
            game.result = result
            game.forfeit_reason = reason
            game.winner_player_id = winner_player_id
            game.loser_player_id = loser_player_id
            game.next_turn = None
            game.black_score = black_score
            game.white_score = white_score
            game.finished_at = utc_now()
            session.add(game)
            self._apply_result_to_standings(session, game, result)
            session.commit()

            tournament_id = game.tournament_id
            round_number = game.round_number
            black_player_id = game.black_player_id
            white_player_id = game.white_player_id

        logger.info("Game %s ended by %s forfeiture (%s)", game_id, color_name(loser_color), reason)
        event_type = "forfeit" if reason == "forfeit" else reason
        await self._broadcast_game_over(game_id, black_player_id, white_player_id, board, result, event_type=event_type, reason=reason)
        self._update_round_if_complete(tournament_id, round_number)
        await self._broadcast_admin_event({"type": "tournament_update", "tournamentId": tournament_id, "status": "active"})

    def _apply_result_to_standings(self, session: Session, game: Game, result: str) -> None:
        existing = session.exec(select(RoundResult).where(Game.id == RoundResult.game_id, RoundResult.player_id == game.black_player_id)).first()
        if existing is not None:
            return

        black_standing = session.exec(
            select(Standing).where(Standing.tournament_id == game.tournament_id, Standing.player_id == game.black_player_id)
        ).first()
        white_standing = session.exec(
            select(Standing).where(Standing.tournament_id == game.tournament_id, Standing.player_id == game.white_player_id)
        ).first()
        if black_standing is None or white_standing is None:
            return

        if result == "black_win":
            black_standing.points += 1.0
            black_standing.wins += 1
            white_standing.losses += 1
            black_points, white_points = 1.0, 0.0
        elif result == "white_win":
            white_standing.points += 1.0
            white_standing.wins += 1
            black_standing.losses += 1
            black_points, white_points = 0.0, 1.0
        else:
            black_standing.points += 0.5
            white_standing.points += 0.5
            black_standing.draws += 1
            white_standing.draws += 1
            black_points = white_points = 0.5

        session.add(black_standing)
        session.add(white_standing)
        session.add(
            RoundResult(
                tournament_id=game.tournament_id,
                round_number=game.round_number,
                player_id=game.black_player_id,
                opponent_player_id=game.white_player_id,
                game_id=game.id,
                points_awarded=black_points,
                outcome=result,
            )
        )
        session.add(
            RoundResult(
                tournament_id=game.tournament_id,
                round_number=game.round_number,
                player_id=game.white_player_id,
                opponent_player_id=game.black_player_id,
                game_id=game.id,
                points_awarded=white_points,
                outcome=result,
            )
        )

    async def _update_game_state(self, game_id: str, board: list[list[str]], last_move: str, next_turn: str | None) -> None:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None:
                return
            black_score, white_score = score(board)
            game.current_board = json.dumps(board)
            game.last_move = last_move
            game.next_turn = next_turn
            game.black_score = black_score
            game.white_score = white_score
            session.add(game)
            session.commit()

    def _get_tournament_or_404(self, session: Session, tournament_id: int) -> Tournament:
        tournament = session.get(Tournament, tournament_id)
        if tournament is None:
            raise HTTPException(status_code=404, detail="Tournament not found")
        return tournament

    def _get_default_tournament(self, session: Session) -> Tournament | None:
        return session.exec(
            select(Tournament)
            .where(Tournament.status == "active")
            .order_by(Tournament.started_at.desc(), Tournament.id.desc())
        ).first()

    def _serialize_tournament_summary(self, session: Session, tournament: Tournament) -> dict[str, Any]:
        rounds = session.exec(select(Round).where(Round.tournament_id == tournament.id).order_by(Round.number)).all()
        players = session.exec(select(Player).where(Player.tournament_id == tournament.id)).all()
        active_games = session.exec(
            select(Game).where(Game.tournament_id == tournament.id, Game.status.in_(["pending", "active"]))
        ).all()
        current_round = max((round_row.number for round_row in rounds if round_row.status in {"active", "completed"}), default=None)
        return {
            "id": tournament.id,
            "name": tournament.name,
            "status": tournament.status,
            "registrationStatus": tournament.registration_status,
            "playerCount": len(players),
            "connectedPlayers": sum(1 for player in players if player.connected),
            "currentRound": current_round,
            "totalRounds": tournament.total_rounds,
            "createdAt": tournament.created_at.isoformat(),
            "activeGames": [self._serialize_game_summary(session, game) for game in active_games],
        }

    def _serialize_tournament_detail(self, session: Session, tournament_id: int) -> dict[str, Any]:
        tournament = self._get_tournament_or_404(session, tournament_id)
        summary = self._serialize_tournament_summary(session, tournament)
        rounds = session.exec(select(Round).where(Round.tournament_id == tournament.id).order_by(Round.number)).all()
        summary["rounds"] = [
            {
                "id": round_row.id,
                "roundNumber": round_row.number,
                "number": round_row.number,
                "status": round_row.status,
                "pairings": [
                    self._serialize_pairing(session, game)
                    for game in session.exec(select(Game).where(Game.round_id == round_row.id)).all()
                ],
            }
            for round_row in rounds
        ]
        summary["standings"] = self.list_admin_standings_for_tournament(session, tournament.id)
        summary["players"] = self._list_players_for_tournament(session, tournament.id)
        summary["activeGames"] = [
            self._serialize_game_summary(session, game)
            for game in session.exec(select(Game).where(Game.tournament_id == tournament.id, Game.status == "active")).all()
        ]
        return summary

    def list_admin_standings_for_tournament(self, session: Session, tournament_id: int) -> list[dict[str, Any]]:
        standings = session.exec(
            select(Standing, Player)
            .join(Player, Player.id == Standing.player_id)
            .where(Standing.tournament_id == tournament_id)
            .order_by(Standing.points.desc(), Standing.player_id)
        ).all()
        differential = self._disc_differential_for_tournament(session, tournament_id)
        return [
            {
                "rank": index + 1,
                "playerId": standing.player_id,
                "playerName": player.name,
                "score": standing.points,
                "wins": standing.wins,
                "losses": standing.losses,
                "draws": standing.draws,
                "byes": standing.byes,
                "discDifferential": differential.get(standing.player_id),
            }
            for index, (standing, player) in enumerate(standings)
        ]

    def _serialize_game_summary(self, session: Session, game: Game) -> dict[str, Any]:
        black_player = session.get(Player, game.black_player_id)
        white_player = session.get(Player, game.white_player_id)
        return {
            "id": game.id,
            "tournamentId": game.tournament_id,
            "roundId": game.round_id,
            "roundNumber": game.round_number,
            "status": game.status,
            "blackPlayerId": game.black_player_id,
            "whitePlayerId": game.white_player_id,
            "blackPlayerName": black_player.name if black_player else f"Player {game.black_player_id}",
            "whitePlayerName": white_player.name if white_player else f"Player {game.white_player_id}",
            "board": json.loads(game.current_board),
            "currentTurn": game.next_turn,
            "countdownMs": self._remaining_ms_for_game(game.id),
            "lastMove": game.last_move,
            "blackScore": game.black_score,
            "whiteScore": game.white_score,
            "scoreDifference": abs(game.black_score - game.white_score),
            "updatedAt": (game.finished_at or game.started_at or game.created_at if hasattr(game, "created_at") else utc_now()).isoformat(),
            "forfeitReason": game.forfeit_reason,
        }

    def _serialize_pairing(self, session: Session, game: Game) -> dict[str, Any]:
        summary = self._serialize_game_summary(session, game)
        return {
            "gameId": summary["id"],
            "board": summary["board"],
            "blackPlayerId": summary["blackPlayerId"],
            "whitePlayerId": summary["whitePlayerId"],
            "blackPlayerName": summary["blackPlayerName"],
            "whitePlayerName": summary["whitePlayerName"],
            "status": summary["status"],
            "result": game.result,
            "roundNumber": game.round_number,
        }

    def _serialize_round_result(self, game: Game) -> dict[str, Any]:
        return {"gameId": game.id, "result": game.result, "winner": self._winner_name_from_game(game)}

    def _serialize_move(self, session: Session, move: MoveLog, game: Game) -> dict[str, Any]:
        player = session.get(Player, move.player_id)
        if move.player_id == game.black_player_id:
            color = "black"
        elif move.player_id == game.white_player_id:
            color = "white"
        else:
            color = None
        return {
            "id": move.id,
            "turnNumber": move.turn_number,
            "playerId": move.player_id,
            "player": player.name if player else f"Player {move.player_id}",
            "color": color,
            "move": move.move,
            "boardAfter": json.loads(move.board_after),
            "timestamp": move.created_at.isoformat(),
        }

    def _list_players_for_tournament(self, session: Session, tournament_id: int | None) -> list[dict[str, Any]]:
        query = select(Player).order_by(Player.id)
        if tournament_id is not None:
            query = query.where(Player.tournament_id == tournament_id)
        players = session.exec(query).all()

        standings_by_player: dict[int, Standing] = {}
        if tournament_id is not None:
            standings = session.exec(select(Standing).where(Standing.tournament_id == tournament_id)).all()
            standings_by_player = {standing.player_id: standing for standing in standings}

        games_query = select(Game)
        if tournament_id is not None:
            games_query = games_query.where(Game.tournament_id == tournament_id)
        games = session.exec(games_query).all()

        current_games: dict[int, str] = {}
        games_played: dict[int, int] = {player.id: 0 for player in players if player.id is not None}
        disc_differential: dict[int, int] = {player.id: 0 for player in players if player.id is not None}
        for game in games:
            games_played[game.black_player_id] = games_played.get(game.black_player_id, 0) + 1
            games_played[game.white_player_id] = games_played.get(game.white_player_id, 0) + 1
            disc_differential[game.black_player_id] = disc_differential.get(game.black_player_id, 0) + (game.black_score - game.white_score)
            disc_differential[game.white_player_id] = disc_differential.get(game.white_player_id, 0) + (game.white_score - game.black_score)
            if game.status == "active":
                current_games[game.black_player_id] = game.id
                current_games[game.white_player_id] = game.id

        return [self._serialize_player_row(session, player, standings_by_player, current_games, games_played, disc_differential) for player in players]

    def _serialize_player_row(
        self,
        session: Session,
        player: Player,
        standings_by_player: dict[int, Standing] | None = None,
        current_games: dict[int, str] | None = None,
        games_played: dict[int, int] | None = None,
        disc_differential: dict[int, int] | None = None,
    ) -> dict[str, Any]:
        if standings_by_player is None:
            standings_by_player = {}
            if player.tournament_id is not None:
                standings = session.exec(select(Standing).where(Standing.tournament_id == player.tournament_id)).all()
                standings_by_player = {standing.player_id: standing for standing in standings}
        if current_games is None or games_played is None or disc_differential is None:
            games = session.exec(
                select(Game).where((Game.black_player_id == player.id) | (Game.white_player_id == player.id))
            ).all()
            current_games = {}
            games_played = {player.id: len(games)}
            disc_value = 0
            for game in games:
                if game.status == "active":
                    current_games[player.id] = game.id
                if player.id == game.black_player_id:
                    disc_value += game.black_score - game.white_score
                else:
                    disc_value += game.white_score - game.black_score
            disc_differential = {player.id: disc_value}

        return {
            "id": player.id,
            "tournamentId": player.tournament_id,
            "name": player.name,
            "connected": player.connected,
            "score": standings_by_player.get(player.id).points if player.id in standings_by_player else 0,
            "currentGameId": current_games.get(player.id),
            "gamesPlayed": games_played.get(player.id, 0),
            "discDifferential": disc_differential.get(player.id, 0),
        }

    def _build_legacy_game_payload(self, session: Session, game_id: str) -> dict[str, Any]:
        game = session.get(Game, game_id)
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")
        move_rows = session.exec(select(MoveLog).where(MoveLog.game_id == game_id).order_by(MoveLog.turn_number)).all()
        return {
            "game_id": game.id,
            "round_number": game.round_number,
            "status": game.status,
            "black_player_id": game.black_player_id,
            "white_player_id": game.white_player_id,
            "board": json.loads(game.current_board),
            "next_turn": game.next_turn,
            "last_move": game.last_move,
            "result": game.result,
            "forfeit_reason": game.forfeit_reason,
            "black_score": game.black_score,
            "white_score": game.white_score,
            "moves": [
                {
                    "player_id": move.player_id,
                    "turn_number": move.turn_number,
                    "move": move.move,
                    "board_after": json.loads(move.board_after),
                    "created_at": move.created_at,
                }
                for move in move_rows
            ],
        }

    def _disc_differential_for_tournament(self, session: Session, tournament_id: int) -> dict[int, int]:
        games = session.exec(select(Game).where(Game.tournament_id == tournament_id)).all()
        differential: dict[int, int] = {}
        for game in games:
            differential[game.black_player_id] = differential.get(game.black_player_id, 0) + (game.black_score - game.white_score)
            differential[game.white_player_id] = differential.get(game.white_player_id, 0) + (game.white_score - game.black_score)
        return differential

    def _remaining_ms_for_game(self, game_id: str) -> int | None:
        for turn in self.turns_by_player.values():
            if turn.game_id == game_id:
                try:
                    now = asyncio.get_running_loop().time()
                except RuntimeError:
                    return None
                return max(0, int((turn.deadline - now) * 1000))
        return None

    def _winner_name_from_game(self, game: Game) -> str | None:
        if game.result == "black_win":
            return "black"
        if game.result == "white_win":
            return "white"
        if game.result == "draw":
            return "draw"
        return None

    def _build_move_recorded_event(self, game_id: str, move: str, player_id: int) -> dict[str, Any]:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            player = session.get(Player, player_id)
            if game is None:
                return {"type": "move_recorded", "gameId": game_id, "move": {"move": move}}
            return {
                "type": "move_recorded",
                "gameId": game_id,
                "roundId": game.round_id,
                "roundNumber": game.round_number,
                "lastMove": None if move == "pass" else move,
                "blackScore": game.black_score,
                "whiteScore": game.white_score,
                "move": {
                    "turnNumber": session.exec(select(MoveLog).where(MoveLog.game_id == game_id).order_by(MoveLog.turn_number.desc())).first().turn_number
                    if session.exec(select(MoveLog).where(MoveLog.game_id == game_id).order_by(MoveLog.turn_number.desc())).first()
                    else None,
                    "playerId": player_id,
                    "player": player.name if player else f"Player {player_id}",
                    "color": "black" if player_id == game.black_player_id else "white",
                    "move": move,
                    "boardAfter": json.loads(game.current_board),
                },
                "timestamp": utc_now().isoformat(),
            }

    def _build_game_started_event(self, game_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            if game is None:
                return {"type": "game_started", "gameId": game_id}
            payload = self._serialize_game_summary(session, game)
            payload["type"] = "game_started"
            payload["gameId"] = payload.pop("id")
            payload["timestamp"] = utc_now().isoformat()
            return payload

    def _cancel_game_task(self, game_id: str) -> None:
        task = self.game_tasks.get(game_id)
        if task is not None:
            task.cancel()
        for player_id, turn in list(self.turns_by_player.items()):
            if turn.game_id == game_id and not turn.future.done():
                turn.future.set_result("__admin_stop__")

    def _game_is_finished(self, game_id: str) -> bool:
        with self.session_factory() as session:
            game = session.get(Game, game_id)
            return bool(game and game.status in FINAL_GAME_STATUSES)

    def _delete_game_records(self, session: Session, game_id: str) -> None:
        game = session.get(Game, game_id)
        if game is None:
            return
        for move in session.exec(select(MoveLog).where(MoveLog.game_id == game_id)).all():
            session.delete(move)
        for round_result in session.exec(select(RoundResult).where(RoundResult.game_id == game_id)).all():
            session.delete(round_result)
        session.delete(game)

    def _recalculate_standings(self, session: Session, tournament_id: int) -> None:
        players = session.exec(select(Player).where(Player.tournament_id == tournament_id)).all()
        player_ids = {player.id for player in players if player.id is not None}
        standings = session.exec(select(Standing).where(Standing.tournament_id == tournament_id)).all()
        standings_by_player = {standing.player_id: standing for standing in standings}

        for standing in standings:
            if standing.player_id not in player_ids:
                session.delete(standing)

        has_started = bool(
            session.exec(select(Round).where(Round.tournament_id == tournament_id)).first()
            or session.exec(select(RoundResult).where(RoundResult.tournament_id == tournament_id)).first()
            or standings
        )
        if not has_started:
            return

        for player_id in player_ids:
            if player_id not in standings_by_player:
                standing = Standing(tournament_id=tournament_id, player_id=player_id)
                session.add(standing)
                standings_by_player[player_id] = standing

        for standing in standings_by_player.values():
            standing.points = 0.0
            standing.wins = 0
            standing.losses = 0
            standing.draws = 0
            standing.byes = 0
            session.add(standing)

        results = session.exec(select(RoundResult).where(RoundResult.tournament_id == tournament_id)).all()
        for result in results:
            standing = standings_by_player.get(result.player_id)
            if standing is None:
                continue
            standing.points += result.points_awarded
            if result.outcome == "bye":
                standing.byes += 1
            elif result.outcome == "draw":
                standing.draws += 1
            elif result.points_awarded == 1.0:
                standing.wins += 1
            else:
                standing.losses += 1
            session.add(standing)

    def _refresh_competition_state(self, session: Session, tournament_id: int) -> None:
        rounds = session.exec(select(Round).where(Round.tournament_id == tournament_id).order_by(Round.number)).all()
        active_round_found = False
        for round_row in rounds:
            games = session.exec(select(Game).where(Game.round_id == round_row.id)).all()
            if not games:
                round_row.status = "pending"
                round_row.completed_at = None
            elif any(game.status not in FINAL_GAME_STATUSES for game in games):
                round_row.status = "active"
                round_row.completed_at = None
                active_round_found = True
            else:
                round_row.status = "completed"
                round_row.completed_at = round_row.completed_at or utc_now()
            session.add(round_row)

        tournament = session.get(Tournament, tournament_id)
        if tournament is None:
            return
        if rounds and all(round_row.status == "completed" for round_row in rounds):
            tournament.status = "completed"
            tournament.completed_at = tournament.completed_at or utc_now()
        elif active_round_found or tournament.started_at is not None:
            tournament.status = "active"
            tournament.completed_at = None
        session.add(tournament)
