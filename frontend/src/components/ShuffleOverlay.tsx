import { useEffect, useState } from "react";
import { PlayingCard } from "./PlayingCard";
import type { CardView } from "../types";

// PlayingCard's faceDown render never reads rank/suit/joker_color —
// it only needs a CardView-shaped value to satisfy the prop type.
const BLANK_CARD: CardView = {
  rank: "2",
  suit: null,
  joker_color: null,
  label: "",
};

const CARD_COUNT = 6;

// Matches the CSS animation's own duration (see .shuffle-card in
// App.css) plus the stagger across all cards, so the overlay doesn't
// start fading while cards are still mid-riffle. Kept short and
// one-shot — this only ever plays once, right when the table first
// mounts for a freshly started game.
const SHUFFLE_MS = 1400;
const FADE_MS = 300;

interface ShuffleOverlayProps {
  onDone: () => void;
}

export function ShuffleOverlay({ onDone }: ShuffleOverlayProps) {
  const [fading, setFading] = useState(false);

  useEffect(() => {
    const fadeTimer = window.setTimeout(() => setFading(true), SHUFFLE_MS);
    const doneTimer = window.setTimeout(onDone, SHUFFLE_MS + FADE_MS);

    return () => {
      window.clearTimeout(fadeTimer);
      window.clearTimeout(doneTimer);
    };
    // Intentionally only depends on onDone — this is a one-shot timer
    // pair set up once when the overlay mounts, not something that
    // should restart if the caller happens to re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={`shuffle-overlay${fading ? " fading" : ""}`}
      aria-hidden="true"
    >
      <div className="shuffle-deck">
        {Array.from({ length: CARD_COUNT }, (_, index) => (
          <div
            key={index}
            className="shuffle-card"
            style={
              {
                "--i": index,
                "--dir": index % 2 === 0 ? 1 : -1,
              } as React.CSSProperties
            }
          >
            <PlayingCard card={BLANK_CARD} faceDown />
          </div>
        ))}
      </div>
      <p className="shuffle-label">Shuffling…</p>
    </div>
  );
}
