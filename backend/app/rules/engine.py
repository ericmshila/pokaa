"""
Kenyan Poker / Kadi rules engine.

Pure game logic only.

No FastAPI.
No WebSockets.
No database.
No UI assumptions.

The engine answers:

- Is this action legal?
- What happens next?
- Who plays next?
- Has someone won?
"""

from __future__ import annotations

import random
from typing import Optional

from .actions import (
    ActionType,
    DrawAction,
    PassAction,
    PlayCardsAction,
    PlayerAction,
    QuitAction,
    SayNikoKadiAction,
)
from .cards import Card, Rank, shuffled_deck
from .config import RuleConfig
from .events import EventType, GameEvent
from .state import GameState, Phase, Player


class IllegalMove(Exception):
    """
    Raised when a player attempts an illegal move.
    """


# ---------------------------------------------------------------------
# Game setup
# ---------------------------------------------------------------------


def create_initial_state(
    players: list[Player],
    rules: Optional[RuleConfig] = None,
    seed: Optional[int] = None,
) -> tuple[GameState, list[GameEvent]]:
    """
    Create a new game state.

    The first discard is forced to be a plain card to avoid opening
    the game with unresolved draw/question/skip/reverse/wild effects.
    """

    rules = rules or RuleConfig()

    if len(players) < 2:
        raise ValueError("At least two players are required.")

    deck = shuffled_deck(seed=seed)
    draw_pile = list(deck)

    hands: dict[str, tuple[Card, ...]] = {}

    for player in players:
        hand: list[Card] = []

        for _ in range(rules.initial_hand_size):
            hand.append(draw_pile.pop())

        hands[player.id] = tuple(hand)

    first_discard = draw_pile.pop()

    while _is_opening_special_card(first_discard, rules):
        draw_pile.insert(0, first_discard)
        first_discard = draw_pile.pop()

    state = GameState(
        players=tuple(players),
        hands=hands,
        draw_pile=tuple(draw_pile),
        discard_pile=(first_discard,),
        current_player_index=0,
        direction=1,
        phase=Phase.AWAITING_MOVE,
    )

    events = [
        GameEvent(
            type=EventType.GAME_STARTED,
            payload={
                "players": [player.id for player in players],
                "top_card": first_discard.label(),
                "current_player_id": state.current_player.id,
            },
        )
    ]

    return state, events


# ---------------------------------------------------------------------
# Public transition function
# ---------------------------------------------------------------------


def apply_move(
    state: GameState,
    action: PlayerAction,
    rules: RuleConfig,
) -> tuple[GameState, list[GameEvent]]:
    """
    Apply one player action to the current state.

    Returns:
        new_state, events
    """

    if state.phase == Phase.FINISHED or state.winner_id is not None:
        raise IllegalMove("Game is already finished.")

    if isinstance(action, SayNikoKadiAction):
        return _apply_say_niko_kadi(state, action)

    if isinstance(action, QuitAction):
        return _apply_quit(state, action)

    if action.player_id != state.current_player.id:
        raise IllegalMove("It is not this player's turn.")

    if isinstance(action, PlayCardsAction):
        return _apply_play_cards(state, action, rules)

    if isinstance(action, DrawAction):
        return _apply_draw(state, action, rules)

    if isinstance(action, PassAction):
        return _apply_pass(state, action, rules)

    raise IllegalMove(f"Unsupported action type: {action.type}")


# ---------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------


def _apply_say_niko_kadi(
    state: GameState,
    action: SayNikoKadiAction,
) -> tuple[GameState, list[GameEvent]]:

    if action.player_id not in state.hands:
        raise IllegalMove("Unknown player.")

    if len(state.hand_of(action.player_id)) != 1:
        raise IllegalMove("Niko Kadi can only be declared when holding one card.")

    declared = set(state.niko_kadi_declared_by)
    declared.add(action.player_id)

    new_state = state.replace(
        niko_kadi_declared_by=frozenset(declared)
    )

    return new_state, [
        GameEvent(
            type=EventType.NIKO_KADI_DECLARED,
            payload={"player_id": action.player_id},
        )
    ]


def _apply_play_cards(
    state: GameState,
    action: PlayCardsAction,
    rules: RuleConfig,
) -> tuple[GameState, list[GameEvent]]:

    _validate_play_action_shape(state, action)

    card = action.cards[0]

    if state.phase == Phase.AWAITING_MOVE:
        _validate_normal_turn_play(state, action, rules)

    elif state.phase == Phase.AWAITING_ANSWER:
        _validate_question_response(state, action, rules)

    elif state.phase == Phase.AWAITING_DRAW_RESPONSE:
        _validate_draw_response(state, action, rules)

    elif state.phase == Phase.AWAITING_SKIP_RESPONSE:
        _validate_skip_response(state, action, rules)

    else:
        raise IllegalMove(f"Unsupported phase: {state.phase}")

    return _commit_play_cards(state, action, rules)


def _apply_draw(
    state: GameState,
    action: DrawAction,
    rules: RuleConfig,
) -> tuple[GameState, list[GameEvent]]:

    if state.phase == Phase.AWAITING_SKIP_RESPONSE:
        raise IllegalMove("Player must pass or counter the skip.")

    is_punishment_draw = state.phase == Phase.AWAITING_DRAW_RESPONSE

    if state.phase == Phase.AWAITING_DRAW_RESPONSE:
        draw_count = state.pending_draw_count

    elif state.phase == Phase.AWAITING_ANSWER:
        draw_count = 1

    elif state.phase == Phase.AWAITING_MOVE:
        draw_count = 1

    else:
        raise IllegalMove(f"Cannot draw during phase: {state.phase}")

    new_state, events = _draw_cards_for_player(
        state=state,
        player_id=action.player_id,
        count=draw_count,
    )

    new_state = new_state.replace(
        phase=Phase.AWAITING_MOVE,
        pending_draw_count=0,
        pending_question_player_id=None,
        pending_skip_player_id=None,
    )

    if (
        is_punishment_draw
        and rules.forfeit_hand_size is not None
        and len(new_state.hand_of(action.player_id)) >= rules.forfeit_hand_size
    ):
        new_state, forfeit_events = _forfeit_player(
            state=new_state,
            player_id=action.player_id,
        )
        events.extend(forfeit_events)

        if new_state.phase == Phase.FINISHED:
            return new_state, events

    new_state, turn_events = _advance_turn(new_state, steps=1)
    events.extend(turn_events)

    return new_state, events


def _apply_pass(
    state: GameState,
    action: PassAction,
    rules: RuleConfig,
) -> tuple[GameState, list[GameEvent]]:

    if state.phase != Phase.AWAITING_SKIP_RESPONSE:
        raise IllegalMove("Pass is only allowed when responding to a skip.")

    skipped_player_id = state.current_player.id

    events = [
        GameEvent(
            type=EventType.PLAYER_SKIPPED,
            payload={"player_id": skipped_player_id},
        )
    ]

    new_state = state.replace(
        phase=Phase.AWAITING_MOVE,
        pending_skip_player_id=None,
    )

    new_state, turn_events = _advance_turn(new_state, steps=1)
    events.extend(turn_events)

    return new_state, events


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def _validate_play_action_shape(
    state: GameState,
    action: PlayCardsAction,
) -> None:

    if not action.cards:
        raise IllegalMove("At least one card must be played.")

    hand = list(state.hand_of(action.player_id))

    for card in action.cards:
        if card not in hand:
            raise IllegalMove(f"Player does not have card: {card.label()}")
        hand.remove(card)

    if len(action.cards) > 1:
        first_rank = action.cards[0].rank

        for card in action.cards:
            if card.rank != first_rank:
                raise IllegalMove("Multi-card play requires cards of the same rank.")


def _validate_normal_turn_play(
    state: GameState,
    action: PlayCardsAction,
    rules: RuleConfig,
) -> None:

    card = action.cards[0]

    if _is_ace(card):
        _validate_declared_suit_for_ace(action, rules)
        return

    if _is_joker(card):
        # Always playable, like Ace — but no suit to declare; it
        # opens a draw-pressure punishment instead (see
        # _apply_card_effects / rules.draw_ranks).
        return

    if not _matches_required_suit_or_rank(state, action.cards):
        raise IllegalMove(
            f"{card.label()} cannot be played on {state.top_card.label()}."
        )


def _validate_question_response(
    state: GameState,
    action: PlayCardsAction,
    rules: RuleConfig,
) -> None:

    card = action.cards[0]

    if _is_ace(card) and rules.ace_can_answer_question:
        # Reactive, not offensive — an Ace played to get out of a
        # question doesn't also get to declare the next suit (see
        # _apply_ace_effect).
        return

    if _is_joker(card) and rules.joker_can_answer_question:
        return

    if card.rank not in rules.question_answer_ranks:
        raise IllegalMove("This card cannot answer a question.")

    required_suit = state.required_suit

    # All cards share a rank (enforced upstream), but not necessarily
    # a suit — any one of them following the required suit is enough
    # to legitimize answering with the whole same-rank group.
    if not any(played.suit == required_suit for played in action.cards):
        raise IllegalMove("Question answer must follow the required suit.")


def _validate_draw_response(
    state: GameState,
    action: PlayCardsAction,
    rules: RuleConfig,
) -> None:

    card = action.cards[0]

    if _is_ace(card) and rules.ace_counters_punishments:
        # Reactive, not offensive — an Ace played to counter draw
        # pressure doesn't also get to declare the next suit (see
        # _apply_ace_effect).
        return

    if not rules.draw_stacking_enabled:
        raise IllegalMove("Draw stacking is disabled. Player must draw.")

    if card.rank not in rules.draw_ranks:
        raise IllegalMove(
            "Only another draw card, Joker, or Ace can respond to draw pressure."
        )

    if _is_joker(state.top_card):
        if not _is_joker(card):
            # A plain 2/3 can only counter an active Joker if it matches
            # the Joker's colour (another Joker or an Ace always works,
            # handled above/below).
            required_color = _card_color(state.top_card)

            for played in action.cards:
                if _card_color(played) != required_color:
                    raise IllegalMove(
                        f"Only a {required_color} card (or another Joker, or "
                        "an Ace) can counter this Joker's draw pressure."
                    )

    elif not _is_joker(card):
        # Countering one suited draw card (2/3) with another follows
        # the same "same rank always works, otherwise match the suit"
        # rule as a normal turn play (see
        # _matches_required_suit_or_rank): a 3 counters a 3 (or a 2
        # counters a 2) regardless of suit — they're both draw cards
        # of the same rank, no suit relationship needed. But a 3
        # countering a 2 (or vice versa) does need to match its suit —
        # e.g. 3 of diamonds cancels 2 of diamonds, but 3 of diamonds
        # does NOT cancel 2 of hearts. A Joker can still counter
        # unconditionally (it has no suit of its own), same as before.
        if not _matches_required_suit_or_rank(state, action.cards):
            required_suit = state.required_suit
            raise IllegalMove(
                f"Only another {state.top_card.rank.value} (any suit), a "
                f"{required_suit.value} card, a Joker, or an Ace can "
                "counter this draw pressure."
            )


def _validate_skip_response(
    state: GameState,
    action: PlayCardsAction,
    rules: RuleConfig,
) -> None:

    if not rules.skip_can_be_countered:
        raise IllegalMove("Skip cannot be countered under the current rules.")

    card = action.cards[0]

    if _is_ace(card) and rules.ace_counters_punishments:
        # Reactive, not offensive — an Ace played to counter a skip
        # doesn't also get to declare the next suit (see
        # _apply_ace_effect).
        return

    if card.rank not in rules.skip_ranks:
        raise IllegalMove("Skip can only be countered by Jack or Ace.")


def _validate_declared_suit_for_ace(
    action: PlayCardsAction,
    rules: RuleConfig,
) -> None:

    if rules.ace_requires_declared_suit and action.declared_suit is None:
        raise IllegalMove("Playing Ace requires declaring the next suit.")


# ---------------------------------------------------------------------
# Commit play
# ---------------------------------------------------------------------


def _commit_play_cards(
    state: GameState,
    action: PlayCardsAction,
    rules: RuleConfig,
) -> tuple[GameState, list[GameEvent]]:

    player_id = action.player_id
    cards = action.cards
    first_card = cards[0]
    last_card = cards[-1]

    events: list[GameEvent] = []

    new_hand = _remove_cards_from_hand(
        hand=state.hand_of(player_id),
        cards=cards,
    )

    if rules.restrict_lone_card_to_finishable:
        _validate_can_reach_one_card(
            player_id=player_id,
            new_hand=new_hand,
            rules=rules,
        )

    new_hands = dict(state.hands)
    new_hands[player_id] = tuple(new_hand)

    new_discard_pile = tuple(list(state.discard_pile) + list(cards))

    declared = set(state.niko_kadi_declared_by)

    if action.declare_niko_kadi:
        declared.add(player_id)
        events.append(
            GameEvent(
                type=EventType.NIKO_KADI_DECLARED,
                payload={"player_id": player_id},
            )
        )

    _validate_niko_kadi(
        player_id=player_id,
        remaining_cards=len(new_hand),
        declared=declared,
        rules=rules,
    )

    for card in cards:
        events.append(
            GameEvent(
                type=EventType.CARD_PLAYED,
                payload={
                    "player_id": player_id,
                    "card": card.label(),
                },
            )
        )

    new_state = state.replace(
        hands=new_hands,
        discard_pile=new_discard_pile,
        niko_kadi_declared_by=frozenset(declared),
    )

    # Emptying your hand only wins the game if the card you emptied it
    # WITH is one the game can actually end on (see finishable_ranks/
    # ace_can_finish/joker_can_finish in config.py — every "power"
    # rank, plus Ace and Joker, is excluded by default). Any card is
    # always playable now, including as your very last one — a lone
    # Joker/2/3 can still be dropped on someone to stop them winning,
    # a lone Ace can still declare a suit, a lone 8/Q still asks a
    # question — but doing so leaves the player cardless rather than
    # winning outright; the round simply continues (their own next
    # "turn" with an empty hand just means they draw), and the
    # card's own effect below still applies normally to whoever's
    # next. Only a finishable last card ends the game right here.
    if len(new_hand) == 0 and _can_finish_with(last_card, rules):
        new_state = new_state.replace(
            phase=Phase.FINISHED,
            winner_id=player_id,
        )

        events.extend(
            [
                GameEvent(
                    type=EventType.PLAYER_WON,
                    payload={"player_id": player_id},
                ),
                GameEvent(
                    type=EventType.GAME_FINISHED,
                    payload={"winner_id": player_id},
                ),
            ]
        )

        return new_state, events

    return _apply_card_effects(
        state=new_state,
        played_cards=cards,
        action=action,
        rules=rules,
        events=events,
    )


# ---------------------------------------------------------------------
# Card effects
# ---------------------------------------------------------------------


def _apply_card_effects(
    state: GameState,
    played_cards: tuple[Card, ...],
    action: PlayCardsAction,
    rules: RuleConfig,
    events: list[GameEvent],
) -> tuple[GameState, list[GameEvent]]:
    """
    Dispatches on the rank shared by every card in ``played_cards``
    (multi-card plays are same-rank only, enforced upstream in
    ``_validate_play_action_shape``). Effect-bearing card types apply
    their effect once PER CARD played, not once for the whole move:
    two 2s stack +4 draw pressure, two Jacks skip two players ahead,
    two Kings reverse direction twice (net no-op), etc. Question cards
    are the one exception — asking is a single yes/no obligation
    regardless of how many question cards were dropped together.

    Joker is a punishment card, not a wild suit-changer (see
    RuleConfig.draw_ranks), so it falls into the same draw_ranks
    branch as 2s/3s below and stacks the same way. Ace is the only
    card that behaves differently as a punishment response — it
    clears the pending draw outright instead of adding to it — so it
    keeps its own dedicated branch.
    """

    player_id = action.player_id
    played_card = played_cards[0]

    if _is_ace(played_card):
        return _apply_ace_effect(state, action, events)

    if played_card.rank in rules.draw_ranks:
        return _apply_draw_card_effect(state, played_cards, rules, events)

    if played_card.rank in rules.question_ranks:
        return _apply_question_effect(state, played_cards, events)

    if played_card.rank in rules.skip_ranks:
        return _apply_skip_effect(state, played_cards, events)

    if played_card.rank in rules.reverse_ranks:
        return _apply_reverse_effect(state, played_cards, events)

    if state.phase == Phase.AWAITING_ANSWER:
        events.append(
            GameEvent(
                type=EventType.QUESTION_ANSWERED,
                payload={"player_id": player_id},
            )
        )

    new_state = state.replace(
        phase=Phase.AWAITING_MOVE,
        pending_draw_count=0,
        pending_question_player_id=None,
        pending_skip_player_id=None,
        active_suit=None,
    )

    new_state, turn_events = _advance_turn(new_state, steps=1)
    events.extend(turn_events)

    return new_state, events


def _apply_ace_effect(
    state: GameState,
    action: PlayCardsAction,
    events: list[GameEvent],
) -> tuple[GameState, list[GameEvent]]:
    """
    An Ace played on a normal turn is offensive: it's always playable
    and the player gets to declare the next suit.

    An Ace played to counter a pending question/draw/skip is
    reactive: it clears the obligation, but — unlike the offensive
    case — does NOT also grant the suit-declare power. Any
    declared_suit the client sends in that situation is ignored;
    active_suit is left unset, so normal play afterwards just follows
    the Ace's own printed suit (via GameState.required_suit's
    discard-pile walk-back), the same as any other card would.
    """

    player_id = action.player_id

    is_countering = state.phase in {
        Phase.AWAITING_ANSWER,
        Phase.AWAITING_DRAW_RESPONSE,
        Phase.AWAITING_SKIP_RESPONSE,
    }

    if is_countering:
        events.append(
            GameEvent(
                type=EventType.ACE_COUNTER_PLAYED,
                payload={"player_id": player_id},
            )
        )

        events.append(
            GameEvent(
                type=EventType.PUNISHMENT_CLEARED,
                payload={"player_id": player_id},
            )
        )

        declared_suit = None
    else:
        declared_suit = action.declared_suit

        events.append(
            GameEvent(
                type=EventType.SUIT_DECLARED,
                payload={
                    "player_id": player_id,
                    "suit": declared_suit.value if declared_suit else None,
                },
            )
        )

    new_state = state.replace(
        phase=Phase.AWAITING_MOVE,
        pending_draw_count=0,
        pending_question_player_id=None,
        pending_skip_player_id=None,
        active_suit=declared_suit,
    )

    new_state, turn_events = _advance_turn(new_state, steps=1)
    events.extend(turn_events)

    return new_state, events


def _apply_draw_card_effect(
    state: GameState,
    played_cards: tuple[Card, ...],
    rules: RuleConfig,
    events: list[GameEvent],
) -> tuple[GameState, list[GameEvent]]:

    added = sum(rules.draw_ranks[card.rank] for card in played_cards)
    pending_total = state.pending_draw_count + added

    new_state = state.replace(
        phase=Phase.AWAITING_DRAW_RESPONSE,
        pending_draw_count=pending_total,
        active_suit=None,
    )

    event_type = (
        EventType.DRAW_STACK_INCREASED
        if state.pending_draw_count > 0
        else EventType.DRAW_STACK_STARTED
    )

    events.append(
        GameEvent(
            type=event_type,
            payload={"pending_draw_count": pending_total},
        )
    )

    new_state, turn_events = _advance_turn(new_state, steps=1)
    events.extend(turn_events)

    return new_state, events


def _apply_question_effect(
    state: GameState,
    played_cards: tuple[Card, ...],
    events: list[GameEvent],
) -> tuple[GameState, list[GameEvent]]:
    """
    The player who plays a question card (8 or Q) must immediately
    answer it themselves — the turn does NOT pass to the next player.

    They stay the current player and must follow up with a valid
    answer card (or draw, if they have none) before their turn ends.
    Playing several question cards at once doesn't multiply this
    obligation — one valid answer still resolves it, however many
    question cards were dropped together.
    """

    asking_player = state.current_player

    new_state = state.replace(
        phase=Phase.AWAITING_ANSWER,
        pending_question_player_id=asking_player.id,
        active_suit=None,
    )

    events.append(
        GameEvent(
            type=EventType.QUESTION_ASKED,
            payload={
                "question_card": played_cards[0].label(),
                "target_player_id": asking_player.id,
                "card_count": len(played_cards),
            },
        )
    )

    return new_state, events


def _apply_skip_effect(
    state: GameState,
    played_cards: tuple[Card, ...],
    events: list[GameEvent],
) -> tuple[GameState, list[GameEvent]]:
    """
    Each Jack skips one more player: playing two Jacks together
    reaches two players ahead instead of one, and turn advancement
    covers the same distance so the reached player is the one left
    to counter or accept the (now doubled) skip.
    """

    skip_count = len(played_cards)

    next_index = _calculate_next_index(state, steps=skip_count)
    next_player = state.players[next_index]

    new_state = state.replace(
        phase=Phase.AWAITING_SKIP_RESPONSE,
        pending_skip_player_id=next_player.id,
        active_suit=None,
    )

    events.append(
        GameEvent(
            type=EventType.SKIP_STARTED,
            payload={
                "skip_card": played_cards[0].label(),
                "target_player_id": next_player.id,
                "skip_count": skip_count,
            },
        )
    )

    new_state, turn_events = _advance_turn(new_state, steps=skip_count)
    events.extend(turn_events)

    return new_state, events


def _apply_reverse_effect(
    state: GameState,
    played_cards: tuple[Card, ...],
    events: list[GameEvent],
) -> tuple[GameState, list[GameEvent]]:
    """
    Each King flips direction once, so an even number played together
    cancels out (net no-op) and an odd number nets a single reverse —
    the literal result of "stacking" a toggle.
    """

    flips = len(played_cards) % 2
    new_direction = state.direction * (-1 if flips else 1)

    new_state = state.replace(
        direction=new_direction,
        phase=Phase.AWAITING_MOVE,
        active_suit=None,
    )

    events.append(
        GameEvent(
            type=EventType.DIRECTION_REVERSED,
            payload={"direction": new_direction},
        )
    )

    new_state, turn_events = _advance_turn(new_state, steps=1)
    events.extend(turn_events)

    return new_state, events


# ---------------------------------------------------------------------
# Draw helpers
# ---------------------------------------------------------------------


def _draw_cards_for_player(
    state: GameState,
    player_id: str,
    count: int,
) -> tuple[GameState, list[GameEvent]]:

    if count <= 0:
        return state, []

    draw_pile = list(state.draw_pile)
    discard_pile = list(state.discard_pile)
    drawn: list[Card] = []
    events: list[GameEvent] = []

    for _ in range(count):
        if not draw_pile:
            draw_pile, discard_pile = _reshuffle_discard_into_draw_pile(
                draw_pile=draw_pile,
                discard_pile=discard_pile,
            )

        if not draw_pile:
            break

        drawn.append(draw_pile.pop())

    hand = list(state.hand_of(player_id))
    hand.extend(drawn)

    new_hands = dict(state.hands)
    new_hands[player_id] = tuple(hand)

    new_state = state.replace(
        hands=new_hands,
        draw_pile=tuple(draw_pile),
        discard_pile=tuple(discard_pile),
    )

    events.append(
        GameEvent(
            type=EventType.CARDS_DRAWN,
            payload={
                "player_id": player_id,
                "count": len(drawn),
            },
        )
    )

    if state.pending_draw_count > 0:
        events.append(
            GameEvent(
                type=EventType.DRAW_STACK_CLEARED,
                payload={"player_id": player_id},
            )
        )

    return new_state, events


def _reshuffle_discard_into_draw_pile(
    draw_pile: list[Card],
    discard_pile: list[Card],
) -> tuple[list[Card], list[Card]]:

    if len(discard_pile) <= 1:
        return draw_pile, discard_pile

    top_card = discard_pile[-1]
    recyclable = discard_pile[:-1]

    random.shuffle(recyclable)

    return recyclable, [top_card]


# ---------------------------------------------------------------------
# Forfeit helpers
# ---------------------------------------------------------------------


def _remove_player_from_play(
    state: GameState,
    player_id: str,
    event_type: EventType,
) -> tuple[GameState, list[GameEvent]]:
    """
    Shared machinery for taking a player out of an in-progress game —
    whether they were forced out (a forfeit, see _forfeit_player) or
    left on their own (a quit, see _apply_quit).

    Their hand is shuffled back into the draw pile so those cards
    stay in circulation for the remaining players, and their seat is
    marked eliminated (skipped in turn order from then on, per
    _calculate_next_index). If only one player is left standing after
    this, the game concludes with them as the winner.

    `event_type` is the caller's choice of PLAYER_ELIMINATED or
    PLAYER_LEFT so the UI can tell a forced forfeit apart from a
    voluntary departure.
    """

    hand_size = len(state.hand_of(player_id))

    returned_cards = list(state.draw_pile) + list(state.hand_of(player_id))
    random.shuffle(returned_cards)

    new_hands = dict(state.hands)
    new_hands[player_id] = tuple()

    eliminated = set(state.eliminated_player_ids)
    eliminated.add(player_id)

    new_state = state.replace(
        hands=new_hands,
        draw_pile=tuple(returned_cards),
        eliminated_player_ids=frozenset(eliminated),
    )

    events = [
        GameEvent(
            type=event_type,
            payload={"player_id": player_id, "hand_size": hand_size},
        )
    ]

    new_state, conclusion_events = _conclude_if_one_player_remains(new_state)
    events.extend(conclusion_events)

    return new_state, events


def _conclude_if_one_player_remains(
    state: GameState,
) -> tuple[GameState, list[GameEvent]]:
    """
    If elimination/departure has left exactly one active player, end
    the game with them as the winner. No-op otherwise.
    """

    if state.active_player_count != 1:
        return state, []

    winner_id = next(
        player.id
        for player in state.players
        if player.id not in state.eliminated_player_ids
    )

    new_state = state.replace(
        phase=Phase.FINISHED,
        winner_id=winner_id,
    )

    events = [
        GameEvent(
            type=EventType.PLAYER_WON,
            payload={"player_id": winner_id},
        ),
        GameEvent(
            type=EventType.GAME_FINISHED,
            payload={"winner_id": winner_id},
        ),
    ]

    return new_state, events


def _forfeit_player(
    state: GameState,
    player_id: str,
) -> tuple[GameState, list[GameEvent]]:
    """
    Eliminate a player who was punished up to the forfeit hand size
    with no way to avoid it. See _remove_player_from_play for the
    shared mechanics.
    """

    return _remove_player_from_play(
        state=state,
        player_id=player_id,
        event_type=EventType.PLAYER_ELIMINATED,
    )


def _apply_quit(
    state: GameState,
    action: QuitAction,
) -> tuple[GameState, list[GameEvent]]:
    """
    Voluntarily leave an in-progress game at any point — not just on
    your own turn (apply_move special-cases QuitAction ahead of the
    turn-ownership check, exactly like SayNikoKadiAction).

    Shares _forfeit_player's "return the hand to the draw pile,
    eliminate the seat, auto-conclude if one player remains"
    machinery via _remove_player_from_play, but emits PLAYER_LEFT
    instead of PLAYER_ELIMINATED since this wasn't a forced-draw
    punishment.

    If the player who quit was mid-obligation (their own turn, or the
    target of a pending question/skip/draw response — these always
    coincide, since the engine only ever points current_player at
    whoever holds the pending obligation), that obligation is cleared
    and the turn moves on to the next active player. Otherwise the
    game's current turn/phase is untouched.
    """

    if action.player_id not in state.hands:
        raise IllegalMove("Unknown player.")

    if action.player_id in state.eliminated_player_ids:
        raise IllegalMove("Player has already left the game.")

    was_current_player = state.current_player.id == action.player_id

    new_state, events = _remove_player_from_play(
        state=state,
        player_id=action.player_id,
        event_type=EventType.PLAYER_LEFT,
    )

    if new_state.phase == Phase.FINISHED:
        return new_state, events

    if was_current_player:
        new_state = new_state.replace(
            phase=Phase.AWAITING_MOVE,
            pending_draw_count=0,
            pending_question_player_id=None,
            pending_skip_player_id=None,
        )

        new_state, turn_events = _advance_turn(new_state, steps=1)
        events.extend(turn_events)

    return new_state, events


# ---------------------------------------------------------------------
# Turn helpers
# ---------------------------------------------------------------------


def _advance_turn(
    state: GameState,
    steps: int,
) -> tuple[GameState, list[GameEvent]]:

    next_index = _calculate_next_index(state, steps=steps)

    new_state = state.replace(current_player_index=next_index)

    return new_state, [
        GameEvent(
            type=EventType.TURN_ADVANCED,
            payload={"current_player_id": new_state.current_player.id},
        )
    ]


def _calculate_next_index(
    state: GameState,
    steps: int,
) -> int:
    """
    Find the seat `steps` hops away in the current direction,
    skipping over eliminated players' seats.
    """

    if state.active_player_count <= 1:
        return state.current_player_index

    index = state.current_player_index
    hops_remaining = steps

    while hops_remaining > 0:
        index = (index + state.direction) % state.player_count

        if state.players[index].id not in state.eliminated_player_ids:
            hops_remaining -= 1

    return index


# ---------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------


def _matches_required_suit_or_rank(
    state: GameState,
    cards: tuple[Card, ...],
) -> bool:
    """
    Whether ``cards`` (all one rank — enforced by
    ``_validate_play_action_shape``) can be laid down on the current
    top card as a group.

    Same rank as the top card always works, regardless of suit: that
    check only needs one representative card since the whole group
    shares it. Otherwise, the group still counts as playable as long
    as ANY one of the cards follows the required suit — the rest just
    ride along on the shared rank, so e.g. a 5 of hearts and a 5 of
    spades can be played together on a hearts pile even though the
    spade alone couldn't be.
    """

    if cards[0].rank == state.top_card.rank:
        return True

    required_suit = state.required_suit

    return any(card.suit == required_suit for card in cards)


def _is_ace(card: Card) -> bool:
    return card.rank == Rank.ACE


def _is_joker(card: Card) -> bool:
    return card.rank == Rank.JOKER


def _card_color(card: Card) -> Optional[str]:
    return card.color


def _is_opening_special_card(
    card: Card,
    rules: RuleConfig,
) -> bool:

    if _is_ace(card) or _is_joker(card):
        return True

    if card.rank in rules.draw_ranks:
        return True

    if card.rank in rules.question_ranks:
        return True

    if card.rank in rules.skip_ranks:
        return True

    if card.rank in rules.reverse_ranks:
        return True

    return False


def _remove_cards_from_hand(
    hand: tuple[Card, ...],
    cards: tuple[Card, ...],
) -> list[Card]:
    new_hand = list(hand)

    for card in cards:
        new_hand.remove(card)

    return new_hand


def _can_finish_with(card: Card, rules: RuleConfig) -> bool:
    """
    Whether ``card`` is a rank the game can actually END on — used to
    decide whether emptying your hand with it is an outright win (see
    _commit_play_cards) and, just as importantly, to stop a player
    from ever being left holding a single card that could NEVER
    legally finish the game if restrict_lone_card_to_finishable is
    enabled (see _validate_can_reach_one_card below). Not a
    playability check — every card is always playable, including as
    your very last one; this only gates whether doing so wins.
    """

    if _is_ace(card):
        return rules.ace_can_finish

    if _is_joker(card):
        return rules.joker_can_finish

    return card.rank in rules.finishable_ranks


def _validate_can_reach_one_card(
    player_id: str,
    new_hand: list[Card],
    rules: RuleConfig,
) -> None:
    """
    Opt-in via rules.restrict_lone_card_to_finishable (off by
    default — see that flag's docstring in config.py for why): when
    enabled, a player is never allowed to play their way down to a
    single card that could never actually finish the game (an Ace, a
    2/3/8/J/Q/K, a Joker — see finishable_ranks/ace_can_finish/
    joker_can_finish). They'd just be stuck holding it, unable to
    ever legally WIN on it (they can still play it — see
    _can_finish_with — just not as a winning move).

    Applies regardless of whether they remembered to send
    declare_niko_kadi=True — reaching one card and declaring it are
    tightly coupled everywhere else in this engine (see
    _validate_niko_kadi), so this blocks the state itself rather than
    just the announcement.
    """

    if len(new_hand) != 1:
        return

    remaining_card = new_hand[0]

    if not _can_finish_with(remaining_card, rules):
        raise IllegalMove(
            f'Player {player_id} cannot declare "Niko Kadi" holding only '
            f"{remaining_card.label()} — that card can never finish the "
            "game."
        )


def _validate_niko_kadi(
    player_id: str,
    remaining_cards: int,
    declared: set[str],
    rules: RuleConfig,
) -> None:

    if not rules.must_declare_niko_kadi:
        return

    if remaining_cards != 1:
        return

    if player_id in declared:
        return

    if rules.strict_niko_kadi:
        raise IllegalMove(
            'Player must declare "Niko Kadi" when going down to one card.'
        )