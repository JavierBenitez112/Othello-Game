# Lib

This directory contains the frontend support code used by the admin pages.

## What is here

- `api.ts`: typed HTTP client for backend admin endpoints
- `ws.ts`: admin WebSocket client with reconnect behavior
- `auth.ts`: token storage helpers
- `types.ts`: shared frontend types
- `utils.ts`: small utility helpers

## Dependencies

- browser `fetch`
- browser `WebSocket`
- Next.js environment variables
- React app code that consumes these helpers

## How it is used

- pages call functions from `api.ts`
- the shell and live widgets subscribe through `ws.ts`
- auth state is stored and read through `auth.ts`

## Important environment variables

Set in `admin/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

## If the backend changes

The first places to update are usually:

- `types.ts` if payload shapes changed
- `api.ts` if endpoint URLs or fields changed
- `ws.ts` if live event formats changed
