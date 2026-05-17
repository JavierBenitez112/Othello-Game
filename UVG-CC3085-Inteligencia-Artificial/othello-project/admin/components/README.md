# Components

This directory contains reusable React components for the admin interface.

## What is here

- board renderers such as `OthelloBoard.tsx` and `MiniOthelloBoard.tsx`
- dashboard and table components such as `PlayersTable.tsx`, `StandingsTable.tsx`, and `LiveGamesTable.tsx`
- live monitoring widgets such as `ConnectionStatus.tsx`, `LiveGameCard.tsx`, and `GameViewer.tsx`
- layout components such as `AdminShell.tsx`
- the smaller UI primitives live in `ui/`

## Dependencies

- React
- TypeScript
- Tailwind CSS
- local helpers from `../lib`
- some icons from `lucide-react`

## How these components are used

Pages in `../app` import these components and supply data fetched from the backend.

Examples:

- `AdminShell` wraps authenticated pages
- `ConnectionStatus` shows WebSocket health
- `GameReplay` and `GameViewer` render game history and board state

## Extending this directory

Add a new component here when:

- the same UI block is used by more than one page
- a page is becoming too large
- a new board/game visualization needs to be isolated and tested separately
