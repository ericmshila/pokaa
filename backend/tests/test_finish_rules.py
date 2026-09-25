"""
Finishing rule wiring.

Traditional Kadi: only a plain, effect-free rank can literally WIN
the game. Every power card — Ace, 2, 3, 8, Jack, Queen, King, Joker —
is excluded from `finishable_ranks` (or gated by its own
`ace_can_finish`/`joker_can_finish` toggle) by default, so playing one
as your very last card never wins the game outright.

This is purely a WINNING rule, not a playability one: every card is
always a legal play, including as a player's very last one — a lone
Joker can still be dropped on the next player as a punishment (it
could well stop THEM from winning), a lone Ace can still declare a
suit, and so on. The only difference from playing it with cards left
in hand is that the player is now cardless rather than out of the
game; the round continues, and they draw back in on their next turn
like anyone else with an empty hand would.

Whether a player may be LEFT holding one of these as their only card
in the first place is a separate, further question — see
test_niko_kadi_finishability.py for that (allowed by default; a
player can freely play their way down to a lone power card, they just
can't WIN the game by playing it).
"""

from dataclasses import replace

from app.rules.actions import ActionType, PlayCardsAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_joker_as_last_card_empties_hand_without_winning_by_default():
    rules = RuleConfig()
    assert rules.joker_can_finish is False

    state = make_state(
        hands={
            "a": (Card(Rank.JOKER, None),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JOKER, None),),
        declared_suit=Suit.CLUBS,
    )

    new_state, events = apply_move(state, action, rules)

    # The Joker's own punishment effect still lands on "b" — this is
    # exactly the "stop someone else from winning" use case that
    # makes always-playable worth having.
    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == rules.draw_ranks[Rank.JOKER]
    assert new_state.winner_id is None
    assert new_state.hand_of("a") == ()
    assert not any(event.type == EventType.PLAYER_WON for event in events)


def test_can_finish_on_joker_when_explicitly_enabled():
    rules = replace(RuleConfig(), joker_can_finish=True)

    state = make_state(
        hands={
            "a": (Card(Rank.JOKER, None),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JOKER, None),),
        declared_suit=Suit.CLUBS,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"


def test_question_card_as_last_card_empties_hand_without_winning_by_default():
    """
    8 is a question rank (a power card) — it can never be the literal
    winning play by default, but it's still always playable, even as
    the last card in hand. The asking player stays "current" (they
    must still answer) despite now holding zero cards — their next
    move is necessarily a draw, same as anyone else in that spot.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (Card(Rank.EIGHT, Suit.HEARTS),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.EIGHT, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_ANSWER
    assert new_state.pending_question_player_id == "a"
    assert new_state.winner_id is None
    assert new_state.hand_of("a") == ()
    assert new_state.current_player.id == "a"
    assert not any(event.type == EventType.PLAYER_WON for event in events)


def test_can_finish_on_a_power_card_when_explicitly_enabled():
    rules = replace(
        RuleConfig(),
        finishable_ranks=RuleConfig().finishable_ranks | {Rank.EIGHT},
    )

    state = make_state(
        hands={
            "a": (Card(Rank.EIGHT, Suit.HEARTS),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.EIGHT, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"


def test_can_finish_on_a_plain_rank_by_default():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (Card(Rank.NINE, Suit.HEARTS),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.NINE, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"
