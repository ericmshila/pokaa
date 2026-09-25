"""
Joker as a punishment card.

A Joker is no longer a wild "declare the next suit" card. It behaves
like a 2/3: playing one forces the next player to draw (5, by
default) or counter. It stacks with 2s/3s and other Jokers the same
way they stack with each other.

The one Joker-specific rule: countering an *active* Joker (i.e. the
top of the discard pile is currently a Joker) with a plain 2 or 3
requires that 2/3 to match the Joker's colour. Another Joker, or an
Ace, always counters regardless of colour.
"""

import pytest

from app.rules.actions import ActionType, PlayCardsAction
from app.rules.cards import Card, JokerColor, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import IllegalMove, apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_joker_forces_a_draw_of_five():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.JOKER, None, JokerColor.BLACK),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JOKER, None, JokerColor.BLACK),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 5
    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.current_player.id == "b"

    draw_events = [e for e in events if e.type == EventType.DRAW_STACK_STARTED]
    assert len(draw_events) == 1
    assert draw_events[0].payload["pending_draw_count"] == 5


def test_joker_is_always_playable_without_declaring_a_suit():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.JOKER, None, JokerColor.RED),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        # Top card shares neither rank nor suit with the Joker — a
        # normal card couldn't be played here, but a Joker always can.
        discard_pile=(Card(Rank.NINE, Suit.DIAMONDS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JOKER, None, JokerColor.RED),),
        declared_suit=None,
    )

    new_state, _events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.active_suit is None


def test_two_jokers_together_stack_to_ten():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.JOKER, None, JokerColor.BLACK),
                Card(Rank.JOKER, None, JokerColor.RED),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.JOKER, None, JokerColor.BLACK),
            Card(Rank.JOKER, None, JokerColor.RED),
        ),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 10

    draw_events = [e for e in events if e.type == EventType.DRAW_STACK_STARTED]
    assert draw_events[0].payload["pending_draw_count"] == 10


def test_matching_color_two_counters_and_stacks_on_top_of_joker():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.TWO, Suit.SPADES),  # black, matches the black Joker
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
        },
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=5,
        discard_pile=(Card(Rank.JOKER, None, JokerColor.BLACK),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.TWO, Suit.SPADES),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 7  # stacks: 5 + 2, doesn't cancel
    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE

    increase_events = [
        e for e in events if e.type == EventType.DRAW_STACK_INCREASED
    ]
    assert increase_events[0].payload["pending_draw_count"] == 7


def test_wrong_color_two_cannot_counter_joker():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.TWO, Suit.HEARTS),  # red, does NOT match black Joker
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
        },
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=5,
        discard_pile=(Card(Rank.JOKER, None, JokerColor.BLACK),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.TWO, Suit.HEARTS),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_any_joker_counters_a_joker_regardless_of_color():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.JOKER, None, JokerColor.RED),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
        },
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=5,
        discard_pile=(Card(Rank.JOKER, None, JokerColor.BLACK),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JOKER, None, JokerColor.RED),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 10  # 5 + 5, stacks


def test_ace_still_clears_joker_punishment_outright():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.ACE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
        },
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=5,
        discard_pile=(Card(Rank.JOKER, None, JokerColor.BLACK),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.HEARTS),),
        declared_suit=Suit.HEARTS,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 0
    assert new_state.phase == Phase.AWAITING_MOVE

    cleared = [e for e in events if e.type == EventType.PUNISHMENT_CLEARED]
    assert len(cleared) == 1


def test_normal_play_resumes_the_suit_underneath_a_resolved_joker_chain():
    """
    Once a Joker punishment is settled (someone just draws instead of
    countering further), the discard pile's literal top card is the
    Joker itself — which has no suit. Normal play afterwards should
    still have to follow whatever suit was on top *before* the
    Joker(s), not be thrown wide open just because the very top card
    happens to be colourless.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.SIX, Suit.HEARTS),  # matches the hearts underneath
                Card(Rank.NINE, Suit.SPADES),  # matches neither suit nor rank
                # Filler so playing the six leaves 2 cards, not 1 —
                # a Niko Kadi requirement isn't what this test checks.
                Card(Rank.FOUR, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        phase=Phase.AWAITING_MOVE,
        # A 6 of hearts was on top, then two Jokers got stacked on it
        # (the second countering the first) before someone just drew
        # instead of continuing the chain.
        discard_pile=(
            Card(Rank.SIX, Suit.HEARTS),
            Card(Rank.JOKER, None, JokerColor.BLACK),
            Card(Rank.JOKER, None, JokerColor.RED),
        ),
    )

    illegal_action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.NINE, Suit.SPADES),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, illegal_action, rules)

    legal_action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.SIX, Suit.HEARTS),),
    )

    new_state, _events = apply_move(state, legal_action, rules)
    assert new_state.current_player.id == "b"


def test_suit_not_color_governs_once_a_plain_two_is_on_top():
    """
    The colour restriction only applies while a Joker is directly on
    top of the discard pile. Once someone stacks a plain 2/3 on top
    of it, the colour check is gone — but normal suit-matching for
    draw counters (see test_draw_response_suit_matching.py) applies
    instead: a 3 of spades matches the 2 of spades now on top, even
    though its colour wouldn't have matched the Joker underneath.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.THREE, Suit.SPADES),  # matches the 2 on top by suit
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=7,
        # A black-Joker punishment already had a black 2 stacked on
        # top of it, so the discard top is now that plain 2, not the
        # Joker itself.
        discard_pile=(
            Card(Rank.JOKER, None, JokerColor.BLACK),
            Card(Rank.TWO, Suit.SPADES),
        ),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.THREE, Suit.SPADES),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 10  # 7 + 3, no colour check applied


def test_mismatched_suit_still_rejected_once_a_plain_two_is_on_top():
    """
    Same setup as above, but the 3 doesn't match the plain 2's suit —
    the colour check is gone (this isn't a Joker anymore), but the
    ordinary suit-matching rule for draw counters still applies and
    still blocks it.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.THREE, Suit.DIAMONDS),  # wrong suit for the 2 of spades on top
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=7,
        discard_pile=(
            Card(Rank.JOKER, None, JokerColor.BLACK),
            Card(Rank.TWO, Suit.SPADES),
        ),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.THREE, Suit.DIAMONDS),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)
