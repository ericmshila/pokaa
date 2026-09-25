import pytest

from app.game import room as room_module
from app.game.room import _ROOM_CODE_ALPHABET, _ROOM_CODE_LENGTH
from app.game.room_manager import RoomManager
from app.rules.config import RuleConfig
from app.rules.state import Player


def test_create_room():
    manager = RoomManager()

    room = manager.create_room()

    assert room is not None
    assert room.room_id is not None
    assert manager.active_room_count() == 1
    assert manager.room_exists(room.room_id)


def test_room_code_is_short_and_easy_to_read():
    # Short enough to read aloud or type on a phone, and free of
    # characters people commonly mix up (I/L/O/0/1).
    manager = RoomManager()

    room = manager.create_room()

    assert len(room.room_id) == _ROOM_CODE_LENGTH
    assert all(char in _ROOM_CODE_ALPHABET for char in room.room_id)
    for ambiguous in "IL0O1":
        assert ambiguous not in room.room_id


def test_room_lookup_is_case_and_whitespace_insensitive():
    # Someone typing a code in by hand shouldn't get "not found" just
    # for lowercasing it or leaving a stray space from copy-paste.
    manager = RoomManager()

    room = manager.create_room()
    assert room.room_id == room.room_id.upper()  # sanity: codes are upper-case

    lowered = f" {room.room_id.lower()} "

    assert manager.room_exists(lowered)
    assert manager.get_room(lowered) is room


def test_create_room_retries_on_a_code_collision(monkeypatch):
    manager = RoomManager()

    # room_manager.create_room() calls room.create_room() (possibly
    # more than once, on a collision), which is what actually
    # generates the code — patching it here covers every call site.
    codes = iter(["AAAAA", "AAAAA", "BBBBB"])
    monkeypatch.setattr(
        room_module,
        "generate_room_code",
        lambda: next(codes),
    )

    first = manager.create_room()
    assert first.room_id == "AAAAA"

    # The next code generated collides with the first room's code —
    # the manager should notice and regenerate rather than clobbering
    # (or silently colliding with) the existing room.
    second = manager.create_room()
    assert second.room_id == "BBBBB"
    assert manager.active_room_count() == 2
    assert manager.get_room("AAAAA") is first
    assert manager.get_room("BBBBB") is second


def test_get_room_returns_same_room():
    manager = RoomManager()

    room = manager.create_room()

    retrieved = manager.get_room(room.room_id)

    assert retrieved is room


def test_get_unknown_room_raises_key_error():
    manager = RoomManager()

    with pytest.raises(KeyError):
        manager.get_room("does-not-exist")


def test_remove_room():
    manager = RoomManager()

    room = manager.create_room()

    assert manager.active_room_count() == 1

    manager.remove_room(room.room_id)

    assert manager.active_room_count() == 0
    assert not manager.room_exists(room.room_id)


def test_clear_removes_all_rooms():
    manager = RoomManager()

    manager.create_room()
    manager.create_room()
    manager.create_room()

    assert manager.active_room_count() == 3

    manager.clear()

    assert manager.active_room_count() == 0


def test_room_uses_supplied_rules():
    manager = RoomManager()

    rules = RuleConfig(initial_hand_size=5)

    room = manager.create_room(rules=rules)

    assert room.rules.initial_hand_size == 5


def test_player_can_join_room():
    manager = RoomManager()

    room = manager.create_room()

    player = Player(
        id="p1",
        name="Eric",
    )

    room.add_player(player)

    assert len(room.players) == 1
    assert room.players[0].id == "p1"


def test_duplicate_player_not_allowed():
    manager = RoomManager()

    room = manager.create_room()

    player = Player(
        id="p1",
        name="Eric",
    )

    room.add_player(player)

    with pytest.raises(ValueError):
        room.add_player(player)


def test_cannot_start_with_less_than_two_players():
    manager = RoomManager()

    room = manager.create_room()

    room.add_player(
        Player(
            id="p1",
            name="Eric",
        )
    )

    with pytest.raises(ValueError):
        room.start_game()


def test_game_starts_with_two_players():
    manager = RoomManager()

    room = manager.create_room()

    room.add_player(
        Player(
            id="p1",
            name="Eric",
        )
    )

    room.add_player(
        Player(
            id="p2",
            name="Angela",
        )
    )

    events = room.start_game(seed=1)

    assert room.has_started
    assert room.state is not None
    assert len(events) > 0


def test_cannot_join_after_game_starts():
    manager = RoomManager()

    room = manager.create_room()

    room.add_player(
        Player(
            id="p1",
            name="Eric",
        )
    )

    room.add_player(
        Player(
            id="p2",
            name="Angela",
        )
    )

    room.start_game(seed=1)

    with pytest.raises(ValueError):
        room.add_player(
            Player(
                id="p3",
                name="Brian",
            )
        )