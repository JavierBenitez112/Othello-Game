from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, select
from starlette import status

from server.admin_auth import AdminAuthManager
from server.db import build_engine, init_db
from server.models import Player
from server.schemas import (
    AdminGameCreate,
    AdminGameUpdate,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminPlayerCreate,
    AdminPlayerUpdate,
    AdminTournamentCreate,
    AdminTournamentUpdate,
    GameRead,
    PlayerCreate,
    PlayerEnrollmentResponse,
    PlayerRead,
    RoundStartResponse,
    StandingsResponse,
    TournamentCreateResponse,
)
from server.tournament import TournamentManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(database_url: str | None = None, move_timeout_seconds: float | None = None) -> FastAPI:
    engine = build_engine(database_url)
    session_factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
    manager = TournamentManager(session_factory=session_factory, move_timeout_seconds=move_timeout_seconds)
    admin_auth = AdminAuthManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        app.state.engine = engine
        app.state.manager = manager
        app.state.admin_auth = admin_auth
        yield

    app = FastAPI(title="Othello Tournament MVP", lifespan=lifespan)

    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOW_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db_session():
        with Session(engine) as session:
            yield session

    def require_admin(authorization: Annotated[str | None, Header()] = None) -> str:
        return admin_auth.validate_http_token(authorization)

    @app.post("/admin/login", response_model=AdminLoginResponse)
    async def admin_login(payload: AdminLoginRequest):
        token = admin_auth.login(payload.username, payload.password)
        return AdminLoginResponse(token=token, username=payload.username)

    @app.post("/players", response_model=PlayerEnrollmentResponse)
    async def create_player(payload: PlayerCreate):
        enrollment = manager.enroll_player(payload.tournament_name, payload.name)
        return PlayerEnrollmentResponse(**enrollment)

    @app.post("/tournament/start", response_model=TournamentCreateResponse)
    async def start_tournament():
        tournament = manager.start_tournament()
        with Session(engine) as session:
            player_count = len(session.exec(select(Player.id)).all())
        return TournamentCreateResponse(
            tournament_id=tournament.id,
            total_rounds=tournament.total_rounds,
            players_registered=player_count,
        )

    @app.post("/tournament/rounds/{round_number}/start", response_model=RoundStartResponse)
    async def start_round(round_number: int):
        tournament, _, games, bye_player_id = await manager.start_round(round_number)
        return RoundStartResponse(
            tournament_id=tournament.id,
            round_number=round_number,
            game_ids=[game.id for game in games],
            bye_player_id=bye_player_id,
        )

    @app.get("/standings", response_model=StandingsResponse)
    async def standings(tournament_id: int | None = None):
        tournament_id, rows = manager.get_standings(tournament_id)
        return StandingsResponse(tournament_id=tournament_id, standings=rows)

    @app.get("/games/{game_id}", response_model=GameRead)
    async def get_game(game_id: str):
        return GameRead.model_validate(manager.get_game(game_id))

    @app.post("/admin/tournaments")
    async def create_admin_tournament(payload: AdminTournamentCreate, _: str = Depends(require_admin)):
        return manager.create_tournament(payload.name, payload.total_rounds)

    @app.patch("/admin/tournaments/{tournament_id}")
    async def update_admin_tournament(
        tournament_id: int,
        payload: AdminTournamentUpdate,
        _: str = Depends(require_admin),
    ):
        return manager.update_tournament(tournament_id, name=payload.name, total_rounds=payload.total_rounds)

    @app.delete("/admin/tournaments/{tournament_id}", status_code=204)
    async def delete_admin_tournament(tournament_id: int, _: str = Depends(require_admin)):
        manager.delete_tournament(tournament_id)

    @app.get("/admin/tournaments")
    async def list_admin_tournaments(_: str = Depends(require_admin)):
        return manager.list_tournaments()

    @app.get("/admin/tournaments/{tournament_id}")
    async def get_admin_tournament(tournament_id: int, _: str = Depends(require_admin)):
        return manager.get_tournament_detail(tournament_id)

    @app.post("/admin/tournaments/{tournament_id}/start-registration")
    async def start_admin_registration(tournament_id: int, _: str = Depends(require_admin)):
        return manager.start_registration(tournament_id)

    @app.post("/admin/tournaments/{tournament_id}/close-registration")
    async def close_admin_registration(tournament_id: int, _: str = Depends(require_admin)):
        return manager.close_registration(tournament_id)

    @app.post("/admin/tournaments/{tournament_id}/start")
    async def start_admin_tournament(tournament_id: int, _: str = Depends(require_admin)):
        payload = manager.start_tournament_by_id(tournament_id)
        payload.pop("__model__", None)
        return payload

    @app.post("/admin/rounds/{round_id}/start")
    async def start_admin_round(round_id: int, _: str = Depends(require_admin)):
        _, round_row, games, bye_player_id = await manager.start_round_by_id(round_id)
        return {
            "id": round_row.id,
            "tournamentId": round_row.tournament_id,
            "number": round_row.number,
            "status": round_row.status,
            "gameIds": [game.id for game in games],
            "byePlayerId": bye_player_id,
        }

    @app.get("/admin/rounds/{round_id}")
    async def get_admin_round(round_id: int, _: str = Depends(require_admin)):
        return manager.get_round_detail(round_id)

    @app.get("/admin/games/{game_id}")
    async def get_admin_game(game_id: str, _: str = Depends(require_admin)):
        return manager.get_admin_game(game_id)

    @app.post("/admin/games")
    async def create_admin_game(payload: AdminGameCreate, _: str = Depends(require_admin)):
        return await manager.create_game(payload.round_id, payload.black_player_id, payload.white_player_id)

    @app.patch("/admin/games/{game_id}")
    async def update_admin_game(game_id: str, payload: AdminGameUpdate, _: str = Depends(require_admin)):
        return await manager.update_game(
            game_id,
            round_id=payload.round_id,
            black_player_id=payload.black_player_id,
            white_player_id=payload.white_player_id,
            status=payload.status,
        )

    @app.delete("/admin/games/{game_id}", status_code=204)
    async def delete_admin_game(game_id: str, _: str = Depends(require_admin)):
        manager.delete_game(game_id)

    @app.post("/admin/games/{game_id}/force-end")
    async def force_end_admin_game(game_id: str, _: str = Depends(require_admin)):
        return await manager.force_end_game(game_id)

    @app.post("/admin/players/{player_id}/forfeit")
    async def forfeit_admin_player(player_id: int, _: str = Depends(require_admin)):
        return await manager.forfeit_player(player_id)

    @app.post("/admin/players")
    async def create_admin_player(payload: AdminPlayerCreate, _: str = Depends(require_admin)):
        return manager.create_admin_player(payload.tournament_id, payload.name)

    @app.patch("/admin/players/{player_id}")
    async def update_admin_player(player_id: int, payload: AdminPlayerUpdate, _: str = Depends(require_admin)):
        return manager.update_player(player_id, name=payload.name)

    @app.delete("/admin/players/{player_id}", status_code=204)
    async def delete_admin_player(player_id: int, _: str = Depends(require_admin)):
        manager.delete_player(player_id)

    @app.get("/admin/players")
    async def get_admin_players(_: str = Depends(require_admin)):
        return manager.list_players()

    @app.get("/admin/standings")
    async def get_admin_standings(_: str = Depends(require_admin)):
        return manager.list_admin_standings()

    @app.get("/admin/live-games")
    async def get_admin_live_games(_: str = Depends(require_admin)):
        return {"games": manager.list_live_games()}

    @app.websocket("/admin/ws")
    async def admin_websocket_endpoint(websocket: WebSocket):
        token = websocket.query_params.get("token")
        if not admin_auth.validate_ws_token(token):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await manager.register_admin_connection(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.unregister_admin_connection(websocket)
        except Exception:
            manager.unregister_admin_connection(websocket)
            raise

    @app.websocket("/ws/{player_id}")
    async def websocket_endpoint(websocket: WebSocket, player_id: int):
        token = websocket.query_params.get("token", "")
        await manager.register_connection(player_id, token, websocket)
        try:
            while True:
                payload = await websocket.receive_json()
                await manager.handle_client_message(player_id, payload)
        except WebSocketDisconnect:
            manager.unregister_connection(player_id)
        except Exception:
            manager.unregister_connection(player_id)
            raise

    return app


app = create_app()
