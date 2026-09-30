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
    # Any legal card empties your hand and wins outright by default —
    # see finishable_ranks below for the full "which cards can end the
    # game" rule. This flag is what lets an Ace specifically take part
    # in that; set False to carve the Ace back out as an exception
    # without touching finishable_ranks itself.
    ace_can_finish: bool = True

    # Joker is always playable regardless of the top card (no suit or
    # rank match required), like Ace — but unlike Ace, it doesn't
    # declare a suit; it triggers a draw-pressure punishment instead
    # (see draw_ranks above) whenever it doesn't end the game outright
    # (see joker_can_finish below).
    joker_can_answer_question: bool = False
    joker_can_finish: bool = True

    must_declare_niko_kadi: bool = True
    strict_niko_kadi: bool = True
    niko_kadi_penalty_cards: int = 2

    # Any card empties your hand and wins outright by default — the
    # simpler, traditional Kadi rule, and the one that actually
    # matches what "Niko Kadi" promises ("I'm about to win"): a player
    # who declares it while holding a lone 2, Joker, or any other
    # power card really is one legal play away from winning, not
    # stuck hoping to draw into a "safer" plain rank first. This is
    # purely about winning, not playability — every card was already a
    # legal play at any time, including as a player's very last one
    # (see _commit_play_cards); this only decides whether doing so
    # ends the game right there or just leaves the player cardless
    # (their card's own effect — the punishment, the question, the
    # skip, the declared suit — still lands on whoever's next, since a
    # non-winning empty-hand play still resolves normally). A stricter
    # ruleset can still narrow this back down — e.g. dropping the
    # punishment ranks (2/3/8) so the round always keeps moving for at
    # least one more play after a punishment — by overriding this set
    # (and/or ace_can_finish/joker_can_finish) explicitly.
    finishable_ranks: set[Rank] = field(
        default_factory=lambda: {
            Rank.TWO,
            Rank.THREE,
            Rank.FOUR,
            Rank.FIVE,
            Rank.SIX,
            Rank.SEVEN,
            Rank.EIGHT,
            Rank.NINE,
            Rank.TEN,
            Rank.JACK,
            Rank.QUEEN,
            Rank.KING,
        }
    )

    # Every card is playable at the player's whim — including playing
    # your way down to a lone card that (under some OTHER, stricter
    # ruleset than the default) can never itself WIN the game — see
    # finishable_ranks/ace_can_finish/joker_can_finish above. Left
    # False (the default), a player is never blocked from reaching
    # that state — they can always still play it (see
    # _commit_play_cards), they just won't win the game by doing so
    # under such a ruleset; they'll be cardless until they draw or
    # someone else changes the board. Under the default ruleset (every
    # rank finishable) this flag is a no-op, since there's no
    # unfinishable lone card left to block reaching. It matters once
    # something is carved back out — e.g. a future rule eliminating
    # whoever holds the highest card value when the game ends (to
    # discourage hoarding) only works if players are actually free to
    # unload any card whenever they want, rather than being forced to
    # keep "safe" cards in hand for a legal win. Set True to restore
    # the older, stricter behavior that blocks reaching that state
    # outright instead.
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
