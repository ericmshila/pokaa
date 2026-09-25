"""
Question card (8 / Q) rules.

House rule for this game: the player who plays a question card must
answer it themselves. The turn does NOT pass to the next player —
they stay the current player and must immediately follow up with a
valid answer card, or draw if they have none.
"""

import pytest

from app.rules.actions import ActionType, DrawAction, PlayCardsAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import IllegalMove, apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_asker_stays_current_player_after_question_card():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.QUEEN, Suit.HEARTS),
                Card(Rank.FOUR, Suit.HEARTS),
                Card(Rank.SIX, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_ANSWER
    assert new_state.current_player.id == "a"
    assert new_state.pending_question_player_id == "a"
    assert any(
        event.type == EventType.QUESTION_ASKED
        and event.payload["target_player_id"] == "a"
        for event in events
    )


def test_other_player_cannot_act_while_question_is_pending():
    rules = RuleConfig()

    state = make_state(
        current_player_index=0,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="a",
        hands={
            "a": (Card(Rank.FOUR, Suit.HEARTS),),
            "b": (Card(Rank.FIVE, Suit.CLUBS),),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FIVE, Suit.CLUBS),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_asker_answers_own_question_then_turn_passes():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=0,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="a",
        hands={
            "a": (
                Card(Rank.FOUR, Suit.HEARTS),
                Card(Rank.SIX, Suit.SPADES),
                Card(Rank.NINE, Suit.CLUBS),
            ),
            "b": tuple(),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FOUR, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_MOVE
    assert new_state.pending_question_player_id is None
    # Only now, after the asker has answered, does the turn move on.
    assert new_state.current_player.id == "b"
    assert any(event.type == EventType.QUESTION_ANSWERED for event in events)


def test_asker_must_draw_when_unable_to_answer():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=0,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="a",
        hands={
            # Off-suit, so it cannot answer a Hearts question.
            "a": (Card(Rank.FIVE, Suit.SPADES),),
            "b": tuple(),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    bad_answer = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FIVE, Suit.SPADES),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, bad_answer, rules)

    draw_action = DrawAction(player_id="a", type=ActionType.DRAW)
    new_state, events = apply_move(state, draw_action, rules)

    assert new_state.phase == Phase.AWAITING_MOVE
    assert new_state.pending_question_player_id is None
    assert len(new_state.hand_of("a")) == 2
    # Drawing instead of answering still ends the asker's turn.
    assert new_state.current_player.id == "b"
    assert any(event.type == EventType.CARDS_DRAWN for event in events)
