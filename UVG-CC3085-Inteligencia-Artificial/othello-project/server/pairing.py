from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SwissPlayer:
    player_id: int
    points: float
    had_bye: bool = False


@dataclass(slots=True)
class PairingResult:
    pairs: list[tuple[int, int]]
    bye_player_id: int | None


def swiss_pair(players: list[SwissPlayer], previous_opponents: dict[int, set[int]]) -> PairingResult:
    ranked = sorted(players, key=lambda player: (-player.points, player.player_id))
    bye_player_id: int | None = None

    if len(ranked) % 2 == 1:
        for candidate in reversed(ranked):
            if not candidate.had_bye:
                bye_player_id = candidate.player_id
                ranked = [player for player in ranked if player.player_id != candidate.player_id]
                break
        if bye_player_id is None:
            bye_player_id = ranked[-1].player_id
            ranked = ranked[:-1]

    pairs: list[tuple[int, int]] = []
    unpaired = ranked[:]

    while unpaired:
        first = unpaired.pop(0)
        opponent_index = _choose_opponent_index(first, unpaired, previous_opponents)
        second = unpaired.pop(opponent_index)
        pairs.append((first.player_id, second.player_id))

    return PairingResult(pairs=pairs, bye_player_id=bye_player_id)


def _choose_opponent_index(
    first: SwissPlayer,
    candidates: list[SwissPlayer],
    previous_opponents: dict[int, set[int]],
) -> int:
    prior = previous_opponents.get(first.player_id, set())
    for index, candidate in enumerate(candidates):
        if candidate.player_id not in prior:
            return index
    return 0
