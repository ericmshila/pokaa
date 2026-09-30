"""
Ace rule wiring.

RuleConfig exposes several ace-related toggles. These tests confirm the
engine actually enforces them (as opposed to the flag existing but being
silently ignored).
"""

import pytest
from dataclasses import replace

from app.rules.actions import ActionType, PlayCardsAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import IllegalMove, apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_ace_cannot_answer_question_by_default():
    rules = RuleConfig()
    assert rules.ace_can_answer_question is False

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="b",
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.ACE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.HEARTS),),
        declared_suit=Suit.HEARTS,
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_ace_can_answer_question_when_enabled_but_cannot_declare_a_suit():
    """
    Answering a question with an Ace is reactive (getting out of an
    obligation), not the offensive normal-turn play — so unlike
    playing an Ace on your own turn, it does NOT also grant the
    "declare the next suit" power. Any declared_suit sent along with
    it is simply ignored.
    """

    rules = replace(RuleConfig(), ace_can_answer_question=True)

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="b",
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.ACE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.HEARTS),),
        declared_suit=Suit.HEARTS,  # ignored — Ace is countering, not opening
        declare_niko_kadi=True,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_MOVE
    assert new_state.active_suit is None
    assert not any(e.type == EventType.SUIT_DECLARED for e in events)
    assert any(e.type == EventType.ACE_COUNTER_PLAYED for e in events)


def test_ace_as_last_card_wins_by_default():
    # An Ace can win the game like any other card by default. See
    # tests/test_rules_engine.py for the twin of this test and
    # tests/test_finish_rules.py for the module-level explanation.
    rules = RuleConfig()
    assert rules.ace_can_finish is True

    state = make_state(
        hands={
            "a": (Card(Rank.ACE, Suit.SPADES),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.SPADES),),
        declared_suit=Suit.CLUBS,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"
    assert any(e.type == EventType.PLAYER_WON for e in events)


def test_ace_does_not_finish_when_explicitly_disabled():
    rules = replace(RuleConfig(), ace_can_finish=False)

    state = make_state(
        hands={
            "a": (Card(Rank.ACE, Suit.SPADES),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.SPADES),),
        declared_suit=Suit.CLUBS,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase != Phase.FINISHED
    assert new_state.winner_id is None
    assert new_state.hand_of("a") == ()
    assert new_state.active_suit == Suit.CLUBS
    assert not any(e.type == EventType.PLAYER_WON for e in events)
