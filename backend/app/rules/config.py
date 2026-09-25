from __future__ import annotations

from dataclasses import dataclass, field

from .cards import Rank


@dataclass(frozen=True)
class RuleConfig:

    initial_hand_size: int = 4

    # Joker is a punishment card, same family as 2s/3s: playing one
    # forces the next player to draw this many, or counter with
    # another draw card. Stacks with 2s/3s and other Jokers just like
    # they stack with each other (see engine._apply_draw_card_effect).
    draw_ranks: dict[Rank, int] = field(
        default_factory=lambda: {
            Rank.TWO: 2,
            Rank.THREE: 3,
            Rank.JOKER: 5,
        }
    )

    draw_stacking_enabled: bool = True

    question_ranks: set[Rank] = field(
        default_factory=lambda: {
            Rank.EIGHT,
            Rank.QUEEN,
        }
    )

    question_answer_ranks: set[Rank] = field(
        default_factory=lambda: {
            Rank.TWO,
            Rank.THREE,
            Rank.FOUR,
            Rank.FIVE,
            Rank.SIX,
            Rank.SEVEN,
            Rank.NINE,
            Rank.TEN,
        }
    )

    skip_ranks: set[Rank] = field(
        default_factory=lambda: {
            Rank.JACK,
        }
    )

    skip_can_be_countered: bool = True

    reverse_ranks: set[Rank] = field(
        default_factory=lambda: {
            Rank.KING,
        }
    )

    ace_is_wild: bool = True
    ace_requires_declared_suit: bool = True
    ace_counters_punishments: bool = True
    ace_can_answer_question: bool = False
    # An Ace can never be the literal WINNING play — it's still always
    # playable, including as your last card (it just leaves you
    # cardless rather than victorious; see finishable_ranks below for
    # the full "which cards can end the game" rule and
    # restrict_lone_card_to_finishable for the separate, opt-in
    # question of whether a player may even be LEFT holding one as
    # their only card).
    ace_can_finish: bool = False

    # Joker is always playable regardless of the top card (no suit or
    # rank match required), like Ace — but unlike Ace, it doesn't
    # declare a suit; it triggers a draw-pressure punishment instead
    # (see draw_ranks above).
    joker_can_answer_question: bool = False
    joker_can_finish: bool = False

    must_declare_niko_kadi: bool = True
    strict_niko_kadi: bool = True
    niko_kadi_penalty_cards: int = 2

    # Traditional Kadi: only a plain, effect-free rank can literally
    # WIN the game — every "power" rank (2/3/Joker's draw pressure,
    # 8/Queen's question, Jack's skip, King's reverse, plus Ace, see
    # ace_can_finish above) is excluded here on purpose. This is
    # purely about winning, not playability: a power card is always a
    # legal play, including as a player's very last card — see
    # _commit_play_cards. Playing one down to zero cards just leaves
    # that player cardless (their card's own effect — the punishment,
    # the question, the skip, the declared suit — still lands on
    # whoever's next) rather than ending the game; they're still an
    # active player and simply draw back in on their next turn if
    # they're still empty-handed by then. A player can also still be
    # holding one of these when they're down to one card — see
    # restrict_lone_card_to_finishable below, a distinct,
    # separately-toggleable question from whether that card can
    # actually complete the game.
    finishable_ranks: set[Rank] = field(
        default_factory=lambda: {
            Rank.FOUR,
            Rank.FIVE,
            Rank.SIX,
            Rank.SEVEN,
            Rank.NINE,
            Rank.TEN,
        }
    )

    # Every card is playable at the player's whim — including playing
    # your way down to a lone power card (Ace/2/3/8/J/Q/K/Joker) that
    # can never itself WIN the game (see finishable_ranks/
    # ace_can_finish/joker_can_finish above). Left False (the
    # default), a player is never blocked from reaching that state —
    # they can always still play it (see _commit_play_cards), they
    # just won't win the game by doing so; they'll be cardless until
    # they draw or someone else changes the board. This matters beyond
    # convenience: a future rule eliminating whoever holds the highest
    # card value when the game ends (to discourage hoarding) only
    # works if players are actually free to unload any card whenever
    # they want, rather than being forced to keep "safe" plain cards
    # in hand for a legal win. Set True to restore the older, stricter
    # behavior that blocks reaching that state outright instead.
    restrict_lone_card_to_finishable: bool = False

    # ---------------------------------------------------------
    # Forfeit
    # ---------------------------------------------------------

    # A player who is forced to draw an unavoidable punishment stack
    # (a 2/3 draw chain they had no counter or restack for) and ends
    # up holding this many cards or more is eliminated from the game.
    # Their hand is shuffled back into the draw pile. Set to None to
    # disable this rule entirely.
    forfeit_hand_size: int | None = 13
