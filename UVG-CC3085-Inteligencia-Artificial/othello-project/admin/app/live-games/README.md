# Live Games Page

This route shows currently active games in the tournament.

## Purpose

- fetch live game summaries from the backend
- show current board state and status
- help admins monitor active matches in real time

## Data sources

- `GET /admin/live-games`
- admin WebSocket events from `../../lib/ws.ts`

## Running

Start the backend, then run the admin app with `npm run dev` in `othello-project/admin`.
