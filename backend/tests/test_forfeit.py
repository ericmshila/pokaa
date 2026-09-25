"""
Forfeit rule.

House rule: a player who is forced to draw an unavoidable punishment
stack (a 2/3 draw chain they had no counter or restack for) and ends
up holding `rules.forfeit_hand_size` cards or more is eliminated. Their
hand is shuffled back into the draw pile, and if only one player is
left standing, the game ends immediately with them as the winner.

This does NOT apply to voluntary draws or draws made because a player
couldn't answer a question — only to punishment draw responses.
"""

from dataclasses import replace

from app.rules.actions import ActionType, DrawAction, PlayCardsAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def _hand_of_size(n: int, suit: Suit = Suit.CLUBS) -> tuple[Card, ...]:
    ranks = [Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN, Rank.NINE, Rank.TEN]
    return tuple(Card(ranks[i % len(ranks)], suit) for i in range(n))


def test_punishment_draw_past_threshold_eliminates_player():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": tuple(),
            "b": _hand_of_size(11),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    action = DrawAction(player_id="b", type=ActionType.DRAW)
    new_state, events = apply_move(state, action, rules)

    assert "b" in new_state.eliminated_player_ids
    assert new_state.hand_of("b") == tuple()
    # b's forfeited hand (13 cards) goes back into the draw pile.
    assert len(new_state.draw_pile) == len(state.draw_pile) - 2 + 13
    assert any(
        event.type == EventType.PLAYER_ELIMINATED
        and event.payload == {"player_id": "b", "hand_size": 13}
        for event in events
    )
    # Turn skips the now-eliminated b and moves straight to c.
    assert new_state.current_player.id == "c"
    assert new_state.phase == Phase.AWAITING_MOVE


def test_forfeit_disabled_when_threshold_is_none():
    rules = replace(RuleConfig(), forfeit_hand_size=None)

    state = make_state(
        player_count=3,
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": tuple(),
            "b": _hand_of_size(8),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    action = DrawAction(player_id="b", type=ActionType.DRAW)
    new_state, events = apply_move(state, action, rules)

    assert new_state.eliminated_player_ids == frozenset()
    assert len(new_state.hand_of("b")) == 10
    assert not any(event.type == EventType.PLAYER_ELIMINATED for event in events)


def test_voluntary_draw_past_threshold_does_not_eliminate():
    rules = RuleConfig()

    state = make_state(
        phase=Phase.AWAITING_MOVE,
        hands={
            "a": _hand_of_size(13),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = DrawAction(player_id="a", type=ActionType.DRAW)
    new_state, events = apply_move(state, action, rules)

    assert len(new_state.hand_of("a")) == 14
    assert new_state.eliminated_player_ids == frozenset()
    assert not any(event.type == EventType.PLAYER_ELIMINATED for event in events)


def test_question_draw_past_threshold_does_not_eliminate():
    rules = RuleConfig()

    state = make_state(
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="a",
        hands={
            "a": _hand_of_size(13),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = DrawAction(player_id="a", type=ActionType.DRAW)
    new_state, events = apply_move(state, action, rules)

    assert len(new_state.hand_of("a")) == 14
    assert new_state.eliminated_player_ids == frozenset()
    assert not any(event.type == EventType.PLAYER_ELIMINATED for event in events)


def test_forfeit_down_to_last_player_ends_the_game():
    rules = RuleConfig()

    state = make_state(
        player_count=2,
        current_player_index=0,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": _hand_of_size(11),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    action = DrawAction(player_id="a", type=ActionType.DRAW)
    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "b"
    assert "a" in new_state.eliminated_player_ids
    assert any(event.type == EventType.PLAYER_WON for event in events)
    assert any(event.type == EventType.GAME_FINISHED for event in events)


def test_eliminated_player_is_skipped_as_a_skip_target():
    """
    A Jack should never target an already-eliminated player — the
    skip should jump over them to the next active player.
    """

    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=0,
        eliminated_player_ids=frozenset({"b"}),
        hands={
            "a": (
                Card(Rank.JACK, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.SPADES),
            ),
            "b": tuple(),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JACK, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_SKIP_RESPONSE
    assert new_state.pending_skip_player_id == "c"
    assert new_state.current_player.id == "c"
