"""
serialize_room_for_player's game-state fields that back frontend
UI features — required_suit, draw_pile_count, and each player's
has_declared_niko_kadi flag.
"""

from app.game.room import GameRoom
from app.game.serializers import serialize_room_for_player
from app.rules.cards import Card, Rank, Suit
from app.rules.config import RuleConfig

from tests.test_rules_engine import make_state


def _room_with_state(state):
    room = GameRoom(room_id="r1", rules=RuleConfig())
    room.players = list(state.players)
    room.started = True
    room.state = state
    return room


def test_required_suit_falls_back_to_top_card_suit():
    state = make_state(
        hands={"a": tuple(), "b": tuple()},
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    payload = serialize_room_for_player(_room_with_state(state), "a")

    assert payload["state"]["required_suit"] == "hearts"


def test_required_suit_uses_active_suit_when_set():
    state = make_state(
        hands={"a": tuple(), "b": tuple()},
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
        active_suit=Suit.CLUBS,
    )

    payload = serialize_room_for_player(_room_with_state(state), "a")

    assert payload["state"]["required_suit"] == "clubs"


def test_required_suit_walks_back_under_a_colourless_joker():
    state = make_state(
        hands={"a": tuple(), "b": tuple()},
        discard_pile=(
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.JOKER, None),
        ),
    )

    payload = serialize_room_for_player(_room_with_state(state), "a")

    assert payload["state"]["top_card"]["rank"] == "JOKER"
    assert payload["state"]["required_suit"] == "hearts"


def test_draw_pile_count_is_exposed():
    draw_pile = (
        Card(Rank.FOUR, Suit.SPADES),
        Card(Rank.FIVE, Suit.CLUBS),
        Card(Rank.SIX, Suit.DIAMONDS),
    )
    state = make_state(
        hands={"a": tuple(), "b": tuple()},
        draw_pile=draw_pile,
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )

    payload = serialize_room_for_player(_room_with_state(state), "a")

    assert payload["state"]["draw_pile_count"] == len(draw_pile)


def test_has_declared_niko_kadi_reflects_state():
    state = make_state(
        hands={"a": (Card(Rank.FOUR, Suit.SPADES),), "b": tuple()},
        discard_pile=(Card(Rank.SEVEN, Suit.HEARTS),),
    )
    state = state.replace(niko_kadi_declared_by=frozenset({"a"}))

    payload = serialize_room_for_player(_room_with_state(state), "a")

    players_by_id = {p["id"]: p for p in payload["state"]["players"]}
    assert players_by_id["a"]["has_declared_niko_kadi"] is True
    assert players_by_id["b"]["has_declared_niko_kadi"] is False
