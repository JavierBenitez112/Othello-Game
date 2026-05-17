from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from server.db import init_db


def test_sqlite_startup_migration_adds_new_tournament_columns(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE player (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    client_token VARCHAR NOT NULL,
                    connected BOOLEAN NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE tournament (
                    id INTEGER PRIMARY KEY,
                    status VARCHAR NOT NULL,
                    total_rounds INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    started_at TIMESTAMP
                )
                """
            )
        )

    init_db(engine)

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("tournament")}

    assert "name" in columns
    assert "registration_status" in columns
    assert "completed_at" in columns

    player_columns = {column["name"] for column in inspector.get_columns("player")}
    assert "tournament_id" in player_columns
