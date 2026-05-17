# Tests

This directory contains pytest coverage for the backend and tournament behavior.

## What is tested

- `test_game_rules.py`: board setup, legal moves, move application, and scoring
- `test_game_flow.py`: end-to-end gameplay behavior such as turns, illegal moves, and outcomes
- `test_pairing.py`: Swiss pairing logic
- `test_admin_api.py`: admin endpoints and common admin flows
- `test_db_migrations.py`: database initialization and persistence-related checks

## Dependencies

- Python 3.11+
- `pytest`
- `httpx`

Install from the project root:

```bash
cd othello-project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## How to run

Run all tests:

```bash
cd othello-project
pytest
```

Run one test file:

```bash
pytest tests/test_game_rules.py
```

## When to add tests

Add or update tests whenever you change:

- Othello rules
- pairing behavior
- API response shapes
- admin actions
- timeout, forfeit, or reconnect logic
