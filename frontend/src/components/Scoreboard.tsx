import type { ScoreboardEntryView } from "../types";
import { colorForPlayer } from "../playerColors";

interface ScoreboardProps {
  scoreboard: ScoreboardEntryView[];
}

/**
 * A compact "wins so far, in this room" strip — the running per-room
 * scoreboard the backend tallies across restarts (see app.db's module
 * docstring: intentionally room-local, not a global/account
 * leaderboard). Already sorted most-wins-first by the server.
 *
 * Rendered as nothing at all until the first game in this room
 * actually finishes — an empty strip reading "0 wins" for everyone
 * would just be clutter during a room's first round.
 */
export function Scoreboard({ scoreboard }: ScoreboardProps) {
  if (scoreboard.length === 0) {
    return null;
  }

  return (
    <div className="scoreboard" aria-label="Wins this session">
      <span className="scoreboard-icon" aria-hidden="true">
        🏆
      </span>
      {scoreboard.map((entry) => (
        <span key={entry.player_id} className="scoreboard-entry">
          <span
            className="scoreboard-name"
            style={{ color: colorForPlayer(entry.player_id) }}
          >
            {entry.name}
          </span>
          <span className="scoreboard-wins">{entry.wins}</span>
        </span>
      ))}
    </div>
  );
}
