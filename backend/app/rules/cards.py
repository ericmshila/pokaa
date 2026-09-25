"""
Card models for Kenyan Poker / Kadi.

This module contains only card-related concepts:
- Suits
- Ranks
- Card model
- Deck creation
- Deck shuffling

No game rules should live here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import random


class Suit(str, Enum):
    SPADES = "spades"
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"


class JokerColor(str, Enum):
    """
    A standard deck's two Jokers are printed in different colours.

    Kadi uses this to distinguish them for the "counter a Joker's
    draw pressure with a matching-colour punishment card" rule (see
    RuleConfig.draw_ranks / engine._card_color) — normal cards never
    set this; only Rank.JOKER cards do.
    """

    RED = "red"
    BLACK = "black"


_SUIT_COLORS: dict[Suit, str] = {
    Suit.HEARTS: "red",
    Suit.DIAMONDS: "red",
    Suit.SPADES: "black",
    Suit.CLUBS: "black",
}


class Rank(str, Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"
    JOKER = "JOKER"


@dataclass(frozen=True)
class Card:
    """
    A playing card.

    Jokers do not have a suit.
    Normal cards always have a suit.

    Jokers do carry a colour instead (``joker_color``), used only to
    check the "matching colour punishment card" counter rule. Normal
    cards leave this unset — use ``.color`` to get a card's colour
    regardless of whether it's a Joker or a suited card.
    """

    rank: Rank
    suit: Optional[Suit] = None
    joker_color: Optional[JokerColor] = None

    @property
    def is_joker(self) -> bool:
        return self.rank == Rank.JOKER

    @property
    def color(self) -> Optional[str]:
        """
        "red" or "black", for a suited card or a coloured Joker.
        None for a Joker with no assigned colour (shouldn't normally
        happen once dealt from ``build_deck``).
        """

        if self.is_joker:
            return self.joker_color.value if self.joker_color else None

        if self.suit is None:
            return None

        return _SUIT_COLORS[self.suit]

    @property
    def is_number_card(self) -> bool:
        return self.rank in {
            Rank.TWO,
            Rank.THREE,
            Rank.FOUR,
            Rank.FIVE,
            Rank.SIX,
            Rank.SEVEN,
            Rank.EIGHT,
            Rank.NINE,
            Rank.TEN,
        }

    def label(self) -> str:
        if self.is_joker:
            return "JOKER"

        if self.suit is None:
            return self.rank.value

        return f"{self.rank.value}{self.suit.value[0].upper()}"

    def __str__(self) -> str:
        return self.label()


def build_deck(
    seed: Optional[int] = None,
    include_jokers: int = 2,
) -> list[Card]:
    """
    Build a standard 52-card deck plus optional jokers.

    Args:
        include_jokers:
            Number of jokers to include (0-2). A real deck's two
            Jokers are printed in different colours, which Kadi uses
            for its "matching colour" counter rule, so the first
            Joker added is black and the second is red.

    Returns:
        A list of Card objects.
    """

    deck: list[Card] = []

    for suit in Suit:
        for rank in Rank:
            if rank == Rank.JOKER:
                continue

            deck.append(Card(rank=rank, suit=suit))

    joker_colors = (JokerColor.BLACK, JokerColor.RED)

    for i in range(include_jokers):
        color = joker_colors[i] if i < len(joker_colors) else None
        deck.append(Card(rank=Rank.JOKER, suit=None, joker_color=color))

    return deck


def shuffled_deck(
    seed: Optional[int] = None,
    include_jokers: int = 2) -> list:
    """
    Build and shuffle a deck.

    A seed can be supplied for deterministic tests.
    """

    deck = build_deck(include_jokers=include_jokers)
    rng = random.Random(seed)
    rng.shuffle(deck)
    return deck