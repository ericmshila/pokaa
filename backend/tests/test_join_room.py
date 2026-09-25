"""
POST /api/rooms/{room_id}/join

Covers a real bug: room.add_player() raises ValueError for both
"game already started" and "player already exists", but the route
didn't used to catch it — an unhandled 500 instead of a clean 400.
That was also hiding a real gap: a player who gets disconnected
mid-game had no way to rejoin, since re-POSTing /join for a seat they
already hold used to be treated as an error instead of a no-op.
"""

import pytest
from fastapi.testclient import TestClient

from app.game.dependencies import connection_manager, room_manager
from app.main import app


@pytest.fixture(autouse=True)
def _reset_shared_state():
    room_manager.clear()
    connection_manager.active_connections.clear()
    yield
    room_manager.clear()
    connection_manager.active_connections.clear()


def test_joining_twice_with_the_same_player_id_is_idempotent():
    client = TestClient(app)
    room_id = client.post("/api/rooms").json()["room_id"]

    first = client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p1", "player_name": "Amina"},
    )
    assert first.status_code == 200
    assert first.json()["player_count"] == 1
    assert first.json()["already_seated"] is False

    second = client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p1", "player_name": "Amina"},
    )
    assert second.status_code == 200
    assert second.json()["player_count"] == 1
    assert second.json()["already_seated"] is True


def test_new_player_cannot_join_after_the_game_has_started():
    client = TestClient(app)
    room_id = client.post("/api/rooms").json()["room_id"]

    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p1", "player_name": "Amina"},
    )
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p2", "player_name": "Brian"},
    )
    client.post(f"/api/rooms/{room_id}/start")

    response = client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p3", "player_name": "Chao"},
    )

    assert response.status_code == 400
    assert "detail" in response.json()


def test_existing_player_can_rejoin_after_the_game_has_started():
    """
    Simulates reconnecting after a dropped WebSocket: re-POSTing
    /join for a seat you already hold must succeed, not 400/500.
    """

    client = TestClient(app)
    room_id = client.post("/api/rooms").json()["room_id"]

    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p1", "player_name": "Amina"},
    )
    client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p2", "player_name": "Brian"},
    )
    client.post(f"/api/rooms/{room_id}/start")

    response = client.post(
        f"/api/rooms/{room_id}/join",
        json={"player_id": "p1", "player_name": "Amina"},
    )

    assert response.status_code == 200
    assert response.json()["already_seated"] is True
    assert response.json()["player_count"] == 2


def test_joining_with_a_lowercased_room_code_still_works():
    """
    Room codes are short and meant to be read aloud/typed by hand —
    someone typing it back in lowercase (or with a stray space from
    copy-paste) shouldn't get "room not found".
    """

    client = TestClient(app)
    room_id = client.post("/api/rooms").json()["room_id"]
    assert room_id == room_id.upper()  # sanity: codes are generated upper-case

    response = client.post(
        f"/api/rooms/{room_id.lower()}/join",
        json={"player_id": "p1", "player_name": "Amina"},
    )

    assert response.status_code == 200
    assert response.json()["player_count"] == 1
