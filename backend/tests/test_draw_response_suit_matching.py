"""
Countering draw pressure (a 2 or 3) with another plain draw card
follows the same "same rank always works, otherwise match the suit"
rule as a normal turn play (see engine._matches_required_suit_or_rank):

- Same rank as the top card: always legal, any suit. A 2 cancels a 2,
  a 3 cancels a 3, regardless of what suit either one is.
- Different rank: needs to match the top card's suit. 3 of diamonds
  cancels 2 of diamonds; 3 of diamonds does NOT cancel 2 of hearts.

Before this, "another draw card" of any suit was enough regardless of
rank, which let a completely unrelated 2/3 cancel punishment just by
sharing the "draw card" family — that's what the different-rank case
above fixes.

This is separate from (and layered underneath) the existing
Joker-colour rule in test_joker_punishment.py: that one only governs
countering an *active Joker* with a plain 2/3 (colour, not suit,
since a Joker has no suit of its own). Once the top of the pile is a
plain 2/3 again, the rank-or-suit rule above is what matters, as
covered here.

A Joker still counters unconditionally either way (see
test_joker_can_still_counter_regardless_of_suit below), and an Ace
still counters unconditionally too (see test_ace_rules.py /
test_rules_engine.py::test_ace_counters_draw_punishment) — this rule
is specific to plain-2/3-vs-plain-2/3.
"""

import pytest

from app.rules.actions import ActionType, PlayCardsAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import IllegalMove, apply_move
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_three_counters_two_of_the_same_suit():
    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.THREE, Suit.DIAMONDS),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.TWO, Suit.DIAMONDS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.THREE, Suit.DIAMONDS),),
        declare_niko_kadi=True,  # leaves a lone, finishable 4 in hand
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == 5  # 2 + 3
    assert new_state.top_card == Card(Rank.THREE, Suit.DIAMONDS)


def test_three_cannot_counter_two_of_a_different_suit():
    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.THREE, Suit.DIAMONDS),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.THREE, Suit.DIAMONDS),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_two_counters_two_regardless_of_suit():
    """
    Matching the top card's rank is its own escape hatch here, same
    as a normal turn play (see _matches_required_suit_or_rank) — a 2
    of spades cancels a 2 of hearts just fine, they're both 2s. The
    suit requirement only kicks in when the rank differs (see
    test_three_cannot_counter_two_of_a_different_suit above).
    """

    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.TWO, Suit.SPADES),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.TWO, Suit.SPADES),),
        declare_niko_kadi=True,  # leaves a lone, finishable 4 in hand
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == 4  # 2 + 2
    assert new_state.top_card == Card(Rank.TWO, Suit.SPADES)


def test_three_counters_three_regardless_of_suit():
    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=3,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.THREE, Suit.CLUBS),
                Card(Rank.FOUR, Suit.HEARTS),
            ),
        },
        discard_pile=(Card(Rank.THREE, Suit.SPADES),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.THREE, Suit.CLUBS),),
        declare_niko_kadi=True,  # leaves a lone, finishable 4 in hand
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == 6  # 3 + 3
    assert new_state.top_card == Card(Rank.THREE, Suit.CLUBS)


def test_multi_card_counter_legal_if_any_one_card_matches_suit():
    """
    Same "any one of the group" convention used for normal turn plays
    and question answers (see test_multi_card_play.py) — playing two
    2s together only needs one of them to match the required suit;
    the other rides along on the shared rank.
    """

    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=3,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.TWO, Suit.HEARTS),  # matches
                Card(Rank.TWO, Suit.CLUBS),  # doesn't, rides along
                Card(Rank.FIVE, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.THREE, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.TWO, Suit.CLUBS),
        ),
        declare_niko_kadi=True,  # leaves a lone, finishable 5 in hand
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 7  # 3 + 2 + 2


def test_joker_can_still_counter_regardless_of_suit():
    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.JOKER, None),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JOKER, None),),
        declare_niko_kadi=True,  # leaves a lone, finishable 4 in hand
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == 7  # 2 + 5
