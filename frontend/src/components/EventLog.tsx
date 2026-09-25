import { useEffect, useRef } from "react";
import type { GameEventView, GameLogEntryView, PlayerView } from "../types";
import { colorForPlayer } from "../playerColors";

function nameOf(players: PlayerView[], id: unknown): string {
  const found = players.find((player) => player.id === id);
  return found ? found.name : String(id);
}

// A row of log text, broken into plain-text segments and
// player-name segments — the name segments get colored per-player
// (see playerColors.ts) so a busy log still reads as "who did what"
// at a glance, without ever relying on color alone (the name itself
// is always right there as text too).
type LogSegment = { text: string; playerId?: string };

function nameSegment(players: PlayerView[], id: unknown): LogSegment {
  return { text: nameOf(players, id), playerId: typeof id === "string" ? id : undefined };
}

function text(value: string): LogSegment {
  return { text: value };
}

function describe(event: GameEventView, players: PlayerView[]): LogSegment[] {
  const payload = event.payload;

  switch (event.type) {
    case "card_played":
      return [nameSegment(players, payload.player_id), text(` played ${payload.card}`)];
    case "cards_drawn":
      return [nameSegment(players, payload.player_id), text(` drew ${payload.count} card(s)`)];
    case "turn_advanced":
      return [nameSegment(players, payload.current_player_id), text("'s turn")];
    case "direction_reversed":
      return [text("Direction reversed")];
    case "draw_stack_started":
      return [text(`Draw pressure started: ${payload.pending_draw_count}`)];
    case "draw_stack_increased":
      return [text(`Draw pressure increased to ${payload.pending_draw_count}`)];
    case "draw_stack_cleared":
      return [nameSegment(players, payload.player_id), text(" cleared the draw pressure")];
    case "question_asked": {
      const count = typeof payload.card_count === "number" ? payload.card_count : 1;
      const prefix = count > 1 ? `Question asked (${count} cards) — ` : "Question asked — ";
      return [text(prefix), nameSegment(players, payload.target_player_id), text(" must answer")];
    }
    case "question_answered":
      return [nameSegment(players, payload.player_id), text(" answered the question")];
    case "question_failed":
      return [nameSegment(players, payload.player_id), text(" failed to answer")];
    case "skip_started": {
      const count = typeof payload.skip_count === "number" ? payload.skip_count : 1;
      const suffix = count > 1 ? ` (${count} players)` : "";
      return [text("Skip aimed at "), nameSegment(players, payload.target_player_id), text(suffix)];
    }
    case "skip_countered":
      return [nameSegment(players, payload.player_id), text(" countered the skip")];
    case "player_skipped":
      return [nameSegment(players, payload.player_id), text(" was skipped")];
    case "ace_counter_played":
      return [nameSegment(players, payload.player_id), text(" countered with an Ace")];
    case "punishment_cleared":
      return [text("Punishment cleared")];
    case "suit_declared":
      return [nameSegment(players, payload.player_id), text(` declared ${payload.suit}`)];
    case "niko_kadi_declared":
      return [nameSegment(players, payload.player_id), text(' declared "Niko Kadi"')];
    case "niko_kadi_penalty":
      return [
        nameSegment(players, payload.player_id),
        text(' was penalized for not declaring "Niko Kadi"'),
      ];
    case "player_won":
      return [nameSegment(players, payload.player_id), text(" won the game!")];
    case "player_eliminated":
      return [
        nameSegment(players, payload.player_id),
        text(` was eliminated (reached ${payload.hand_size} cards)`),
      ];
    case "player_left":
      return [nameSegment(players, payload.player_id), text(" left the game")];
    case "game_started":
      return [text("Game started")];
    case "game_finished":
      return [text("Game finished")];
    default:
      return [text(event.type.replace(/_/g, " "))];
  }
}

// A small, deliberately coarse icon set — grouped by what KIND of
// thing happened (drew, cleared/succeeded, played, warned/penalized,
// game-boundary) rather than one bespoke icon per event type, so the
// log reads at a glance instead of turning into an icon soup.
function iconFor(eventType: string): string {
  switch (eventType) {
    case "cards_drawn":
      return "🂠";
    case "draw_stack_cleared":
    case "punishment_cleared":
    case "question_answered":
    case "skip_countered":
    case "ace_counter_played":
      return "✅";
    case "card_played":
    case "suit_declared":
      return "🂡";
    case "draw_stack_started":
    case "draw_stack_increased":
    case "question_asked":
    case "skip_started":
      return "⚠️";
    case "niko_kadi_declared":
      return "✋";
    case "niko_kadi_penalty":
    case "question_failed":
    case "player_skipped":
    case "player_eliminated":
      return "❗";
    case "player_left":
      return "🚪";
    case "player_won":
      return "🏆";
    case "direction_reversed":
      return "🔄";
    case "game_started":
    case "game_finished":
      return "🎮";
    default:
      return "•";
  }
}

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

interface EventLogProps {
  entries: GameLogEntryView[];
  players: PlayerView[];
}

/**
 * The persistent "GAME LOG" panel — an accumulated running history
 * (see GameLogEntryView / useGameSocket's eventHistory), not just the
 * latest batch of events. Auto-scrolls to the newest entry, mirroring
 * ChatPanel's behaviour.
 */
export function EventLog({ entries, players }: EventLogProps) {
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const list = listRef.current;
    if (list) {
      list.scrollTop = list.scrollHeight;
    }
  }, [entries.length]);

  return (
    <div className="event-log-panel">
      <div className="event-log-header">
        <span className="event-log-icon" aria-hidden="true">
          📋
        </span>
        <span>Game Log</span>
      </div>
      <div className="event-log" ref={listRef}>
        {entries.length === 0 ? (
          <p className="hint">Nothing has happened yet.</p>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="event-log-row">
              <span className="event-log-row-icon" aria-hidden="true">
                {iconFor(entry.event.type)}
              </span>
              <span className="event-log-row-text">
                {describe(entry.event, players).map((segment, i) =>
                  segment.playerId ? (
                    <span key={i} style={{ color: colorForPlayer(segment.playerId) }}>
                      {segment.text}
                    </span>
                  ) : (
                    <span key={i}>{segment.text}</span>
                  ),
                )}
              </span>
              <span className="event-log-row-time">
                {formatTime(entry.timestamp)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
