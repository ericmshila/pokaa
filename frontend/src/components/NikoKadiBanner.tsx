import { useEffect, useState } from "react";
import { colorForPlayer } from "../playerColors";

// Matches the CSS animation's own duration (see .niko-kadi-banner in
// App.css) — held on screen long enough to actually register, then
// fades. One-shot per declaration; Table.tsx remounts this (via a
// fresh `key`) for each new "niko_kadi_declared" event rather than
// this component tracking a queue itself.
const HOLD_MS = 2200;
const FADE_MS = 350;

interface NikoKadiBannerProps {
  playerId: string;
  playerName: string;
  onDone: () => void;
}

/**
 * A loud, table-wide announcement the moment anyone declares "Niko
 * Kadi" — the whole point being that it's genuinely hard for the
 * other players to miss, unlike the existing tension badge/glow on
 * the opponent row (see .niko-kadi-tension in App.css), which is easy
 * to not notice mid-conversation. Deliberately non-blocking
 * (pointer-events: none) — it's a heads-up, not a modal — and
 * self-dismisses; nobody has to close it.
 */
export function NikoKadiBanner({
  playerId,
  playerName,
  onDone,
}: NikoKadiBannerProps) {
  const [fading, setFading] = useState(false);

  useEffect(() => {
    const fadeTimer = window.setTimeout(() => setFading(true), HOLD_MS);
    const doneTimer = window.setTimeout(onDone, HOLD_MS + FADE_MS);

    return () => {
      window.clearTimeout(fadeTimer);
      window.clearTimeout(doneTimer);
    };
    // One-shot timer pair set up once per declaration (this component
    // remounts per event via Table.tsx's `key`) — not something that
    // should restart on an unrelated re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={`niko-kadi-banner${fading ? " fading" : ""}`}
      role="status"
      aria-live="polite"
    >
      <span className="niko-kadi-banner-icon" aria-hidden="true">
        🃏
      </span>
      <span className="niko-kadi-banner-text">
        <span
          className="niko-kadi-banner-name"
          style={{ color: colorForPlayer(playerId) }}
        >
          {playerName}
        </span>
        <span className="niko-kadi-banner-declare">declares Niko Kadi!</span>
      </span>
    </div>
  );
}
