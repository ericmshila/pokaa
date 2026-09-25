"""
Multi-card plays: dropping two or more cards of the same rank in one
move.

The engine already validated the "same rank" shape rule before this
was wired up end-to-end — what was missing was that effect-bearing
cards (2/3 draw, Jack skip, King reverse) only ever applied their
effect once, using just the first card, regardless of how many were
actually played. These tests cover the fix: effects now apply once
per card.
"""

import pytest

from app.rules.actions import ActionType, PlayCardsAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import IllegalMove, apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_multi_card_play_requires_same_rank():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.THREE, Suit.HEARTS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
        ),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_two_twos_stack_draw_pressure_by_four_not_two():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.TWO, Suit.SPADES),
                # Filler so playing both 2s leaves 2 cards, not 0 or 1
                # — a bare win or a Niko Kadi requirement would mask
                # what this test is actually checking (draw stacking).
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
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.TWO, Suit.SPADES),
        ),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 4
    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert len(new_state.hand_of("a")) == 2

    draw_events = [e for e in events if e.type == EventType.DRAW_STACK_STARTED]
    assert len(draw_events) == 1
    assert draw_events[0].payload["pending_draw_count"] == 4


def test_stacking_two_more_twos_onto_existing_pressure():
    """
    Countering a draw card now requires matching its suit (see
    tests/test_draw_response_suit_matching.py) — so the top card here
    is a 3 of hearts, and the group counters it because one of the
    two 2s played (2 of hearts) matches that suit; the other (2 of
    clubs) rides along on the shared rank, same as elsewhere in the
    engine.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.TWO, Suit.CLUBS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
        },
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=3,
        discard_pile=(Card(Rank.THREE, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.TWO, Suit.CLUBS),
        ),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.pending_draw_count == 7

    increase_events = [
        e for e in events if e.type == EventType.DRAW_STACK_INCREASED
    ]
    assert len(increase_events) == 1
    assert increase_events[0].payload["pending_draw_count"] == 7


def test_two_jacks_skip_two_players_ahead():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        hands={
            "a": (
                Card(Rank.JACK, Suit.HEARTS),
                Card(Rank.JACK, Suit.SPADES),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.JACK, Suit.HEARTS),
            Card(Rank.JACK, Suit.SPADES),
        ),
    )

    new_state, events = apply_move(state, action, rules)

    # a -> (skip 2) -> c is the one left holding the response
    assert new_state.pending_skip_player_id == "c"
    assert new_state.current_player.id == "c"
    assert new_state.phase == Phase.AWAITING_SKIP_RESPONSE

    skip_events = [e for e in events if e.type == EventType.SKIP_STARTED]
    assert len(skip_events) == 1
    assert skip_events[0].payload["skip_count"] == 2
    assert skip_events[0].payload["target_player_id"] == "c"


def test_two_kings_cancel_out_direction():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.KING, Suit.SPADES),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        direction=1,
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
        ),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.direction == 1  # unchanged: two flips cancel out

    reverse_events = [e for e in events if e.type == EventType.DIRECTION_REVERSED]
    assert len(reverse_events) == 1
    assert reverse_events[0].payload["direction"] == 1


def test_three_kings_nets_a_single_reverse():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        hands={
            "a": (
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.KING, Suit.SPADES),
                Card(Rank.KING, Suit.CLUBS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.FIVE, Suit.CLUBS),
            ),
            "b": tuple(),
            "c": tuple(),
        },
        direction=1,
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.KING, Suit.SPADES),
            Card(Rank.KING, Suit.CLUBS),
        ),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.direction == -1


def test_two_question_cards_ask_only_once():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.EIGHT, Suit.HEARTS),
                Card(Rank.EIGHT, Suit.SPADES),
                Card(Rank.FOUR, Suit.HEARTS),
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
            Card(Rank.EIGHT, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.SPADES),
        ),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_ANSWER
    assert new_state.current_player.id == "a"  # asker answers their own question

    question_events = [e for e in events if e.type == EventType.QUESTION_ASKED]
    assert len(question_events) == 1
    assert question_events[0].payload["card_count"] == 2


# ---------------------------------------------------------------------
# Mixed-suit same-rank plays
#
# Legality for a same-rank group was only ever checked against
# cards[0] — so a group like (5 of spades, 5 of hearts) on a hearts
# pile was legal or not purely by luck of which one happened to be
# listed first in the action, even though the group as a whole is
# obviously playable (the 5 of hearts alone would be). These tests
# pin the fix: order within the group must not matter.
# ---------------------------------------------------------------------


def test_multi_card_play_legal_regardless_of_which_card_is_listed_first():
    rules = RuleConfig()

    # Top card is 7 of hearts: required suit is hearts, and neither 5
    # matches that top card's rank — the only reason this play is
    # legal at all is that ONE of the two 5s is a heart.
    state = make_state(
        hands={
            "a": (
                Card(Rank.FIVE, Suit.SPADES),  # doesn't match hearts
                Card(Rank.FIVE, Suit.HEARTS),  # does
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    # The non-matching suit listed first used to get this wrongly
    # rejected, even though the pair as a whole is legal.
    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.FIVE, Suit.SPADES),
            Card(Rank.FIVE, Suit.HEARTS),
        ),
    )

    new_state, _events = apply_move(state, action, rules)

    assert len(new_state.hand_of("a")) == 2
    assert new_state.current_player.id == "b"


def test_multi_card_play_still_illegal_when_no_card_in_the_group_matches():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.FIVE, Suit.SPADES),
                Card(Rank.FIVE, Suit.CLUBS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        # Required suit is hearts; neither 5 is a heart and neither
        # matches the top card's rank (7) — genuinely not playable.
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.FIVE, Suit.SPADES),
            Card(Rank.FIVE, Suit.CLUBS),
        ),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_multi_card_play_legal_via_shared_rank_regardless_of_suits():
    rules = RuleConfig()

    # Top card is 5 of diamonds: the shared rank (5) matches, so both
    # cards ride along regardless of suit — neither is a diamond.
    state = make_state(
        hands={
            "a": (
                Card(Rank.FIVE, Suit.SPADES),
                Card(Rank.FIVE, Suit.CLUBS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.FIVE, Suit.DIAMONDS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.FIVE, Suit.SPADES),
            Card(Rank.FIVE, Suit.CLUBS),
        ),
    )

    new_state, _events = apply_move(state, action, rules)

    assert len(new_state.hand_of("a")) == 2
    assert new_state.current_player.id == "b"


def test_question_answer_legal_regardless_of_which_card_is_listed_first():
    """
    Same anti-pattern, same fix, for answering a question — the
    required-suit check only looked at cards[0] there too.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.FOUR, Suit.SPADES),  # doesn't follow hearts
                Card(Rank.FOUR, Suit.HEARTS),  # does
                Card(Rank.SIX, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="a",
        discard_pile=(Card(Rank.EIGHT, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(
            Card(Rank.FOUR, Suit.SPADES),
            Card(Rank.FOUR, Suit.HEARTS),
        ),
        # Leaves "a" with 1 card (a finishable 6), so this must be
        # declared — not what this test is about, just satisfying it.
        declare_niko_kadi=True,
    )

    new_state, events = apply_move(state, action, rules)

    assert len(new_state.hand_of("a")) == 1
    answered = [e for e in events if e.type == EventType.QUESTION_ANSWERED]
    assert len(answered) == 1
