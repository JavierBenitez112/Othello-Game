from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Player(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tournament_id: Optional[int] = Field(default=None, index=True, foreign_key="tournament.id")
    name: str = Field(index=True)
    client_token: str = Field(index=True, unique=True)
    connected: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class Tournament(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="Tournament", index=True)
    status: str = Field(default="pending", index=True)
    registration_status: str = Field(default="closed", index=True)
    total_rounds: int = Field(default=10)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)


class Round(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tournament_id: int = Field(index=True, foreign_key="tournament.id")
    number: int = Field(index=True)
    status: str = Field(default="pending", index=True)
    started_at: datetime = Field(default_factory=utc_now, nullable=False)
    completed_at: Optional[datetime] = Field(default=None)


class Standing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tournament_id: int = Field(index=True, foreign_key="tournament.id")
    player_id: int = Field(index=True, foreign_key="player.id")
    points: float = Field(default=0.0)
    wins: int = Field(default=0)
    losses: int = Field(default=0)
    draws: int = Field(default=0)
    byes: int = Field(default=0)


class Game(SQLModel, table=True):
    id: str = Field(primary_key=True)
    tournament_id: int = Field(index=True, foreign_key="tournament.id")
    round_id: int = Field(index=True, foreign_key="round.id")
    round_number: int = Field(index=True)
    black_player_id: int = Field(index=True, foreign_key="player.id")
    white_player_id: int = Field(index=True, foreign_key="player.id")
    status: str = Field(default="pending", index=True)
    current_board: str = Field(nullable=False)
    next_turn: Optional[str] = Field(default="black")
    last_move: Optional[str] = Field(default=None)
    winner_player_id: Optional[int] = Field(default=None, foreign_key="player.id")
    loser_player_id: Optional[int] = Field(default=None, foreign_key="player.id")
    result: Optional[str] = Field(default=None)
    forfeit_reason: Optional[str] = Field(default=None)
    black_score: int = Field(default=2)
    white_score: int = Field(default=2)
    started_at: Optional[datetime] = Field(default=None)
    finished_at: Optional[datetime] = Field(default=None)


class MoveLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(index=True, foreign_key="game.id")
    player_id: int = Field(index=True, foreign_key="player.id")
    turn_number: int = Field(index=True)
    move: str = Field(nullable=False)
    board_after: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class RoundResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tournament_id: int = Field(index=True, foreign_key="tournament.id")
    round_number: int = Field(index=True)
    player_id: int = Field(index=True, foreign_key="player.id")
    opponent_player_id: Optional[int] = Field(default=None, foreign_key="player.id")
    game_id: Optional[str] = Field(default=None, foreign_key="game.id")
    points_awarded: float = Field(default=0.0)
    outcome: str = Field(nullable=False)
