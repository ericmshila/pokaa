"""
Player actions.

Actions are requests.

Examples:

- Play card(s)
- Draw card(s)
- Accept a skip
- Declare Niko Kadi

The engine decides whether an action is legal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .cards import Card, Suit


class ActionType(str, Enum):
    PLAY_CARDS = "play_cards"
    DRAW = "draw"
    PASS = "pass"
    SAY_NIKO_KADI = "say_niko_kadi"
    QUIT = "quit"


@dataclass(frozen=True)
class PlayerAction:
    player_id: str
    type: ActionType


# ------------------------------------------------------------------
# Play cards
# ------------------------------------------------------------------

@dataclass(frozen=True)
class PlayCardsAction(PlayerAction):
    """
    Play one or more cards.

    Multi-card play is allowed only where
    the rules engine permits it.
    """

    cards: tuple[Card, ...]

    declared_suit: Optional[Suit] = None

    declare_niko_kadi: bool = False


# ------------------------------------------------------------------
# Draw
# ------------------------------------------------------------------

@dataclass(frozen=True)
class DrawAction(PlayerAction):
    """
    Draw one card or satisfy a pending draw punishment.
    """

    pass


# ------------------------------------------------------------------
# Pass
# ------------------------------------------------------------------

@dataclass(frozen=True)
class PassAction(PlayerAction):
    """
    Used primarily for skip resolution.

    Example:

    A plays Jack
    B has no Jack or chooses not to counter
    B passes
    B is skipped
    """

    pass


# ------------------------------------------------------------------
# Explicit Niko Kadi declaration
# ------------------------------------------------------------------

@dataclass(frozen=True)
class SayNikoKadiAction(PlayerAction):
    """
    Standalone declaration.

    Most of the time we expect
    declare_niko_kadi=True on PlayCardsAction.

    Keeping this allows future flexibility.
    """

    pass


# ------------------------------------------------------------------
# Quit
# ------------------------------------------------------------------

@dataclass(frozen=True)
class QuitAction(PlayerAction):
    """
    Leave an in-progress game voluntarily, at any point — not just on
    your own turn.

    The engine bypasses the usual turn-ownership check for this
    action (see apply_move), exactly like SayNikoKadiAction, since a
    player should be able to step away without waiting for their turn
    to come back around.
    """

    pass