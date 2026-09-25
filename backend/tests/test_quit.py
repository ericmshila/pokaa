"""
Voluntary mid-game quit.

A player can leave an in-progress game at any time — not just on
their own turn — without needing to restart the server or wait for
the game to end naturally. Mechanically this reuses the same
"shuffle the hand back into the draw pile, mark the seat eliminated,
skip them in turn order, auto-conclude if one player remains" logic
as the punishment-forfeit rule (see test_forfeit.py), but is
triggered voluntarily via QuitAction and emits PLAYER_LEFT instead of
PLAYER_ELIMINATED so the UI can tell the two apart.
"""

from app.rules.actions import ActionType, QuitAction
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig
from app.rules.engine import IllegalMove, apply_move
from app.rules.events import EventType
from app.rules.state import Phase

from tests.test_rules_engine import make_state


def test_quit_on_own_turn_advances_to_next_active_player():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=1,
        phase=Phase.AWAITING_MOVE,
        hands={
            "a": tuple(),
            "b": (Card(Rank.FOUR, Suit.CLUBS), Card(Rank.FIVE, Suit.HEARTS)),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = QuitAction(player_id="b", type=ActionType.QUIT)
    new_state, events = apply_move(state, action, rules)

    assert "b" in new_state.eliminated_player_ids
    assert new_state.hand_of("b") == tuple()
    # b's hand (2 cards) goes back into the draw pile.
    assert len(new_state.draw_pile) == len(state.draw_pile) + 2
    assert new_state.current_player.id == "c"
    assert new_state.phase == Phase.AWAITING_MOVE
    assert any(
        event.type == EventType.PLAYER_LEFT
        and event.payload == {"player_id": "b", "hand_size": 2}
        for event in events
    )
    assert not any(event.type == EventType.PLAYER_ELIMINATED for event in events)


def test_quit_when_not_your_turn_does_not_change_turn_or_phase():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=0,
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=4,
        hands={
            "a": (Card(Rank.TWO, Suit.CLUBS),),
            "b": (Card(Rank.FOUR, Suit.CLUBS), Card(Rank.FIVE, Suit.HEARTS)),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.TWO, Suit.HEARTS),),
    )

    # It's a's turn (current_player_index=0); c quits instead.
    action = QuitAction(player_id="c", type=ActionType.QUIT)
    new_state, events = apply_move(state, action, rules)

    assert "c" in new_state.eliminated_player_ids
    assert new_state.current_player.id == "a"
    # a's pending draw-response obligation is untouched by an
    # unrelated player quitting.
    assert new_state.phase == Phase.AWAITING_DRAW_RESPONSE
    assert new_state.pending_draw_count == 4
    assert any(event.type == EventType.PLAYER_LEFT for event in events)
    assert not any(event.type == EventType.TURN_ADVANCED for event in events)


def test_quit_clears_pending_answer_obligation_when_current_player_quits():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=1,
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id="b",
        hands={
            "a": tuple(),
            "b": (Card(Rank.FOUR, Suit.CLUBS),),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.QUEEN, Suit.HEARTS),),
    )

    action = QuitAction(player_id="b", type=ActionType.QUIT)
    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.AWAITING_MOVE
    assert new_state.pending_question_player_id is None
    assert new_state.current_player.id == "c"


def test_quit_down_to_last_player_ends_the_game():
    rules = RuleConfig()

    state = make_state(
        player_count=2,
        current_player_index=0,
        phase=Phase.AWAITING_MOVE,
        hands={
            "a": (Card(Rank.FOUR, Suit.CLUBS),),
            "b": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = QuitAction(player_id="a", type=ActionType.QUIT)
    new_state, events = apply_move(state, action, rules)

    assert new_state.phase == Phase.FINISHED
    assert new_state.winner_id == "b"
    assert "a" in new_state.eliminated_player_ids
    assert any(event.type == EventType.PLAYER_LEFT for event in events)
    assert any(event.type == EventType.PLAYER_WON for event in events)
    assert any(event.type == EventType.GAME_FINISHED for event in events)


def test_quit_on_finished_game_is_illegal():
    rules = RuleConfig()

    state = make_state(
        player_count=2,
        phase=Phase.FINISHED,
        hands={"a": tuple(), "b": tuple()},
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )
    state = state.replace(winner_id="a")

    action = QuitAction(player_id="b", type=ActionType.QUIT)

    try:
        apply_move(state, action, rules)
        assert False, "expected IllegalMove"
    except IllegalMove:
        pass


def test_quit_twice_by_the_same_player_is_illegal():
    rules = RuleConfig()

    state = make_state(
        player_count=3,
        current_player_index=0,
        phase=Phase.AWAITING_MOVE,
        eliminated_player_ids=frozenset({"b"}),
        hands={
            "a": (Card(Rank.FOUR, Suit.CLUBS),),
            "b": tuple(),
            "c": tuple(),
        },
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = QuitAction(player_id="b", type=ActionType.QUIT)

    try:
        apply_move(state, action, rules)
        assert False, "expected IllegalMove"
    except IllegalMove:
        pass


def test_unknown_player_cannot_quit():
    rules = RuleConfig()

    state = make_state(
        player_count=2,
        hands={"a": tuple(), "b": tuple()},
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    action = QuitAction(player_id="ghost", type=ActionType.QUIT)

    try:
        apply_move(state, action, rules)
        assert False, "expected IllegalMove"
    except IllegalMove:
        pass
