import type { Phase } from "../types";

interface DrawButtonProps {
  phase: Phase;
  isMyTurn: boolean;
  pendingDrawCount: number;
  onDraw: () => void;
  onPass: () => void;
}

/**
 * The primary call-to-action beneath the turn indicator: draw a card,
 * draw under punishment pressure, or accept a pending skip. Renders
 * nothing when it isn't this player's turn or the round is over — the
 * same gating the inline `ActionBar` used before this was pulled out
 * into its own file.
 */
export function DrawButton({
  phase,
  isMyTurn,
  pendingDrawCount,
  onDraw,
  onPass,
}: DrawButtonProps) {
  if (!isMyTurn || phase === "finished") {
    return null;
  }

  if (phase === "awaiting_skip_response") {
    return (
      <div className="action-bar">
        <button type="button" className="btn-secondary" onClick={onPass}>
          Accept skip (pass)
        </button>
      </div>
    );
  }

  if (phase === "awaiting_draw_response") {
    return (
      <div className="action-bar">
        <button type="button" className="draw-cta" onClick={onDraw}>
          🂠 Draw {pendingDrawCount} cards
        </button>
      </div>
    );
  }

  return (
    <div className="action-bar">
      <button type="button" className="draw-cta" onClick={onDraw}>
        🂠 Draw a card
      </button>
    </div>
  );
}
