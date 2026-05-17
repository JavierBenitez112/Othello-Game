# Othello Admin Portal

Next.js admin dashboard for an existing Othello/Reversi tournament backend. It provides tournament controls, player monitoring, standings, live game supervision, and per-game replay tools.

## Stack

- Next.js App Router
- React + TypeScript
- Tailwind CSS
- shadcn-style UI primitives
- TanStack Query
- Native browser WebSocket client

## Local setup

1. Install Node.js 22 or newer.
2. Copy the example environment file:

```bash
cp .env.local.example .env.local
```

3. Install dependencies and start the app:

```bash
npm install
npm run dev
```

The app runs on `http://localhost:3000`.

To run it successfully, the backend from `../server` must already be running on `http://localhost:8000` unless you change the environment variables below.

## Environment variables

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

`NEXT_PUBLIC_API_BASE_URL` is used by `lib/api.ts`.

`NEXT_PUBLIC_WS_BASE_URL` is used by `lib/ws.ts`.

## Authentication flow

- `POST /admin/login` with `{ username, password }`
- Store returned `token` in `localStorage`
- Send `Authorization: Bearer <token>` on HTTP requests
- Send `token` query param when opening `WS /admin/ws`
- Unauthenticated users are redirected to `/login`

Default backend credentials unless overridden by environment variables:

```text
username: admin
password: admin123
```

Tournament enrollment is username-based per tournament. Registration must be opened first, and each bot should connect using:

```bash
python -m client.sample_bot --server-url http://localhost:8000 --tournament-name "Spring Open" --username bot-a
```

## Expected backend API shapes

The UI assumes these endpoints exist:

### HTTP

- `POST /admin/login`
- `GET /admin/tournaments`
- `POST /admin/tournaments`
- `GET /admin/tournaments/{id}`
- `POST /admin/tournaments/{id}/start-registration`
- `POST /admin/tournaments/{id}/close-registration`
- `POST /admin/tournaments/{id}/start`
- `POST /admin/rounds/{roundId}/start`
- `GET /admin/rounds/{roundId}`
- `GET /admin/games/{gameId}`
- `POST /admin/games/{gameId}/force-end`
- `POST /admin/players/{playerId}/forfeit`
- `GET /admin/players`
- `GET /admin/standings`
- `GET /admin/live-games`

### WebSocket

- `WS /admin/ws?token=<token>`

Supported live event types:

- `tournament_update`
- `player_connected`
- `player_disconnected`
- `round_started`
- `game_started`
- `game_update`
- `game_over`
- `move_recorded`
- `illegal_move`
- `timeout`
- `forfeit`

## Notes on response shapes

The frontend keeps the API layer typed but intentionally tolerant:

- `GET /admin/live-games` can return either `{ games: [...] }` or a bare array.
- Tournament details can include embedded `standings`, `rounds`, and `activeGames`.
- Game details should include `board`, `moveHistory`, player names, status, and score fields.
- Round details should include `pairings` and any result metadata.

If your backend uses slightly different field names, update `admin/lib/types.ts` and the mapping logic in `admin/lib/api.ts`.

## Folder guide

- `app/`: App Router pages and layouts
- `components/`: visual building blocks for boards, tables, and page shells
- `components/ui/`: reusable UI primitives such as buttons, cards, inputs, and tables
- `lib/`: auth helpers, typed API calls, WebSocket client logic, and shared types

Each of those directories also has its own `README.md`.

## Docker

Build and run:

```bash
docker build -t othello-admin .
docker run --rm -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  -e NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000 \
  othello-admin
```

## Limitations

- This app assumes the backend already enforces tournament rules and permissions.
- No server-side rendering auth guard is included; auth redirect is client-side.
- The UI is tolerant of missing fields, but richer backend payloads will produce a better experience.
