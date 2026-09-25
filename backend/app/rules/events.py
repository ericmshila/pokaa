"""
Game events.

Events describe things that have already happened.

They are produced by the rules engine and can later be:

- Sent to clients
- Logged
- Stored for replays
- Used by AI
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventType(str, Enum):

    # ---------------------------------------------------------
    # Game lifecycle
    # ---------------------------------------------------------

    GAME_STARTED = "game_started"

    GAME_FINISHED = "game_finished"

    PLAYER_WON = "player_won"

    # ---------------------------------------------------------
    # Card events
    # ---------------------------------------------------------

    CARD_PLAYED = "card_played"

    CARDS_DRAWN = "cards_drawn"

    SUIT_DECLARED = "suit_declared"

    # ---------------------------------------------------------
    # Turn events
    # ---------------------------------------------------------

    TURN_ADVANCED = "turn_advanced"

    DIRECTION_REVERSED = "direction_reversed"

    # ---------------------------------------------------------
    # Draw mechanics
    # ---------------------------------------------------------

    DRAW_STACK_STARTED = "draw_stack_started"

    DRAW_STACK_INCREASED = "draw_stack_increased"

    DRAW_STACK_CLEARED = "draw_stack_cleared"

    # ---------------------------------------------------------
    # Question mechanics
    # ---------------------------------------------------------

    QUESTION_ASKED = "question_asked"

    QUESTION_ANSWERED = "question_answered"

    QUESTION_FAILED = "question_failed"

    # ---------------------------------------------------------
    # Skip mechanics
    # ---------------------------------------------------------

    SKIP_STARTED = "skip_started"

    SKIP_COUNTERED = "skip_countered"

    PLAYER_SKIPPED = "player_skipped"

    # ---------------------------------------------------------
    # Ace mechanics
    # ---------------------------------------------------------

    ACE_COUNTER_PLAYED = "ace_counter_played"

    PUNISHMENT_CLEARED = "punishment_cleared"

    # ---------------------------------------------------------
    # Niko Kadi
    # ---------------------------------------------------------

    NIKO_KADI_DECLARED = "niko_kadi_declared"

    NIKO_KADI_REQUIRED = "niko_kadi_required"

    NIKO_KADI_PENALTY = "niko_kadi_penalty"

    # ---------------------------------------------------------
    # Forfeits
    # ---------------------------------------------------------

    PLAYER_ELIMINATED = "player_eliminated"

    # A voluntary mid-game departure — distinct from PLAYER_ELIMINATED
    # (a forced-draw punishment forfeit) so the UI can describe the
    # two differently.
    PLAYER_LEFT = "player_left"


@dataclass(frozen=True)
class GameEvent:
    """
    Generic structured event.

    Example:

    GameEvent(
        type=EventType.CARD_PLAYED,
        payload={
            "player_id": "p1",
            "card": "5H"
        }
    )
    """

    type: EventType

    payload: dict[str, Any]