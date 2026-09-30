import pytest

from app.rules.actions import (
    ActionType,
    DrawAction,
    PassAction,
    PlayCardsAction,
)
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import (
    IllegalMove,
    apply_move,
    create_initial_state,
)
from app.rules.events import EventType
from app.rules.state import GameState, Phase, Player


def make_players(count: int = 2):
    names = ["a", "b", "c", "d"]

    return tuple(
        Player(id=names[i], name=names[i].upper())
        for i in range(count)
    )


def make_state(
    *,
    player_count: int = 2,
    current_player_index: int = 0,
    hands: dict[str, tuple[Card, ...]] | None = None,
    draw_pile: tuple[Card, ...] | None = None,
    discard_pile: tuple[Card, ...] | None = None,
    direction: int = 1,
    phase: Phase = Phase.AWAITING_MOVE,
    pending_draw_count: int = 0,
    active_suit: Suit | None = None,
    pending_question_player_id: str | None = None,
    pending_skip_player_id: str | None = None,
    eliminated_player_ids: frozenset[str] | None = None,
) -> GameState:
    players = make_players(player_count)

    if hands is None:
        hands = {player.id: tuple() for player in players}

    if draw_pile is None:
        draw_pile = (
            Card(Rank.FOUR, Suit.SPADES),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.SIX, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.NINE, Suit.SPADES),
            Card(Rank.TEN, Suit.CLUBS),
        )

    if discard_pile is None:
        discard_pile = (Card(Rank.SEVEN, Suit.HEARTS),)

    return GameState(
        players=players,
        hands=hands,
        draw_pile=draw_pile,
        discard_pile=discard_pile,
        current_player_index=current_player_index,
        direction=direction,
        phase=phase,
        pending_draw_count=pending_draw_count,
        active_suit=active_suit,
        pending_question_player_id=pending_question_player_id,
        pending_skip_player_id=pending_skip_player_id,
        eliminated_player_ids=eliminated_player_ids or frozenset(),
    )


def test_create_initial_state_deals_correct_hand_size():
    rules = RuleConfig()
    players = list(make_players(4))
    state, events = create_initial_state(
        players=players,
        rules=rules,
        seed=1,
    )

    assert len(state.players) == 4

    for player in state.players:
        assert len(state.hand_of(player.id)) == rules.initial_hand_size

    assert state.phase == Phase.AWAITING_MOVE
    assert len(state.discard_pile) == 1
    assert any(event.type == EventType.GAME_STARTED for event in events)


def test_cannot_play_out_of_turn():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.FIVE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
            "b": (
                Card(Rank.FIVE, Suit.CLUBS),
            ),
        }
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FIVE, Suit.CLUBS),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_card_must_match_suit_or_rank():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.NINE, Suit.CLUBS),
                Card(Rank.FOUR, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.NINE, Suit.CLUBS),),
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_normal_matching_suit_play_advances_turn():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.FIVE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FIVE, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)
    assert len(new_state.hand_of("a")) == 2
    assert new_state.current_player.id == "b"
    assert new_state.top_card == Card(Rank.FIVE, Suit.HEARTS)
    assert any(event.type == EventType.CARD_PLAYED for event in events)


def test_ace_requires_declared_suit():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
            "b": tuple(),
        }
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.SPADES),),
        declare_niko_kadi=True,
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_ace_sets_active_suit():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
            "b": tuple(),
        }
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.SPADES),),
        declared_suit=Suit.DIAMONDS,
        declare_niko_kadi=True,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.active_suit == Suit.DIAMONDS
    assert new_state.current_player.id == "b"
    assert any(event.type == EventType.SUIT_DECLARED for event in events)


def test_question_card_enters_awaiting_answer_phase():
    rules = RuleConfig()
    state = make_state(
        hands={
            "a": (
                Card(Rank.QUEEN, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
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

    # The player who asks the question must answer it themselves — the
    # turn stays with them, it does not pass to the next player.
    assert new_state.phase == Phase.AWAITING_ANSWER
    assert new_state.current_player.id == "a"
    assert new_state.pending_question_player_id == "a"
    assert any(event.type == EventType.QUESTION_ASKED for event in events)


def test_only_allowed_number_cards_can_answer_question():
    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="b",
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.FIVE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.SPADES),
            ),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FIVE, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_MOVE
    assert new_state.current_player.id == "a"
    assert any(event.type == EventType.QUESTION_ANSWERED for event in events)


def test_eight_cannot_answer_question_even_if_same_suit():
    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="b",
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.EIGHT, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.EIGHT, Suit.HEARTS),),
        declare_niko_kadi=True,
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_draw_card_creates_pending_draw_response():
    rules = RuleConfig()
    state = make_state(
        hands={
            "a": (
                Card(Rank.TWO, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.SPADES),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.TWO, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == 2
    assert new_state.current_player.id == "b"
    assert any(event.type == EventType.DRAW_STACK_STARTED for event in events)


def test_ace_counters_draw_punishment():
    """
    Countering draw pressure with an Ace is reactive, not the
    offensive normal-turn play — it clears the punishment but does
    NOT grant the "declare the next suit" power (any declared_suit
    sent along with it is ignored). Follow-up play instead falls back
    to the Ace's own printed suit, same as any other card would (see
    GameState.required_suit's discard-pile walk-back).
    """

    rules = RuleConfig()

    state = make_state(
        current_player_index=1,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=2,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.ACE, Suit.SPADES),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.ACE, Suit.SPADES),),
        declared_suit=Suit.CLUBS,  # ignored — Ace is countering, not opening
        declare_niko_kadi=True,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_MOVE
    assert new_state.pending_draw_count == 0
    assert new_state.active_suit is None
    assert new_state.top_card == Card(Rank.ACE, Suit.SPADES)
    assert any(event.type == EventType.PUNISHMENT_CLEARED for event in events)
    assert not any(event.type == EventType.SUIT_DECLARED for event in events)


def test_jack_starts_skip_response():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
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
    assert new_state.current_player.id == "b"
    assert new_state.pending_skip_player_id == "b"
    assert any(event.type == EventType.SKIP_STARTED for event in events)


def test_pass_accepts_jack_skip():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=1,
        phase=Phase.AWAITING_SKIP_RESPONSE,
        pending_skip_player_id="b",
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.FOUR, Suit.CLUBS),
            ),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.JACK, Suit.HEARTS),),
    )

    action = PassAction(
        player_id="b",
        type=ActionType.PASS,
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_MOVE
    assert new_state.current_player.id == "c"
    assert new_state.pending_skip_player_id is None
    assert any(event.type == EventType.PLAYER_SKIPPED for event in events)


def test_king_reverses_direction():
    rules = RuleConfig()

    state = make_state(
        player_count=4,
        current_player_index=1,
        hands={
            "a": tuple(),
            "b": (
                Card(Rank.KING, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
                Card(Rank.SIX, Suit.SPADES),
            ),
            "c": tuple(),
            "d": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
        direction=1,
    )

    action = PlayCardsAction(
        player_id="b",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.KING, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.direction == -1
    assert new_state.current_player.id == "a"
    assert any(event.type == EventType.DIRECTION_REVERSED for event in events)


def test_niko_kadi_required_when_going_down_to_one_card():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.FIVE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.CLUBS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FIVE, Suit.HEARTS),),
        declare_niko_kadi=False,
    )

    with pytest.raises(IllegalMove):
        apply_move(state, action, rules)


def test_can_finish_on_plain_card():
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.FIVE, Suit.HEARTS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.FIVE, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"
    assert any(event.type == EventType.PLAYER_WON for event in events)


def test_ace_as_last_card_wins_by_default():
    # Any card, including an Ace, wins the game outright by default
    # when it empties the player's hand (see
    # RuleConfig.finishable_ranks/ace_can_finish). See
    # tests/test_ace_rules.py for the explicitly-disabled variant and
    # tests/test_finish_rules.py for the module-level explanation.
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.ACE, Suit.SPADES),
            ),
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
    assert any(event.type == EventType.PLAYER_WON for event in events)


def test_jack_as_last_card_wins_by_default():
    # Jack is a power card (skip), but it's still in finishable_ranks
    # by default — same story as the Ace above. See
    # tests/test_finish_rules.py for the explicitly-disabled variant.
    rules = RuleConfig()

    state = make_state(
        hands={
            "a": (
                Card(Rank.JACK, Suit.HEARTS),
            ),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = PlayCardsAction(
        player_id="a",
        type=ActionType.PLAY_CARDS,
        cards=(Card(Rank.JACK, Suit.HEARTS),),
    )

    new_state, events = apply_move(state, action, rules)

    # Winning short-circuits before the Jack's own skip effect would
    # otherwise land on "b" — the round is over, so there's no "next
    # player" left to skip.
    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "a"
    assert new_state.hand_of("a") == ()
    assert any(event.type == EventType.PLAYER_WON for event in events)