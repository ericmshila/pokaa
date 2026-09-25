import type { PlayerView } from "../types";
import { colorForPlayer } from "../playerColors";

function initialOf(name: string): string {
  return name.trim().charAt(0).toUpperCase() || "?";
}

interface OpponentPanelProps {
  opponents: PlayerView[];
  nextUpPlayerId: string | null;
  isInTension: (player: PlayerView) => boolean;
}

/**
 * The row of opponent seats along the top of the table — one compact
 * card per opponent with their avatar (initial, per the existing
 * PlayerView data — never a hardcoded name), name, and live card
 * count, plus the current-turn / up-next / Niko-Kadi-tension cues
 * that were previously inlined in Table.tsx. Pure display: every
 * value comes from the room state passed in, nothing is computed or
 * mutated here.
 */
export function OpponentPanel({
  opponents,
  nextUpPlayerId,
  isInTension,
}: OpponentPanelProps) {
  return (
    <div className="opponents">
      {opponents.map((player) => {
        const tense = isInTension(player);

        return (
          <div
            key={player.id}
            className={[
              "opponent",
              player.is_current_player ? "current" : "",
              player.is_eliminated ? "eliminated" : "",
              tense ? "niko-kadi-tension" : "",
              player.id === nextUpPlayerId ? "up-next" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className="avatar" aria-hidden="true">
              {initialOf(player.name)}
            </span>
            <span className="name" style={{ color: colorForPlayer(player.id) }}>
              {player.name}
            </span>
            {player.is_eliminated ? (
              <span className="count">Eliminated</span>
            ) : (
              <span className="count">
                {player.card_count} card{player.card_count === 1 ? "" : "s"}
              </span>
            )}
            {tense && (
              <span className="tension-badge" title="Declared Niko Kadi">
                ✋
              </span>
            )}
            {!player.is_current_player && player.id === nextUpPlayerId && (
              <span className="up-next-label">Up next</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
