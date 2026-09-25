"""
"Play again" — starting a fresh round for the same group of players
once one round finishes, without having to leave the room and
re-create it.

No persistent host/owner concept, but restart authority isn't open to
literally anyone either: any player who was ever seated in this room
may trigger it (see GameRoom.restart's docstring) — not just whoever
won the round that just ended. A round commonly ends because someone
forfeited rather than because anyone actually chose to stop playing,
so restricting this to "only the winner clicks a button" would leave
everyone else stuck waiting on a player who may not even still be
watching.
"""

import pytest
from fastapi.testclient import TestClient

from app.game.dependencies import connection_manager, room_manager
from app.game.room import create_room
from app.main import app
from app.rules.state import Phase, Player


@pytest.fixture(autouse=True)
def _reset_shared_state():
    room_manager.clear()
    connection_manager.active_connections.clear()
    yield
    room_manager.clear()
    connection_manager.active_connections.clear()


def _two_player_room():
    room = create_room()
    room.add_player(Player(id="a", name="Amina"))
    room.add_player(Player(id="b", name="Brian"))
    return room


def test_restart_before_first_start_raises():
    room = _two_player_room()

    with pytest.raises(ValueError):
        room.restart("a")


def test_restart_while_round_in_progress_raises():
    room = _two_player_room()
    room.start_game()

    assert room.state.phase != Phase.FINISHED

    with pytest.raises(ValueError):
        room.restart("a")


def test_restart_after_finish_deals_a_fresh_round():
    room = _two_player_room()
    room.start_game()

    # Force the round to a finished state directly rather than
    # playing it out card by card — restart() only cares that
    # phase == FINISHED, not how it got there.
    room.state = room.state.replace(
        phase=Phase.FINISHED,
        winner_id="a",
        eliminated_player_ids=frozenset({"b"}),
    )

    events = room.restart("a")

    assert room.state.phase != Phase.FINISHED
    assert room.state.winner_id is None
    assert room.state.eliminated_player_ids == frozenset()
    # Same two players carry over into the new round.
    assert {p.id for p in room.state.players} == {"a", "b"}
    assert any(event.type.value == "game_started" for event in events)


def test_restart_keeps_same_room_and_players_list():
    room = _two_player_room()
    room.start_game()
    room.state = room.state.replace(phase=Phase.FINISHED, winner_id="a")

    room.restart("a")

    assert len(room.players) == 2
    assert {p.id for p in room.players} == {"a", "b"}


def test_restart_by_the_loser_is_allowed():
    """
    A round often ends because someone forfeited, not because either
    player actually chose to stop — so the player who DIDN'T win a
    given round must still be able to deal a fresh one.
    """

    room = _two_player_room()
    room.start_game()
    room.state = room.state.replace(phase=Phase.FINISHED, winner_id="a")

    events = room.restart("b")

    assert room.state.phase != Phase.FINISHED
    assert room.state.winner_id is None
    assert any(event.type.value == "game_started" for event in events)


def test_restart_by_an_eliminated_or_departed_player_is_allowed():
    """
    A player who was forfeited out (punishment forfeit) or who quit
    mid-round is still someone who was seated in this room, and may
    still want to start a fresh one once it's over.
    """

    room = _two_player_room()
    room.start_game()
    room.state = room.state.replace(
        phase=Phase.FINISHED,
        winner_id="a",
        eliminated_player_ids=frozenset({"b"}),
    )

    events = room.restart("b")

    assert room.state.phase != Phase.FINISHED
    assert room.state.eliminated_player_ids == frozenset()
    assert any(event.type.value == "game_started" for event in events)


def test_restart_by_someone_never_seated_in_the_room_raises():
    room = _two_player_room()
    room.start_game()
    room.state = room.state.replace(phase=Phase.FINISHED, winner_id="a")

    with pytest.raises(ValueError):
        room.restart("stranger")

    # Nothing changed — the illegitimate restart attempt had no effect.
    assert room.state.phase == Phase.FINISHED
    assert room.state.winner_id == "a"


def test_restart_by_a_different_winner_each_round_is_allowed():
    """
    Whoever happens to win can also restart — this isn't exclusive,
    it's just one more seated player among the others.
    """

    room = _two_player_room()
    room.start_game()
    room.state = room.state.replace(phase=Phase.FINISHED, winner_id="a")
    room.restart("a")

    room.state = room.state.replace(phase=Phase.FINISHED, winner_id="b")
    events = room.restart("b")

    assert room.state.phase != Phase.FINISHED
    assert any(event.type.value == "game_started" for event in events)


def test_websocket_restart_message_broadcasts_fresh_state():
    client = TestClient(app)

    room_id = client.post("/api/rooms").json()["room_id"]
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "a", "player_name": "Amina"},
    )
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "b", "player_name": "Brian"},
    )
    client.post(f"/api/rooms/{room_id}/start")

    room = room_manager.get_room(room_id)
    room.state = room.state.replace(phase=Phase.FINISHED, winner_id="a")

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id=a"
    ) as ws:
        ws.receive_json()  # initial state on connect

        ws.send_json({"type": "restart"})

        message = ws.receive_json()

        assert message["type"] == "state"
        assert message["room"]["state"]["phase"] != "finished"
        assert message["room"]["state"]["winner_id"] is None


def test_websocket_restart_before_finish_sends_error():
    client = TestClient(app)

    room_id = client.post("/api/rooms").json()["room_id"]
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "a", "player_name": "Amina"},
    )
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "b", "player_name": "Brian"},
    )
    client.post(f"/api/rooms/{room_id}/start")

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id=a"
    ) as ws:
        ws.receive_json()  # initial state on connect

        ws.send_json({"type": "restart"})

        message = ws.receive_json()

        assert message["type"] == "error"


def test_websocket_restart_by_non_winner_broadcasts_fresh_state():
    client = TestClient(app)

    room_id = client.post("/api/rooms").json()["room_id"]
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "a", "player_name": "Amina"},
    )
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "b", "player_name": "Brian"},
    )
    client.post(f"/api/rooms/{room_id}/start")

    room = room_manager.get_room(room_id)
    room.state = room.state.replace(phase=Phase.FINISHED, winner_id="a")

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id=b"
    ) as ws:
        ws.receive_json()  # initial state on connect

        ws.send_json({"type": "restart"})

        message = ws.receive_json()

        assert message["type"] == "state"
        assert message["room"]["state"]["phase"] != "finished"


    # No websocket-level "restart by a stranger" test here: the socket
    # layer itself already refuses to connect anyone who isn't seated
    # in the room (see room_websocket's join check above the message
    # loop), so a stranger can never even reach the restart handler
    # that way. test_restart_by_someone_never_seated_in_the_room_raises
    # covers the ValueError path directly against GameRoom.restart.
