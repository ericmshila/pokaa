import { PlayingCard } from "./PlayingCard";
import type { CardView, Suit } from "../types";

interface CurrentCardProps {
  topCard: CardView;
  activeSuit: Suit | null;
  drawPileCount: number;
  landingPulse: number;
}

/**
 * The central play area's discard pile: the current top card (with its
 * landing-animation replay, keyed on `landingPulse` so a fresh play
 * always re-triggers it), the declared-suit badge when one is active,
 * and the live draw-pile count. Pure display — every value comes from
 * room state passed in by Table.tsx, nothing is computed here.
 */
export function CurrentCard({
  topCard,
  activeSuit,
  drawPileCount,
  landingPulse,
}: CurrentCardProps) {
  return (
    <div className="discard-pile">
      <div key={landingPulse} className="card-landing-wrap">
        <PlayingCard card={topCard} />
      </div>
      {activeSuit && <span className="active-suit">Declared: {activeSuit}</span>}
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
