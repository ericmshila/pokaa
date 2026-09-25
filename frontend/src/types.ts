/**
 * Types mirroring the backend's JSON shapes.
 *
 * Kept intentionally close to app/api/schemas.py, app/game/serializers.py
 * and app/rules/events.py on the backend so the two sides don't quietly
 * drift apart.
 */

export type Suit = "spades" | "hearts" | "diamonds" | "clubs";

export type Rank =
  | "2"
  | "3"
  | "4"
  | "5"
  | "6"
  | "7"
  | "8"
  | "9"
  | "10"
  | "J"
  | "Q"
  | "K"
  | "A"
  | "JOKER";

export type JokerColor = "red" | "black";

export interface CardView {
  rank: Rank;
  suit: Suit | null;
  joker_color: JokerColor | null;
  label: string;
}

export type Phase =
  | "awaiting_move"
  | "awaiting_answer"
  | "awaiting_draw_response"
  | "awaiting_skip_response"
  | "finished";

export interface PlayerView {
  id: string;
  name: string;
  card_count: number;
  is_current_player: boolean;
  is_you: boolean;
  is_eliminated: boolean;
  has_declared_niko_kadi: boolean;
}

export interface RoomPlayerSummary {
  id: string;
  name: string;
}

export interface GameStateView {
  current_player: string;
  phase: Phase;
  top_card: CardView;
  direction: number;
  winner_id: string | null;
  pending_draw_count: number;
  pending_question_player_id: string | null;
  pending_skip_player_id: string | null;
  active_suit: Suit | null;
  // What a normal play (or question/draw/skip response) must match
  // right now — see backend GameState.required_suit. null only when
  // the discard pile is nothing but colourless Jokers (shouldn't
  // happen in practice, since the very first discard is forced to be
  // a plain card).
  required_suit: Suit | null;
  draw_pile_count: number;
  players: PlayerView[];
  my_hand: CardView[];
}

// One row of the room-scoped running scoreboard (see backend app.db —
// wins are tallied per room across restarts/replays, not tied to any
// durable cross-room identity). `name` is resolved server-side against
// the room's live player list, so it's always current even though the
// underlying win record only stores a player id.
export interface ScoreboardEntryView {
  player_id: string;
  name: string;
  wins: number;
}

export interface RoomView {
  room_id: string;
  started: boolean;
  players: RoomPlayerSummary[];
  state: GameStateView | null;
  // Present (possibly empty) even before a game has started or
  // finished — the backend always includes this key, never omits it.
  scoreboard: ScoreboardEntryView[];
}

export interface GameEventView {
  type: string;
  payload: Record<string, unknown>;
}

export type ServerMessageType =
  | "state"
  | "error"
  | "player_connected"
  | "player_disconnected"
  | "chat";

export interface ServerMessage {
  type: ServerMessageType;
  room?: RoomView;
  events?: GameEventView[];
  detail?: string;
  player_id?: string;
  name?: string;
  text?: string;
}

// The hook-local, accumulated view of a chat message — `id` is
// generated client-side (the server doesn't assign one) purely so
// React has a stable list key.
export interface ChatMessageView {
  id: string;
  playerId: string;
  name: string;
  text: string;
}

// The hook-local, accumulated Game Log — unlike `lastEvents` (which
// the socket hook replaces wholesale with just the latest action's
// events), this grows across the whole session so the log panel
// keeps a running history instead of flickering to whatever just
// happened. `id` and `timestamp` are both generated client-side on
// arrival — the server doesn't stamp events with wall-clock time.
export interface GameLogEntryView {
  id: string;
  event: GameEventView;
  timestamp: number;
}
