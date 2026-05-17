# Tournaments Pages

This route group handles tournament creation and overview pages.

## Purpose

- list tournaments
- create tournaments
- start or close registration
- start tournament execution

## Data sources

- `GET /admin/tournaments`
- `POST /admin/tournaments`
- `POST /admin/tournaments/{id}/start-registration`
- `POST /admin/tournaments/{id}/close-registration`
- `POST /admin/tournaments/{id}/start`

## Related routes

- `[id]/` contains the detail page for a single tournament
