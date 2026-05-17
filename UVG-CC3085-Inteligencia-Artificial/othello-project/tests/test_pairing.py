from server.pairing import SwissPlayer, swiss_pair


def test_swiss_pairing_avoids_repeat_when_possible() -> None:
    players = [
        SwissPlayer(player_id=1, points=3.0),
        SwissPlayer(player_id=2, points=2.0),
        SwissPlayer(player_id=3, points=2.0),
        SwissPlayer(player_id=4, points=1.0),
    ]
    previous_opponents = {
        1: {2},
        2: {1},
        3: set(),
        4: set(),
    }

    result = swiss_pair(players, previous_opponents)

    assert (1, 3) in result.pairs
    assert (2, 4) in result.pairs
    assert result.bye_player_id is None
