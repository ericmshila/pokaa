"""
Persistence: finished-game history and the per-room win scoreboard.

This is the one place SQL lives. Deliberately plain ``sqlite3`` from
the standard library rather than an ORM or async driver — the whole
job here is "append a row when a game finishes, sum rows by winner
when asked", and a single small table does that without pulling in a
new dependency. See db.README (module docstring below) for the
concurrency/scaling notes if this ever needs to grow past one process.

Design:

- One append-only table, ``game_results`` — one row per FINISHED game
  (see app.rules.events.EventType.GAME_FINISHED), not a mutable
  per-player counter. Counting rows to get a scoreboard is trivial and
  can never drift out of sync with "what actually happened"; a
  directly-mutated counter can (double-increment bugs, a write that
  partially fails, etc). It also leaves room to answer other questions
  later (games played, last winner, win rate) from the same table
  without a schema change — which is the "whatever else needs to
  persist" the room-scoped scoreboard implies, without speculatively
  building out tables nothing asks for yet.
- Player *names* are deliberately NOT stored here. A player's current
  display name always lives on the room's own player list
  (GameRoom.players, via app.game.room — see get_scoreboard's caller
  in app.game.serializers), which is the single source of truth for
  "what is this player currently called". Storing a name here too
  would just be a second place for it to go stale.
- Scope is intentionally room-local: wins are tallied for the group
  currently playing together in one room (a room code), not tied to
  any durable player identity across visits. That matches how the app
  already works — join with a name, no login — and avoids having to
  invent an account system this app doesn't otherwise have. A given
  browser tab's player_id is stable for that tab's session
  (see frontend App.tsx's sessionStorage-backed id), so it correctly
  tracks one person across restarts of the SAME room while they stay
  in that tab.

Concurrency: every call opens a short-lived connection and closes it
— simpler and safer than sharing one connection across FastAPI's
threadpool (sync routes) and asyncio.to_thread calls (the async
WebSocket path) than trying to manage one long-lived connection's
thread-affinity. SQLite handles many short connections against one
file fine at this scale (a handful of concurrent casual card games).
If this ever needs to run as multiple backend processes/instances,
SQLite (a single on-disk file) stops being the right tool regardless
of connection strategy — that's a bigger architecture change (a real
client-server DB) than this module's job.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# Resolved relative to this file (backend/app/db.py -> backend/data/
# kadi.db) rather than the process's current working directory, so
# the default location is stable no matter where uvicorn/pytest was
# launched from. Override with KADI_DB_PATH (e.g. to point at a
# platform's persistent-disk mount, or a temp file in tests) — read
# fresh on every call rather than cached at import time, so tests can
# monkeypatch the environment variable per-test without needing to
# reload this module.
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "kadi.db"


def _db_path() -> Path:
    override = os.environ.get("KADI_DB_PATH")
    return Path(override) if override else _DEFAULT_DB_PATH


_SCHEMA = """
CREATE TABLE IF NOT EXISTS game_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    winner_player_id TEXT,
    player_count INTEGER NOT NULL,
    ended_reason TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_game_results_room_id
    ON game_results (room_id);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """
    Ensures the schema exists. Not strictly required before calling
    the functions below (``_connect`` runs the same schema script on
    every connection, idempotently — CREATE TABLE/INDEX IF NOT EXISTS
    is cheap), but calling this once at app startup (see app.main's
    lifespan) surfaces a broken DB path/permissions problem
    immediately on boot rather than on the first game anyone finishes.
    """

    with _connect():
        pass


# A finished game either ended because someone actually played their
# way to an empty, winning hand ("finished"), or because everyone else
# forfeited/quit and one player was simply left standing
# ("last_player_standing") — see engine._conclude_if_one_player_remains
# vs the normal win path in engine._commit_play_cards. Kept as a plain
# string column rather than a foreign-keyed lookup table: it's exactly
# two values, chosen for readability in a future query, not modeled as
# its own entity.
ENDED_REASON_FINISHED = "finished"
ENDED_REASON_LAST_PLAYER_STANDING = "last_player_standing"


def record_game_result(
    *,
    room_id: str,
    winner_player_id: str | None,
    player_count: int,
    ended_reason: str,
) -> None:
    """
    Appends one row for a game that just finished. Called once per
    GAME_FINISHED event — see the callers in app.api.websocket and
    app.api.routes, which both funnel every state-changing action
    through a single broadcast point already, making that the natural
    place to check "did this action's events include GAME_FINISHED?"
    rather than threading a DB call through every individual action
    handler.

    winner_player_id is nullable defensively (it always exists on
    schema records from GAME_FINISHED payloads today) rather than
    romantically because it's not clearly required — it just costs
    nothing to allow a null "no winner" row instead of crashing this
    process if some future path ever finishes a game without one.
    """

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO game_results
                (room_id, winner_player_id, player_count, ended_reason, finished_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                room_id,
                winner_player_id,
                player_count,
                ended_reason,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_scoreboard(room_id: str) -> list[dict]:
    """
    Win tally for one room, most wins first. Each entry is
    ``{"player_id": ..., "wins": N}`` — deliberately no name here (see
    the module docstring: names are resolved against the room's own
    live player list by the caller, which is always current).

    Only counts rows with a winner — a null-winner row (see
    record_game_result) contributes to game history but nobody's
    tally.
    """

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT winner_player_id, COUNT(*) AS wins
            FROM game_results
            WHERE room_id = ? AND winner_player_id IS NOT NULL
            GROUP BY winner_player_id
            ORDER BY wins DESC, winner_player_id ASC
            """,
            (room_id,),
        ).fetchall()

    return [
        {"player_id": winner_player_id, "wins": wins}
        for winner_player_id, wins in rows
    ]
