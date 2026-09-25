/**
 * Client-side legality PREVIEW for the current player's hand — powers
 * a subtle glow on cards that are currently playable (see
 * PlayingCard.tsx). Deliberately a POSITIVE-only hint: a card this
 * module calls illegal renders exactly like any other unglowed card,
 * there's no separate "dimmed = don't bother" treatment. Dimming
 * everything unplayable used to hand the player the answer the
 * instant it became their turn — nothing left to actually weigh.
 *
 * Table.tsx also holds off on ever showing the glow for a few seconds
 * after a new decision starts (see its hintsRevealed timer), so even
 * this positive hint is a nudge for someone still thinking, not an
 * instant readout.
 *
 * This is a preview only. The server (app/rules/engine.py) is the
 * sole source of truth for what's actually legal — every move is
 * still validated there regardless of what this module says. That
 * means two things:
 *
 * 1. A card this module calls "illegal" must never be prevented from
 *    being clicked/selected — it's a visual hint, not a gate. If this
 *    logic ever drifts from the engine's, the worst case is a
 *    momentarily wrong (or missing) glow, never a blocked legal move.
 * 2. Each card is evaluated as if it were a lone, single-card play.
 *    The engine actually allows a same-rank GROUP to ride along on
 *    just one member matching the required suit (see
 *    engine._matches_required_suit_or_rank) — so in the rare case of
 *    a multi-card same-rank play where only one card in hand matches
 *    suit, its same-rank siblings may not glow here despite being
 *    genuinely playable once grouped with it. Cosmetic only, per (1).
 *
 * The constants below mirror the relevant defaults in
 * backend/app/rules/config.py. Keep them in sync if those change —
 * again, only the preview goes stale if they drift, not enforcement.
 */

import type { CardView, GameStateView, Rank } from "./types";

const DRAW_RANKS = new Set<Rank>(["2", "3", "JOKER"]);
const QUESTION_ANSWER_RANKS = new Set<Rank>([
  "2",
  "3",
  "4",
  "5",
  "6",
  "7",
  "9",
  "10",
]);
const SKIP_RANKS = new Set<Rank>(["J"]);

const ACE_CAN_ANSWER_QUESTION = false;
const JOKER_CAN_ANSWER_QUESTION = false;
const ACE_COUNTERS_PUNISHMENTS = true;
const DRAW_STACKING_ENABLED = true;
const SKIP_CAN_BE_COUNTERED = true;

function isAce(card: CardView): boolean {
  return card.rank === "A";
}

function isJoker(card: CardView): boolean {
  return card.rank === "JOKER";
}

function cardColor(card: CardView): "red" | "black" | null {
  if (card.joker_color) {
    return card.joker_color;
  }

  if (card.suit === "hearts" || card.suit === "diamonds") {
    return "red";
  }

  if (card.suit === "spades" || card.suit === "clubs") {
    return "black";
  }

  return null;
}

// Same rank as the top card always works, any suit — otherwise the
// card's own suit has to match required_suit. Mirrors
// engine._matches_required_suit_or_rank for a single card.
function matchesRequiredSuitOrRank(
  card: CardView,
  state: GameStateView,
): boolean {
  if (card.rank === state.top_card.rank) {
    return true;
  }

  return state.required_suit !== null && card.suit === state.required_suit;
}

/**
 * Whether `card`, played alone, would currently be accepted by the
 * server — see the module docstring above for the caveats.
 */
export function isCardLegal(card: CardView, state: GameStateView): boolean {
  switch (state.phase) {
    case "awaiting_move":
      if (isAce(card)) {
        return true;
      }
      if (isJoker(card)) {
        return true;
      }
      return matchesRequiredSuitOrRank(card, state);

    case "awaiting_answer":
      if (isAce(card) && ACE_CAN_ANSWER_QUESTION) {
        return true;
      }
      if (isJoker(card) && JOKER_CAN_ANSWER_QUESTION) {
        return true;
      }
      if (!QUESTION_ANSWER_RANKS.has(card.rank)) {
        return false;
      }
      return state.required_suit !== null && card.suit === state.required_suit;

    case "awaiting_draw_response": {
      if (isAce(card) && ACE_COUNTERS_PUNISHMENTS) {
        return true;
      }
      if (!DRAW_STACKING_ENABLED) {
        return false;
      }
      if (!DRAW_RANKS.has(card.rank)) {
        return false;
      }

      if (isJoker(state.top_card)) {
        if (isJoker(card)) {
          return true;
        }
        return cardColor(card) === cardColor(state.top_card);
      }

      if (isJoker(card)) {
        return true;
      }
      return matchesRequiredSuitOrRank(card, state);
    }

    case "awaiting_skip_response":
      if (isAce(card) && ACE_COUNTERS_PUNISHMENTS) {
        return true;
      }
      if (!SKIP_CAN_BE_COUNTERED) {
        return false;
      }
      return SKIP_RANKS.has(card.rank);

    default:
      return false;
  }
}
