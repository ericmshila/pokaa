"""
Shared "did this action just finish the game, and if so what should we
record" logic.

Used by both the WebSocket action handler (app.api.websocket, the
path the actual frontend plays through) and the REST play/draw/pass
endpoints (app.api.routes, kept around for direct/debug testing) —
factored out here so the two paths can't quietly drift on what counts
as a finish or how it gets classified. See app.db for the actual
storage.
"""

from __future__ import annotations

from app import db
from app.game.room import GameRoom
from app.rules.events import EventType, GameEvent


def maybe_record_game_result(
    room: GameRoom,
    room_id: str,
    events: list[GameEvent],
) -> None:
    """
    Inspects one action's resulting events for a GAME_FINISHED and, if
    present, appends a row to the scoreboard history. A no-op for any
    action that didn't just end the game (the overwhelming majority).
    """

    finished = next(
        (event for event in events if event.type == EventType.GAME_FINISHED),
        None,
    )

    if finished is None:
        return

    # A game can finish because someone actually played their way to
    # an empty, winning hand, or because everyone else forfeited/quit
    # and one player was simply left standing — see
    # engine._conclude_if_one_player_remains vs the normal win path in
    # engine._commit_play_cards. Distinguished here by whether an
    # elimination/departure event rode along in the same batch, rather
    # than teaching the pure rules engine about persistence.
    ended_reason = (
        db.ENDED_REASON_LAST_PLAYER_STANDING
        if any(
            event.type in (EventType.PLAYER_ELIMINATED, EventType.PLAYER_LEFT)
            for event in events
        )
        else db.ENDED_REASON_FINISHED
    )

    db.record_game_result(
        room_id=room_id,
        winner_player_id=finished.payload.get("winner_id"),
        player_count=len(room.players),
        ended_reason=ended_reason,
    )
