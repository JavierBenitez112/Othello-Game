from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PlayerCreate(BaseModel):
    tournament_name: str
    name: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    username: str


class PlayerRead(BaseModel):
    player_id: int
    name: str


class PlayerEnrollmentResponse(BaseModel):
    tournament_id: int
    tournament_name: str
    player_id: int
    name: str
    client_token: str


class AdminTournamentCreate(BaseModel):
    name: str
    total_rounds: int = 10


class AdminTournamentUpdate(BaseModel):
    name: str | None = None
    total_rounds: int | None = None


class TournamentCreateResponse(BaseModel):
    tournament_id: int
    total_rounds: int
    players_registered: int


class RoundStartResponse(BaseModel):
    tournament_id: int
    round_number: int
    game_ids: list[str]
    bye_player_id: int | None


class StandingRow(BaseModel):
    player_id: int
    player_name: str
    points: float
    wins: int
    losses: int
    draws: int
    byes: int


class StandingsResponse(BaseModel):
    tournament_id: int
    standings: list[StandingRow]


class MoveLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    turn_number: int
    move: str
    board_after: list[list[str]]
    created_at: datetime


class GameRead(BaseModel):
    game_id: str
    round_number: int
    status: str
    black_player_id: int
    white_player_id: int
    board: list[list[str]]
    next_turn: str | None
    last_move: str | None
    result: str | None
    forfeit_reason: str | None
    black_score: int
    white_score: int
    moves: list[MoveLogRead]


class IncomingMove(BaseModel):
    type: Literal["move"]
    game_id: str
    move: str


class AdminPlayerCreate(BaseModel):
    tournament_id: int
    name: str


class AdminPlayerUpdate(BaseModel):
    name: str | None = None


class AdminGameCreate(BaseModel):
    round_id: int
    black_player_id: int
    white_player_id: int


class AdminGameUpdate(BaseModel):
    round_id: int | None = None
    black_player_id: int | None = None
    white_player_id: int | None = None
    status: Literal["pending", "active"] | None = None
