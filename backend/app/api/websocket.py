"""
Real-time gameplay over WebSocket.

Responsibilities:
- Accept a connection for a player already seated in a room (joining a
  room still happens over REST — see ``app.api.routes``).
- Track that connection via the shared ConnectionManager.
- Translate incoming JSON messages into rules-engine PlayerActions.
- Broadcast a personalized game state to every connected player after
  each successful move.

No game rules live here — all legality checks happen in
``app.rules.engine``. This module is a thin translation layer between
JSON and the engine's action/event objects.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import db
from app.game.dependencies import connection_manager, room_manager
from app.game.game_results import maybe_record_game_result
from app.game.room import GameRoom
from app.game.serializers import serialize_room_for_player
from app.rules.actions import (
    ActionType,
    DrawAction,
    PassAction,
    PlayCardsAction,
    PlayerAction,
    QuitAction,
    SayNikoKadiAction,
)
from app.rules.cards import Card, JokerColor, Rank, Suit
from app.rules.engine import IllegalMove
from app.rules.events import GameEvent


router = APIRouter(
    prefix="/api",
    tags=["websocket"],
)

# Plenty for a casual room chat message; keeps one player from
# flooding everyone else's screen with a single giant paste.
_CHAT_MAX_LENGTH = 500


@router.websocket("/ws/rooms/{room_id}")
async def room_websocket(
    websocket: WebSocket,
    room_id: str,
) -> None:

    player_id = websocket.query_params.get("player_id")

    if not player_id:
        await websocket.close(code=4000, reason="player_id query param is required")
        return

    try:
        room = room_manager.get_room(room_id)
    except KeyError:
        await websocket.close(code=4004, reason="Room not found")
        return

    if not any(player.id == player_id for player in room.players):
        await websocket.close(
            code=4003,
            reason="Player has not joined this room. Join over REST first.",
        )
        return

    await connection_manager.connect(room_id, player_id, websocket)

    await _send_state(room_id, player_id, events=[])

    await connection_manager.broadcast_to_room(
        room_id,
        {"type": "player_connected", "player_id": player_id},
        exclude_player_id=player_id,
    )

    try:
        while True:
            try:
                message = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                await connection_manager.send_to_player(
                    room_id,
                    player_id,
                    {"type": "error", "detail": "Malformed message. Expected JSON."},
                )
                continue

            await _handle_message(room_id, player_id, message)

    except WebSocketDisconnect:
        connection_manager.disconnect(room_id, player_id)

        await connection_manager.broadcast_to_room(
            room_id,
            {"type": "player_disconnected", "player_id": player_id},
        )


# ---------------------------------------------------------------------
# Message handling
# ---------------------------------------------------------------------


async def _handle_message(
    room_id: str,
    player_id: str,
    message: dict[str, Any],
) -> None:

    try:
        room = room_manager.get_room(room_id)
    except KeyError:
        await connection_manager.send_to_player(
            room_id,
            player_id,
            {"type": "error", "detail": "Room not found"},
        )
        return

    if message.get("type") == "chat":
        # Not a rules-engine action and not gated on the game having
        # started (unlike everything below) — chat is just relayed to
        # everyone currently connected to the room, with no effect on
        # GameState at all.
        await _handle_chat(room, room_id, player_id, message)
        return

    if room.state is None:
        await connection_manager.send_to_player(
            room_id,
            player_id,
            {"type": "error", "detail": "Game has not started"},
        )
        return

    if message.get("type") == "restart":
        # Not a rules-engine "move" on the current state (it replaces
        # the state outright), so it's handled here rather than going
        # through _parse_action/room.apply like everything else. Any
        # player who was seated in this room may trigger it (see
        # GameRoom.restart) — not just the winner, since a round often
        # ends because someone forfeited rather than because anyone
        # actually chose to stop.
        try:
            events = room.restart(player_id)
        except ValueError as exc:
            await connection_manager.send_to_player(
                room_id,
                player_id,
                {"type": "error", "detail": str(exc)},
            )
            return

        await _broadcast_state(room_id, events)
        return

    try:
        action = _parse_action(player_id, message)
    except (ValueError, KeyError, TypeError) as exc:
        await connection_manager.send_to_player(
            room_id,
            player_id,
            {"type": "error", "detail": f"Invalid message: {exc}"},
        )
        return

    try:
        events = room.apply(action)
    except IllegalMove as exc:
        await connection_manager.send_to_player(
            room_id,
            player_id,
            {"type": "error", "detail": str(exc)},
        )
        return

    await _broadcast_state(room_id, events)


async def _handle_chat(
    room: GameRoom,
    room_id: str,
    player_id: str,
    message: dict[str, Any],
) -> None:
    """
    Relay a chat message to everyone currently connected to the room
    — including the sender, so every open tab/device for the same
    player shows an identical, single source of truth for the
    conversation rather than the sender optimistically rendering its
    own message locally.

    Plain text, no persistence, no encryption yet (see room_id being
    passed around in the clear elsewhere already) — this is a casual
    room chat, not a secure channel.
    """

    text = message.get("text")

    if not isinstance(text, str) or not text.strip():
        await connection_manager.send_to_player(
            room_id,
            player_id,
            {"type": "error", "detail": "Chat message cannot be empty."},
        )
        return

    text = text.strip()[:_CHAT_MAX_LENGTH]

    sender = next(
        (player for player in room.players if player.id == player_id),
        None,
    )
    sender_name = sender.name if sender is not None else player_id

    await connection_manager.broadcast_to_room(
        room_id,
        {
            "type": "chat",
            "player_id": player_id,
            "name": sender_name,
            "text": text,
        },
    )


def _parse_action(
    player_id: str,
    message: dict[str, Any],
) -> PlayerAction:
    """
    Translate a raw JSON message into a PlayerAction.

    Expected shapes:

    {"type": "play_cards", "cards": [{"rank": "5", "suit": "hearts"}],
     "declared_suit": null, "declare_niko_kadi": false}
    {"type": "play_cards", "cards": [{"rank": "JOKER", "suit": null,
     "joker_color": "black"}], "declared_suit": null,
     "declare_niko_kadi": false}
    {"type": "draw"}
    {"type": "pass"}
    {"type": "say_niko_kadi"}
    {"type": "quit"}
    """

    action_type = message.get("type")

    if action_type == "play_cards":
        cards_payload = message.get("cards") or []

        if not cards_payload:
            raise ValueError("At least one card is required.")

        cards = tuple(
            Card(
                rank=Rank(card["rank"]),
                suit=(
                    Suit(card["suit"])
                    if card.get("suit") is not None
                    else None
                ),
                joker_color=(
                    JokerColor(card["joker_color"])
                    if card.get("joker_color") is not None
                    else None
                ),
            )
            for card in cards_payload
        )

        declared_suit = message.get("declared_suit")

        return PlayCardsAction(
            player_id=player_id,
            type=ActionType.PLAY_CARDS,
            cards=cards,
            declared_suit=(
                Suit(declared_suit) if declared_suit is not None else None
            ),
            declare_niko_kadi=bool(message.get("declare_niko_kadi", False)),
        )

    if action_type == "draw":
        return DrawAction(
            player_id=player_id,
            type=ActionType.DRAW,
        )

    if action_type == "pass":
        return PassAction(
            player_id=player_id,
            type=ActionType.PASS,
        )

    if action_type == "say_niko_kadi":
        return SayNikoKadiAction(
            player_id=player_id,
            type=ActionType.SAY_NIKO_KADI,
        )

    if action_type == "quit":
        return QuitAction(
            player_id=player_id,
            type=ActionType.QUIT,
        )

    raise ValueError(f"Unknown action type: {action_type!r}")


# ---------------------------------------------------------------------
# Broadcasting
# ---------------------------------------------------------------------


async def _send_state(
    room_id: str,
    player_id: str,
    events: list[GameEvent],
) -> None:

    room = room_manager.get_room(room_id)
    scoreboard = await asyncio.to_thread(db.get_scoreboard, room_id)

    await connection_manager.send_to_player(
        room_id,
        player_id,
        {
            "type": "state",
            "room": serialize_room_for_player(room, player_id, scoreboard),
            "events": _serialize_events(events),
        },
    )


async def _broadcast_state(
    room_id: str,
    events: list[GameEvent],
) -> None:

    room = room_manager.get_room(room_id)
    # Every state-changing action (a rules-engine move, or a restart)
    # funnels through here, which makes this the one place that needs
    # to notice "did this just finish the game?" rather than
    # threading a DB call through every individual action handler.
    # Run in a thread — this handler is async, so a direct blocking
    # sqlite3 call would stall the event loop that's also serving
    # every other room's WebSocket traffic in this same process,
    # however briefly.
    await asyncio.to_thread(maybe_record_game_result, room, room_id, events)
    scoreboard = await asyncio.to_thread(db.get_scoreboard, room_id)

    serialized_events = _serialize_events(events)

    connected_player_ids = list(
        connection_manager.active_connections.get(room_id, {}).keys()
    )

    for connected_player_id in connected_player_ids:
        await connection_manager.send_to_player(
            room_id,
            connected_player_id,
            {
                "type": "state",
                "room": serialize_room_for_player(room, connected_player_id, scoreboard),
                "events": serialized_events,
            },
        )


def _serialize_events(events: list[GameEvent]) -> list[dict]:
    return [
        {"type": event.type.value, "payload": event.payload}
        for event in events
    ]
