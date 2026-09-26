import { PlayingCard } from "./PlayingCard";
import type { CardView, Suit } from "../types";

interface CurrentCardProps {
  topCard: CardView;
  activeSuit: Suit | null;
  requiredSuit: Suit | null;
  drawPileCount: number;
  landingPulse: number;
}

/**
 * The central play area's discard pile: the current top card (with its
 * landing-animation replay, keyed on `landingPulse` so a fresh play
 * always re-triggers it), a badge for whatever suit actually has to be
 * matched right now, and the live draw-pile count. Pure display —
 * every value comes from room state passed in by Table.tsx, nothing is
 * computed here.
 *
 * The suit badge covers two distinct cases that both boil down to
 * "the suit you need isn't visible on the top card itself":
 * - An Ace declared one (activeSuit set) — labeled "Declared".
 * - The top card is a Joker, which has no suit of its own, so the
 *   game is still enforcing whatever suit the last suited card before
 *   it had (requiredSuit, walked back by the backend — see
 *   GameState.required_suit) — labeled "Match". Without this, a
 *   Joker on top gives no visible clue why a hand full of cards all
 *   fail to glow as legal.
 * When the top card already shows its own suit plainly (any non-Joker
 * card), requiredSuit is always just that same suit, so no badge is
 * needed — it'd be redundant with the card already on screen.
 */
export function CurrentCard({
  topCard,
  activeSuit,
  requiredSuit,
  drawPileCount,
  landingPulse,
}: CurrentCardProps) {
  const suitBadge = activeSuit
    ? { label: "Declared", suit: activeSuit }
    : topCard.suit === null && requiredSuit
      ? { label: "Match", suit: requiredSuit }
      : null;

  return (
    <div className="discard-pile">
      <div key={landingPulse} className="card-landing-wrap">
        <PlayingCard card={topCard} />
      </div>
      {suitBadge && (
        <span className="active-suit">
          {suitBadge.label}: {suitBadge.suit}
        </span>
      )}
      <span
        className={[
          "draw-pile-count",
          drawPileCount <= 5 ? "critical" : drawPileCount <= 15 ? "low" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        🂠 {drawPileCount} left
      </span>
    </div>
  );
}
