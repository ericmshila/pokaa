"""
Finishing rule wiring.

Traditional, simpler Kadi: ANY legal card empties your hand and wins
the game outright, including every power card — Ace, 2, 3, 8, Jack,
Queen, King, Joker. `finishable_ranks` covers the plain ranks plus 2,
3, 8, Jack, Queen, King; Ace and Joker have their own
`ace_can_finish`/`joker_can_finish` toggles (also on by default) since
they're handled specially elsewhere in the engine.

This project briefly used a stricter variant (only 4/5/6/7/9/10 could
win, every power card excluded) but reverted it — see this file's git
history / test_niko_kadi_finishability.py's module docstring for why:
it made "Niko Kadi" a lie half the time, since a player could declare
it while holding a lone card that could never actually win. The
stricter shape is still fully supported by the engine — it's just no
longer the default — and the "_when_restricted" tests below exercise
it by explicitly overriding finishable_ranks/ace_can_finish/
joker_can_finish rather than relying on RuleConfig()'s defaults.

Either way, this is purely a WINNING rule, not a playability one:
every card is always a legal play, including as a player's very last
one — a lone Joker can still be dropped on the next player as a
punishment (it could well stop THEM from winning), a lone Ace can
still declare a suit, and so on. Under a ruleset where that rank can't
finish, the only difference from playing it with cards left in hand is
that the player is now cardless rather than out of the game; the round
continues, and they draw back in on their next turn like anyone else
with an empty hand would. Whether a player may even be LEFT holding
one of these as their only card in the first place, under such a
ruleset, is a separate, further question — see
test_niko_kadi_finishability.py for that (allowed by default via
restrict_lone_card_to_finishable=False).
"""

from dataclasses import replace

from app.rules.actions import ActionType, PlayCardsAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_joker_as_last_card_wins_by_default():
    rules = RuleConfig()
    assert rules.joker_can_finish is True

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

    # Winning short-circuits before the Joker's own punishment effect
    # would otherwise land on "b" — the round is over, so there's no
    # "next player" left to punish.
    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"
    assert any(event.type == EventType.PLAYER_WON for event in events)


def test_joker_as_last_card_does_not_win_when_explicitly_disabled():
    rules = replace(RuleConfig(), joker_can_finish=False)

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
    # makes always-playable worth having, once winning is turned off
    # for this rank.
    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == rules.draw_ranks[Rank.JOKER]
    assert new_state.winner_id is None
    assert new_state.hand_of("a") == ()
    assert not any(event.type == EventType.PLAYER_WON for event in events)


def test_question_card_as_last_card_wins_by_default():
    """
    8 is a question rank — but since it's a legal play and it empties
    the hand, it wins outright by default, same as any other card. The
    question is never actually asked: winning is decided before the
    engine would otherwise move to AWAITING_ANSWER, since there's no
    one left to answer to once the round is over.
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

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"
    assert any(event.type == EventType.PLAYER_WON for event in events)


def test_question_card_as_last_card_does_not_win_when_explicitly_disabled():
    """
    With 8 explicitly carved out of finishable_ranks, playing it as
    the last card empties the hand without winning — the asker stays
    "current" (they must still answer, or draw if they can't) despite
    now holding zero cards.
    """

    rules = replace(
        RuleConfig(),
        finishable_ranks=RuleConfig().finishable_ranks - {Rank.EIGHT},
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

    assert new_state.phase == Phase.AWAITING_ANSWER
    assert new_state.pending_question_player_id == "a"
    assert new_state.winner_id is None
    assert new_state.hand_of("a") == ()
    assert new_state.current_player.id == "a"
    assert not any(event.type == EventType.PLAYER_WON for event in events)


def test_can_finish_by_answering_a_question_with_your_last_card():
    """
    The scenario that motivated reverting to "any card wins": ask a
    question with a non-final card, then answer it with your actual
    last card. That answer is a completely separate, later play (see
    _commit_play_cards being reused for AWAITING_ANSWER), so it's
    judged as its own last-card play — and under the default ruleset,
    any legal answer wins, including a punishment rank like 2 or 3.
    """

    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (Card(Rank.EIGHT, Suit.HEARTS), Card(Rank.TWO, Suit.HEARTS)),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    ask = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.EIGHT, Suit.HEARTS),),
        declare_niko_kadi=True,
    )
    state_after_ask, _ = apply_move(state, ask, rules)
    assert state_after_ask.phase == Phase.AWAITING_ANSWER

    answer = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.TWO, Suit.HEARTS),),
    )
    state_after_answer, events = apply_move(state_after_ask, answer, rules)

    assert state_after_answer.phase == Phase.FINISHED
    assert state_after_answer.winner_id == "a"
    assert any(event.type == EventType.PLAYER_WON for event in events)


def test_can_finish_on_a_power_card_when_explicitly_enabled():
    """Regression guard: a ruleset can still narrow finishable_ranks
    right down to nothing but plain numbers, the way this project's
    earlier, stricter variant did, and re-widening just one rank back
    in (here, 8) still works as a targeted override."""

    rules = replace(
        RuleConfig(),
        finishable_ranks={
            Rank.FOUR,
            Rank.FIVE,
            Rank.SIX,
            Rank.SEVEN,
            Rank.EIGHT,
            Rank.NINE,
            Rank.TEN,
        },
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
