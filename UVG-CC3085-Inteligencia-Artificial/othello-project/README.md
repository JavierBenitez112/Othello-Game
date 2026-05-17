# Othello Tournament MVP

FastAPI + SQLite + WebSockets Othello/Reversi tournament system with:

- a Python backend that runs tournaments and games
- a reusable Python bot client
- a Next.js admin dashboard
- Docker support for local or server deployment

## Project guide

- `server/`: FastAPI API, WebSocket endpoints, rules engine, pairing logic, persistence, and tournament orchestration
- `client/`: reusable bot transport plus a simple sample bot
- `admin/`: browser-based admin dashboard for login, tournament control, standings, and live games
- `tests/`: pytest coverage for rules, pairings, API, and game flow

Each source directory has its own `README.md` with local details.

## Dependencies

### Backend

- Python `3.11+`
- FastAPI
- SQLModel / SQLAlchemy
- Uvicorn
- websockets
- pytest and httpx for development/testing

Install from `pyproject.toml`.

### Admin frontend

- Node.js `22+`
- Next.js `15`
- React `19`
- Tailwind CSS
- TanStack Query

Install from `admin/package.json`.

## Local setup

### 1. Backend

```bash
cd othello-project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Admin frontend

```bash
cd othello-project/admin
cp .env.local.example .env.local
npm install
```

## Run locally

### Start the backend

```bash
cd othello-project
export MOVE_TIMEOUT_SECONDS=3
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123
uvicorn server.main:app --reload
```

The backend listens on `http://localhost:8000`.

By default it writes SQLite data to `./othello.db`. You can override that with `DATABASE_URL`.

### Start the admin dashboard

```bash
cd othello-project/admin
npm run dev
```

The dashboard runs on `http://localhost:3000`.

## Docker

Run the backend container defined in `docker-compose.yml`:

```bash
cd othello-project
docker compose up --build
```

## How to use the project

### 1. Login as admin

Default credentials:

```text
username: admin
password: admin123
```

You can override them with `ADMIN_USERNAME` and `ADMIN_PASSWORD`.

### 2. Create a tournament

Use the admin UI or call:

```bash
curl -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Then create and open registration:

```bash
curl -X POST http://localhost:8000/admin/tournaments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name":"Campus Cup","total_rounds":3}'

curl -X POST http://localhost:8000/admin/tournaments/1/start-registration \
  -H "Authorization: Bearer <token>"
```

### 3. Start bots

```bash
cd othello-project
python -m client.sample_bot --server-url http://localhost:8000 --tournament-id 1 --username bot-a
python -m client.sample_bot --server-url http://localhost:8000 --tournament-id 1 --username bot-b
```

Each bot enrolls itself, receives a `player_id` and token, then opens a WebSocket connection automatically.

### 4. Close registration and start play

From the admin UI or API:

1. Close registration
2. Start the tournament
3. Start a round
4. Watch standings and live games update in the admin dashboard

## Important endpoints

- `POST /admin/login`
- `POST /admin/tournaments`
- `POST /admin/tournaments/{id}/start-registration`
- `POST /admin/tournaments/{id}/close-registration`
- `POST /admin/tournaments/{id}/start`
- `POST /admin/rounds/{roundId}/start`
- `GET /admin/live-games`
- `GET /admin/standings`
- `POST /players`
- `GET /games/{game_id}`
- `WS /ws/{player_id}?token=...`
- `WS /admin/ws?token=...`

## Tests

```bash
cd othello-project
pytest
```

## Notes

- The server is authoritative for board state and legality.
- Illegal moves and missed deadlines immediately lose the game.
- Pairing is greedy Swiss, not a full tournament solver.
- The sample bot is intentionally simple and is meant to be replaced or upgraded.
