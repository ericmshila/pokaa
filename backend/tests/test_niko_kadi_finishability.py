"""
"Niko Kadi" is a promise to win on the very next turn. Under the
default ruleset, every card can finish the game (see
test_finish_rules.py), so that promise is always literally true: by
the time a player is down to one card, playing it — whatever it is —
wins, and declaring "Niko Kadi" at that point is a straightforward,
honest announcement.

A stricter ruleset can still carve specific ranks back out of being
able to finish (via finishable_ranks / ace_can_finish /
joker_can_finish — see test_finish_rules.py). The
`restrict_lone_card_to_finishable` toggle covers what happens to a
player under such a ruleset: whether they're allowed to be LEFT
holding one of those unfinishable ranks as their only card in the
first place. Left False (the default), a player can still freely play
their way down to one, and can freely play that lone card too — they
just won't WIN by playing it, per test_finish_rules.py. Set True to
block reaching that state outright instead — see the
"_when_restricted" tests below, which build their own stricter
RuleConfig to have something to actually restrict, since nothing is
unfinishable under the plain default.
"""

import pytest
from dataclasses import replace

from app.rules.actions import ActionType, PlayCardsAction
from app.rules.cards import Card, JokerColor, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import IllegalMove, apply_move

from tests.test_rules_engine import make_state


def test_can_declare_niko_kadi_down_to_a_lone_ace_by_default():
    rules = RuleConfig()  # ace_can_finish is True by default

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),  # legal to play on the 7 of hearts
                Card(Rank.ACE, Suit.SPADES),  # would be the only card left
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
        declare_niko_kadi=True,
    )

    new_state, _events = apply_move(state, action, rules)

    assert new_state.hand_of("a") == (Card(Rank.ACE, Suit.SPADES),)
    assert "a" in new_state.niko_kadi_declared_by


def test_cannot_declare_niko_kadi_down_to_a_lone_unfinishable_ace_when_restricted():
    rules = replace(
        RuleConfig(),
        ace_can_finish=False,
        restrict_lone_card_to_finishable=True,
    )

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),
                Card(Rank.ACE, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
        declare_niko_kadi=True,
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)

    # Nothing should have moved out of the hand — the play never went through.


def test_can_declare_niko_kadi_down_to_a_power_card_by_default():
    """
    King is a "power"/effect card, but it's still in finishable_ranks
    by default (see test_finish_rules.py) — so being left holding
    only a King, and later winning by playing it, are both fine
    without needing to touch restrict_lone_card_to_finishable at all.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),
                Card(Rank.KING, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
        declare_niko_kadi=True,
    )

    new_state, _events = apply_move(state, action, rules)

    assert new_state.hand_of("a") == (Card(Rank.KING, Suit.SPADES),)
    assert "a" in new_state.niko_kadi_declared_by


def test_cannot_declare_niko_kadi_down_to_an_unfinishable_power_card_when_restricted():
    rules = replace(
        RuleConfig(),
        finishable_ranks=RuleConfig().finishable_ranks - {Rank.KING},
        restrict_lone_card_to_finishable=True,
    )

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),
                Card(Rank.KING, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
        declare_niko_kadi=True,
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_can_declare_niko_kadi_down_to_a_finishable_card():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),
                Card(Rank.NINE, Suit.SPADES),  # finishable, in the default set
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
        declare_niko_kadi=True,
    )

    new_state, _events = apply_move(state, action, rules)

    assert new_state.hand_of("a") == (Card(Rank.NINE, Suit.SPADES),)
    assert "a" in new_state.niko_kadi_declared_by


def test_lone_joker_is_allowed_by_default_but_blocked_when_restricted():
    rules = RuleConfig()  # joker_can_finish is True by default

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),
                Card(Rank.JOKER, None, JokerColor.BLACK),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
        declare_niko_kadi=True,
    )

    new_state, _events = apply_move(state, action, rules)
    assert new_state.hand_of("a") == (Card(Rank.JOKER, None, JokerColor.BLACK),)

    restrictive_rules = replace(
        RuleConfig(),
        joker_can_finish=False,
        restrict_lone_card_to_finishable=True,
    )
    with pytest.raises(IllegalMove):
        apply_move(state, action, restrictive_rules)


def test_the_restriction_applies_even_without_declaring_niko_kadi():
    """
    When restrict_lone_card_to_finishable is on, the block is on the
    state itself (ending up with an unfinishable lone card), not just
    on the declaration flag — so it still fires even if the player
    didn't set declare_niko_kadi on this action.
    """

    rules = replace(
        RuleConfig(),
        ace_can_finish=False,
        restrict_lone_card_to_finishable=True,
    )

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),
                Card(Rank.ACE, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
        declare_niko_kadi=False,
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)
