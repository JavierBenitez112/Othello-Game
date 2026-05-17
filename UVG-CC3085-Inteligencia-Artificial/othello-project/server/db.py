from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine


DEFAULT_DATABASE_URL = "sqlite:///./othello.db"


def build_engine(database_url: str | None = None):
    url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )


engine = build_engine()


def init_db(db_engine=None) -> None:
    active_engine = db_engine or engine
    SQLModel.metadata.create_all(active_engine)
    _run_startup_migrations(active_engine)


def _run_startup_migrations(db_engine) -> None:
    if not str(db_engine.url).startswith("sqlite"):
        return

    inspector = inspect(db_engine)
    if "tournament" not in inspector.get_table_names():
        return

    tournament_columns = {column["name"] for column in inspector.get_columns("tournament")}
    statements: list[str] = []

    if "name" not in tournament_columns:
        statements.append("ALTER TABLE tournament ADD COLUMN name VARCHAR NOT NULL DEFAULT 'Tournament'")
    if "registration_status" not in tournament_columns:
        statements.append("ALTER TABLE tournament ADD COLUMN registration_status VARCHAR NOT NULL DEFAULT 'closed'")
    if "completed_at" not in tournament_columns:
        statements.append("ALTER TABLE tournament ADD COLUMN completed_at TIMESTAMP")

    player_columns = set()
    if "player" in inspector.get_table_names():
        player_columns = {column["name"] for column in inspector.get_columns("player")}
    if player_columns and "tournament_id" not in player_columns:
        statements.append("ALTER TABLE player ADD COLUMN tournament_id INTEGER")

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
