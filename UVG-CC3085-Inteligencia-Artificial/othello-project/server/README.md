# Server

This directory contains the backend that runs the tournament.

## What is here

- `main.py`: creates the FastAPI app and defines HTTP/WebSocket routes
- `tournament.py`: tournament orchestration, live game runtime state, admin events, and move handling
- `game_rules.py`: Othello board representation, legal move generation, move application, scoring, and winner detection
- `pairing.py`: Swiss-style round pairing logic
- `models.py`: SQLModel database tables
- `schemas.py`: request/response validation models
- `db.py`: database engine creation and initialization
- `admin_auth.py`: simple admin authentication and token validation

## Dependencies

- Python 3.11+
- `fastapi`
- `sqlmodel`
- `uvicorn`
- `websockets`

## How to run

From the project root:

```bash
cd othello-project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export MOVE_TIMEOUT_SECONDS=3
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123
uvicorn server.main:app --reload
```

## Important environment variables

- `DATABASE_URL`: overrides the default SQLite database path
- `MOVE_TIMEOUT_SECONDS`: per-turn timeout
- `ADMIN_USERNAME`: admin login name
- `ADMIN_PASSWORD`: admin login password
- `CORS_ALLOW_ORIGINS`: comma-separated frontend origins allowed to call the API

## How to use it

1. Start the server.
2. Login through `POST /admin/login`.
3. Create a tournament.
4. Open registration.
5. Start bots so they enroll through `POST /players` using the tournament name.
6. Close registration.
7. Start the tournament and rounds through the admin endpoints.

## Architecture notes

- The server is authoritative: clients never decide legality.
- Bot gameplay happens through WebSockets.
- Admin live updates also happen through a WebSocket channel.
- Game state is persisted so standings and replays can be queried over HTTP.
