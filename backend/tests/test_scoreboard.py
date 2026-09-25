"""
End-to-end verification of the persistence layer: a real GAME_FINISHED
produced by ``room.apply()`` (not a directly-mutated state, which would
bypass ``_broadcast_state``/the REST handlers entirely and never reach
``app.game.game_results.maybe_record_game_result``) must result in a
``game_results`` row, and that row must be visible back to clients as
the room's ``scoreboard``.

Covers both paths that call ``maybe_record_game_result``:
- The WebSocket path (app.api.websocket._broadcast_state), which is
  what the real frontend plays through.
- The REST debug endpoints (app.api.routes), kept around for direct
  testing.

Also covers the specific thing the user asked for: a *running* tally
per room that survives a restart/replay within the same room, not just
a single win being recorded.
"""

import pytest
from fastapi.testclient import TestClient

from app import db
from app.game.dependencies import connection_manager, room_manager
from app.game.room import create_room
from app.main import app
from app.rules.cards import Card, Rank, Suit
from app.rules.state import Phase, Player


@pytest.fixture(autouse=True)
def _reset_shared_state(tmp_path, monkeypatch):
    # Isolate every test in this file from both the shared in-memory
    # room registry AND the real on-disk kadi.db — without this, tests
    # here would read/write the same database file the dev server (or
    # other test files, however unlikely given room-code randomness)
    # uses, and would accumulate rows across runs.
    monkeypatch.setenv("KADI_DB_PATH", str(tmp_path / "test_kadi.db"))

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


def _rig_state_so_a_wins_by_playing_a_four(room):
    """
    Overwrites the just-started round's state with a hand-crafted one
    where it's player a's turn, a holds exactly one card (a plain,
    finishable Four of Hearts), and the top of the discard pile is a
    Four of Hearts too — so playing it is legal, empties a's hand, and
    (Four being a finishable rank) actually wins the game via the real
    _commit_play_cards path, producing PLAYER_WON + GAME_FINISHED
    events for room.apply() to return.
    """

    winning_card = Card(rank=Rank.FOUR, suit=Suit.HEARTS)
    top_card = Card(rank=Rank.FOUR, suit=Suit.HEARTS)

    a_index = next(
        index for index, player in enumerate(room.state.players)
        if player.id == "a"
    )

    new_hands = dict(room.state.hands)
    new_hands["a"] = (winning_card,)
    # Leave b with something so the room isn't ALSO a last-player-
    # standing finish — this test wants the plain "played their way to
    # zero" path specifically.
    if len(new_hands.get("b", ())) == 0:
        new_hands["b"] = (Card(rank=Rank.FIVE, suit=Suit.CLUBS),)

    room.state = room.state.replace(
        hands=new_hands,
        discard_pile=tuple(list(room.state.discard_pile) + [top_card]),
        current_player_index=a_index,
        pending_draw_count=0,
        active_suit=None,
        pending_question_player_id=None,
        pending_skip_player_id=None,
    )

    return winning_card


def test_rest_play_that_finishes_the_game_records_a_result():
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
    _rig_state_so_a_wins_by_playing_a_four(room)

    response = client.post(
        f"/api/rooms/{room_id}/play",
        json={"player_id": "a", "rank": "4", "suit": "hearts"},
    )
    assert response.status_code == 200

    event_types = [event["type"] for event in response.json()["events"]]
    assert "game_finished" in event_types

    scoreboard = db.get_scoreboard(room_id)
    assert scoreboard == [{"player_id": "a", "wins": 1}]

    # And it's visible through the REST room view too, resolved to a
    # display name rather than a bare id.
    room_view = client.get(f"/api/rooms/{room_id}").json()
    assert room_view["scoreboard"] == [
        {"player_id": "a", "name": "Amina", "wins": 1}
    ]


def test_websocket_play_that_finishes_the_game_broadcasts_scoreboard():
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
    _rig_state_so_a_wins_by_playing_a_four(room)

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id=a"
    ) as ws:
        ws.receive_json()  # initial state on connect

        ws.send_json(
            {
                "type": "play_cards",
                "cards": [{"rank": "4", "suit": "hearts"}],
            }
        )

        message = ws.receive_json()

        assert message["type"] == "state"
        assert message["room"]["state"]["phase"] == "finished"
        assert message["room"]["state"]["winner_id"] == "a"
        assert message["room"]["scoreboard"] == [
            {"player_id": "a", "name": "Amina", "wins": 1}
        ]

    # And the DB itself agrees, independent of what got broadcast.
    assert db.get_scoreboard(room_id) == [{"player_id": "a", "wins": 1}]


def test_scoreboard_accumulates_across_a_restart_in_the_same_room():
    """
    The exact thing the user asked for: a RUNNING tally per room across
    restarts/replays, not a one-shot record.
    """

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
    _rig_state_so_a_wins_by_playing_a_four(room)

    client.post(
        f"/api/rooms/{room_id}/play",
        json={"player_id": "a", "rank": "4", "suit": "hearts"},
    )

    assert db.get_scoreboard(room_id) == [{"player_id": "a", "wins": 1}]

    # Play again, same room — restart deals a fresh round for the same
    # seated players.
    room.restart("a")
    _rig_state_so_a_wins_by_playing_a_four(room)

    client.post(
        f"/api/rooms/{room_id}/play",
        json={"player_id": "a", "rank": "4", "suit": "hearts"},
    )

    # Second win, same room, same player -> the tally accumulates
    # rather than being overwritten.
    assert db.get_scoreboard(room_id) == [{"player_id": "a", "wins": 2}]


def test_a_move_that_does_not_finish_the_game_records_nothing():
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

    a_index = next(
        index for index, player in enumerate(room.state.players)
        if player.id == "a"
    )
    top_card = Card(rank=Rank.FIVE, suit=Suit.HEARTS)
    new_hands = dict(room.state.hands)
    # a keeps more than one card after this play — not a finish
    # either way, and avoids tripping the separate "must declare Niko
    # Kadi when going down to exactly one card" rule, which isn't what
    # this test is about.
    new_hands["a"] = (
        Card(rank=Rank.FIVE, suit=Suit.HEARTS),
        Card(rank=Rank.SIX, suit=Suit.CLUBS),
        Card(rank=Rank.NINE, suit=Suit.SPADES),
    )
    room.state = room.state.replace(
        hands=new_hands,
        discard_pile=tuple(list(room.state.discard_pile) + [top_card]),
        current_player_index=a_index,
        pending_draw_count=0,
        active_suit=None,
        pending_question_player_id=None,
        pending_skip_player_id=None,
    )

    response = client.post(
        f"/api/rooms/{room_id}/play",
        json={"player_id": "a", "rank": "5", "suit": "hearts"},
    )
    assert response.status_code == 200

    assert db.get_scoreboard(room_id) == []


def test_scoreboard_empty_before_any_game_finishes():
    client = TestClient(app)

    room_id = client.post("/api/rooms").json()["room_id"]

    view = client.get(f"/api/rooms/{room_id}").json()
    assert view["scoreboard"] == []
    assert db.get_scoreboard(room_id) == []
