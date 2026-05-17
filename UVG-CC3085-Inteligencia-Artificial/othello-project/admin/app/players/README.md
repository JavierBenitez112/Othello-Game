# Players Page

This route is used to inspect and manage tournament players.

## Purpose

- list registered players
- show connection status
- support admin actions such as forfeit or deletion through the backend API

## Data sources

- `GET /admin/players`
- `POST /admin/players/{playerId}/forfeit`

## Running

Run the backend and the admin app locally, then open `/players`.
