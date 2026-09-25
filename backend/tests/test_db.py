"""
Unit tests for app.db in isolation — no FastAPI, no rules engine, just
the SQLite wrapper itself: does a recorded result show up in the
scoreboard, correctly grouped and ordered, and correctly scoped per
room.
"""

import pytest

from app import db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    # A fresh, empty on-disk DB per test — see db._db_path(), which
    # reads KADI_DB_PATH fresh on every call rather than caching it at
    # import time, specifically so this works without a module reload.
    monkeypatch.setenv("KADI_DB_PATH", str(tmp_path / "test_kadi.db"))


def test_init_db_creates_the_schema_and_is_idempotent():
    db.init_db()
    db.init_db()  # must not raise on a second call

    assert db.get_scoreboard("ANY01") == []


def test_get_scoreboard_empty_room_returns_empty_list():
    assert db.get_scoreboard("EMPTY") == []


def test_record_and_read_back_a_single_win():
    db.record_game_result(
        room_id="ROOM1",
        winner_player_id="a",
        player_count=2,
        ended_reason=db.ENDED_REASON_FINISHED,
    )

    assert db.get_scoreboard("ROOM1") == [{"player_id": "a", "wins": 1}]


def test_repeat_wins_by_the_same_player_accumulate():
    for _ in range(3):
        db.record_game_result(
            room_id="ROOM1",
            winner_player_id="a",
            player_count=2,
            ended_reason=db.ENDED_REASON_FINISHED,
        )

    assert db.get_scoreboard("ROOM1") == [{"player_id": "a", "wins": 3}]


def test_scoreboard_is_sorted_most_wins_first():
    db.record_game_result(
        room_id="ROOM1", winner_player_id="a", player_count=3,
        ended_reason=db.ENDED_REASON_FINISHED,
    )
    for _ in range(2):
        db.record_game_result(
            room_id="ROOM1", winner_player_id="b", player_count=3,
            ended_reason=db.ENDED_REASON_FINISHED,
        )
    db.record_game_result(
        room_id="ROOM1", winner_player_id="c", player_count=3,
        ended_reason=db.ENDED_REASON_LAST_PLAYER_STANDING,
    )

    assert db.get_scoreboard("ROOM1") == [
        {"player_id": "b", "wins": 2},
        {"player_id": "a", "wins": 1},
        {"player_id": "c", "wins": 1},
    ]


def test_scoreboard_is_scoped_per_room():
    db.record_game_result(
        room_id="ROOM1", winner_player_id="a", player_count=2,
        ended_reason=db.ENDED_REASON_FINISHED,
    )
    db.record_game_result(
        room_id="ROOM2", winner_player_id="a", player_count=2,
        ended_reason=db.ENDED_REASON_FINISHED,
    )

    # Same player id, but different rooms don't share a tally — wins
    # are room-scoped, not tied to a durable cross-room identity (see
    # db.py's module docstring).
    assert db.get_scoreboard("ROOM1") == [{"player_id": "a", "wins": 1}]
    assert db.get_scoreboard("ROOM2") == [{"player_id": "a", "wins": 1}]


def test_a_null_winner_row_is_recorded_but_not_tallied():
    db.record_game_result(
        room_id="ROOM1",
        winner_player_id=None,
        player_count=2,
        ended_reason=db.ENDED_REASON_LAST_PLAYER_STANDING,
    )

    # Doesn't crash, and contributes nothing to anyone's win count.
    assert db.get_scoreboard("ROOM1") == []
