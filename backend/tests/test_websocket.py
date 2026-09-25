"""
WebSocket endpoint tests.

Room creation / joining / starting still happens over REST; the
WebSocket is exercised for connection handshakes and live gameplay.
"""

import pytest
from fastapi.testclient import TestClient

from app.game.dependencies import connection_manager, room_manager
from app.main import app
from app.rules.cards import Card, JokerColor, Rank, Suit


@pytest.fixture(autouse=True)
def _reset_shared_state():
    """
    room_manager / connection_manager are process-wide singletons
    (see app.game.dependencies), so tests must not leak state between
    each other.
    """
    room_manager.clear()
    connection_manager.active_connections.clear()
    yield
    room_manager.clear()
    connection_manager.active_connections.clear()


def _create_and_start_room(client: TestClient, player_ids=("p1", "p2")):
    room_id = client.post("/api/rooms").json()["room_id"]

    for player_id in player_ids:
        client.post(
            f"/api/rooms/{room_id}/join",
            json={"player_id": player_id, "player_name": player_id},
        )

    client.post(f"/api/rooms/{room_id}/start")

    return room_id


def test_connect_without_player_id_is_rejected():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/ws/rooms/{room_id}"):
            pass


def test_connect_to_unknown_room_is_rejected():
    client = TestClient(app)

    with pytest.raises(Exception):
        with client.websocket_connect("/api/ws/rooms/does-not-exist?player_id=p1"):
            pass


def test_connect_as_non_member_is_rejected():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/api/ws/rooms/{room_id}?player_id=stranger"
        ):
            pass


def test_connect_receives_initial_personalized_state():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    with client.websocket_connect(f"/api/ws/rooms/{room_id}?player_id=p1") as ws:
        message = ws.receive_json()

        assert message["type"] == "state"
        assert message["room"]["room_id"] == room_id
        assert message["room"]["state"] is not None
        # p1 should see their own hand and only card counts for others.
        assert "my_hand" in message["room"]["state"]
        assert len(message["room"]["state"]["my_hand"]) > 0


def test_illegal_move_returns_error_to_sender_only():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    with client.websocket_connect(f"/api/ws/rooms/{room_id}?player_id=p1") as ws1:
        ws1.receive_json()  # initial state

        with client.websocket_connect(
            f"/api/ws/rooms/{room_id}?player_id=p2"
        ) as ws2:
            ws2.receive_json()  # initial state
            ws1.receive_json()  # player_connected notice for p2

            # p2 is not the current player yet (p1 goes first) — any
            # action from p2 must be rejected.
            ws2.send_json({"type": "draw"})

            error = ws2.receive_json()
            assert error["type"] == "error"


def test_valid_move_broadcasts_state_to_all_connected_players():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id
    other_player_id = next(
        p.id for p in room.players if p.id != current_player_id
    )

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws_current:
        ws_current.receive_json()  # initial state

        with client.websocket_connect(
            f"/api/ws/rooms/{room_id}?player_id={other_player_id}"
        ) as ws_other:
            ws_other.receive_json()  # initial state
            ws_current.receive_json()  # player_connected notice

            # Draw is always legal on a fresh turn.
            ws_current.send_json({"type": "draw"})

            update_current = ws_current.receive_json()
            update_other = ws_other.receive_json()

            assert update_current["type"] == "state"
            assert update_other["type"] == "state"
            assert any(
                event["type"] == "cards_drawn"
                for event in update_current["events"]
            )


def test_multi_card_play_over_the_real_websocket_wire():
    """
    Full-stack check that a multi-card play actually works end to
    end: JSON -> _parse_action -> room.apply -> broadcast, not just
    the pure apply_move() function tested in test_multi_card_play.py.

    Rigs the dealt hand directly (rooms deal randomly over REST) so
    the current player provably holds two 2s they can legally open
    with, then sends both in one play_cards message and checks both
    connected clients see the stacked draw pressure.
    """

    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id
    other_player_id = next(
        p.id for p in room.players if p.id != current_player_id
    )

    rigged_hand = (
        Card(Rank.TWO, Suit.HEARTS),
        Card(Rank.TWO, Suit.SPADES),
        Card(Rank.FOUR, Suit.CLUBS),
        Card(Rank.FIVE, Suit.CLUBS),
    )
    new_hands = dict(room.state.hands)
    new_hands[current_player_id] = rigged_hand
    room.state = room.state.replace(
        hands=new_hands,
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws_current:
        ws_current.receive_json()  # initial state

        with client.websocket_connect(
            f"/api/ws/rooms/{room_id}?player_id={other_player_id}"
        ) as ws_other:
            ws_other.receive_json()  # initial state
            ws_current.receive_json()  # player_connected notice

            ws_current.send_json(
                {
                    "type": "play_cards",
                    "cards": [
                        {"rank": "2", "suit": "hearts"},
                        {"rank": "2", "suit": "spades"},
                    ],
                    "declared_suit": None,
                    "declare_niko_kadi": False,
                }
            )

            update_current = ws_current.receive_json()
            update_other = ws_other.receive_json()

    assert update_current["type"] == "state"
    assert update_current["room"]["state"]["pending_draw_count"] == 4
    assert update_other["room"]["state"]["pending_draw_count"] == 4

    draw_events = [
        e
        for e in update_current["events"]
        if e["type"] == "draw_stack_started"
    ]
    assert len(draw_events) == 1
    assert draw_events[0]["payload"]["pending_draw_count"] == 4


def test_joker_punishment_over_the_real_websocket_wire():
    """
    Proves the "joker_color" field survives the full round trip:
    serialized out to the client, sent back in a play_cards message,
    parsed back into a Card the engine recognizes as matching what's
    actually in the rigged hand (Card equality includes joker_color,
    so a mismatch here would surface as an IllegalMove instead of a
    JSON bug).
    """

    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id
    other_player_id = next(
        p.id for p in room.players if p.id != current_player_id
    )

    rigged_hand = (
        Card(Rank.JOKER, None, JokerColor.BLACK),
        Card(Rank.FOUR, Suit.CLUBS),
        Card(Rank.FIVE, Suit.CLUBS),
    )
    new_hands = dict(room.state.hands)
    new_hands[current_player_id] = rigged_hand
    room.state = room.state.replace(
        hands=new_hands,
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws_current:
        initial = ws_current.receive_json()  # initial state

        # The server's own serialization should already round-trip
        # the black Joker's colour correctly.
        joker_view = next(
            card
            for card in initial["room"]["state"]["my_hand"]
            if card["rank"] == "JOKER"
        )
        assert joker_view["joker_color"] == "black"

        with client.websocket_connect(
            f"/api/ws/rooms/{room_id}?player_id={other_player_id}"
        ) as ws_other:
            ws_other.receive_json()  # initial state
            ws_current.receive_json()  # player_connected notice

            ws_current.send_json(
                {
                    "type": "play_cards",
                    "cards": [
                        {"rank": "JOKER", "suit": None, "joker_color": "black"},
                    ],
                    "declared_suit": None,
                    "declare_niko_kadi": False,
                }
            )

            update_current = ws_current.receive_json()
            update_other = ws_other.receive_json()

    assert update_current["type"] == "state"
    assert update_current["room"]["state"]["pending_draw_count"] == 5
    assert update_other["room"]["state"]["pending_draw_count"] == 5
    assert update_current["room"]["state"]["phase"] == "awaiting_draw_response"


def test_chat_broadcasts_to_everyone_including_the_sender():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id
    other_player_id = next(
        p.id for p in room.players if p.id != current_player_id
    )

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws_current:
        ws_current.receive_json()  # initial state

        with client.websocket_connect(
            f"/api/ws/rooms/{room_id}?player_id={other_player_id}"
        ) as ws_other:
            ws_other.receive_json()  # initial state
            ws_current.receive_json()  # player_connected notice

            ws_current.send_json({"type": "chat", "text": "gg everyone"})

            received_current = ws_current.receive_json()
            received_other = ws_other.receive_json()

    for received in (received_current, received_other):
        assert received["type"] == "chat"
        assert received["player_id"] == current_player_id
        assert received["name"] == current_player_id
        assert received["text"] == "gg everyone"


def test_chat_does_not_touch_game_state():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id
    state_before = room.state

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws:
        ws.receive_json()  # initial state
        ws.send_json({"type": "chat", "text": "hello"})
        ws.receive_json()  # chat broadcast

    assert room_manager.get_room(room_id).state == state_before


def test_chat_works_regardless_of_whose_turn_it_is():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id
    other_player_id = next(
        p.id for p in room.players if p.id != current_player_id
    )

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws_current:
        ws_current.receive_json()  # initial state

        with client.websocket_connect(
            f"/api/ws/rooms/{room_id}?player_id={other_player_id}"
        ) as ws_other:
            ws_other.receive_json()  # initial state
            ws_current.receive_json()  # player_connected notice

            # other_player_id is NOT the current player, but chat
            # should still work — it's not a rules-engine action.
            ws_other.send_json({"type": "chat", "text": "not my turn but hi"})

            received_current = ws_current.receive_json()
            received_other = ws_other.receive_json()

    for received in (received_current, received_other):
        assert received["type"] == "chat"
        assert received["player_id"] == other_player_id


def test_blank_chat_message_is_rejected():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws:
        ws.receive_json()  # initial state
        ws.send_json({"type": "chat", "text": "   "})

        error = ws.receive_json()
        assert error["type"] == "error"


def test_chat_message_is_truncated_to_max_length():
    client = TestClient(app)
    room_id = _create_and_start_room(client)

    room = room_manager.get_room(room_id)
    current_player_id = room.state.current_player.id

    with client.websocket_connect(
        f"/api/ws/rooms/{room_id}?player_id={current_player_id}"
    ) as ws:
        ws.receive_json()  # initial state
        ws.send_json({"type": "chat", "text": "x" * 5000})

        received = ws.receive_json()
        assert len(received["text"]) == 500
