# App

This directory contains the Next.js App Router pages for the admin portal.

## What is here

- `layout.tsx`: root shell and page chrome
- `globals.css`: global styles
- `page.tsx`: dashboard landing page
- `login/`: login screen
- `tournaments/`: tournament list and tournament detail pages
- `players/`: player management page
- `standings/`: standings page
- `live-games/`: live games view
- `games/[gameId]/`: single game detail/replay page
- `rounds/[roundId]/`: single round detail page
- `providers.tsx`: shared React providers such as React Query

## Dependencies

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- TanStack Query

## How to run

From `othello-project/admin`:

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

## How it is used

Each route in this directory renders a page that calls helpers from `../lib` and components from `../components`.

Typical flow:

1. Login at `/login`
2. View dashboard at `/`
3. Create or manage tournaments
4. Start rounds
5. Monitor live games and standings

## Notes

- Most pages are client components because they depend on browser auth state and live updates.
- The API base URL and WebSocket base URL are read from `.env.local`.
