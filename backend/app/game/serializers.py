"""
Serialization helpers.

These convert internal Python objects into JSON-safe dictionaries.

Important:
- Do not expose every player's hand.
- Each player should only see their own hand.
- Other players should only expose card counts.
"""

from __future__ import annotations

from app.game.room import GameRoom
from app.rules.cards import Card


def serialize_card(card: Card) -> dict:
    return {
        "rank": card.rank.value,
        "suit": card.suit.value if card.suit else None,
        "joker_color": card.joker_color.value if card.joker_color else None,
        "label": card.label(),
    }


def serialize_scoreboard(room: GameRoom, scoreboard: list[dict]) -> list[dict]:
    """
    Resolves each scoreboard row's player_id to that player's CURRENT
    display name via the room's own player list — see app.db's module
    docstring for why names are never stored in the DB itself. A
    winner_player_id with no match in room.players (can't happen
    today; room.players is append-only, see GameRoom.add_player) is
    dropped defensively rather than shown with a blank name.
    """

    names_by_id = {player.id: player.name for player in room.players}

    resolved = [
        {"player_id": row["player_id"], "name": names_by_id[row["player_id"]], "wins": row["wins"]}
        for row in scoreboard
        if row["player_id"] in names_by_id
    ]

    return resolved


def serialize_room_for_player(
    room: GameRoom,
    player_id: str,
    scoreboard: list[dict] | None = None,
) -> dict:

    base = {
        "room_id": room.room_id,
        "started": room.started,
        "players": [
            {
                "id": player.id,
                "name": player.name,
            }
            for player in room.players
        ],
        # Room-scoped win tally (see app.db) — present even before a
        # game starts (always empty then) and even in a room with no
        # finished games yet, so the frontend never has to special-
        # case a missing key.
        "scoreboard": serialize_scoreboard(room, scoreboard or []),
    }

    if room.state is None:
        return {
            **base,
            "state": None,
        }

    state = room.state

    return {
        **base,
        "state": {
            "current_player": state.current_player.id,
            "phase": state.phase.value,
            "top_card": serialize_card(state.top_card),
            "direction": state.direction,
            "winner_id": state.winner_id,
            "pending_draw_count": state.pending_draw_count,
            "pending_question_player_id": state.pending_question_player_id,
            "pending_skip_player_id": state.pending_skip_player_id,
            "active_suit": (
                state.active_suit.value
                if state.active_suit
                else None
            ),
            # What a normal play (or question/draw/skip response) has
            # to match right now — an explicitly declared suit if one
            # is active, otherwise the suit of the nearest card in the
            # discard pile that actually has one (see
            # GameState.required_suit). Exposed so the client can
            # preview which cards in hand are currently legal without
            # duplicating the discard-pile walk-back itself.
            "required_suit": (
                state.required_suit.value
                if state.required_suit
                else None
            ),
            "draw_pile_count": len(state.draw_pile),
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "card_count": len(state.hand_of(player.id)),
                    "is_current_player": player.id == state.current_player.id,
                    "is_you": player.id == player_id,
                    "is_eliminated": player.id in state.eliminated_player_ids,
                    "has_declared_niko_kadi": (
                        player.id in state.niko_kadi_declared_by
                    ),
                }
                for player in state.players
            ],
            "my_hand": [
                serialize_card(card)
                for card in state.hand_of(player_id)
            ],
        },
    }