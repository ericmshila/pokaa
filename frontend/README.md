# Kenyan Poker (Kadi) — frontend

React + TypeScript + Vite client for the Kadi backend in `../backend`.

This is a **minimal playable table**: create/join a room, start a game,
see your hand, play/draw/pass, watch opponents' card counts and turn
order update live over WebSocket. It's intentionally plain (no card
art, animations, or lobby browser) — a foundation to build polish on
top of, not a finished product.

## Running it

1. Start the backend first (from `../backend`):

   ```bash
   pip install -r requirements.txt
   python run.py
   ```

   It listens on `http://localhost:8000` by default (bound to
   `0.0.0.0`, so it's also reachable from other devices — see
   "Playing with others" below).

2. Install and run the frontend:

   ```bash
   npm install
   npm run dev
   ```

   Vite will print a local URL (typically `http://localhost:5173`)
   plus a "Network" URL other devices can use.

3. Open that URL in two browser tabs (or two different browsers) to
   play against yourself: create a room in one tab, copy the room
   code into the other, join, then start once at least 2 players have
   joined.

The app auto-detects the backend at whatever host you used to load
the page, on port 8000 — no config needed whether that's `localhost`,
a LAN IP, or a Hamachi/Tailscale virtual IP. Only copy `.env.example`
to `.env.local` and set `VITE_API_BASE_URL` if the backend runs
somewhere genuinely different (a separate host/port from the
frontend).

### Playing with others

See `../backend/README.md#playing-with-others` for how to have a
friend join over your LAN, or remotely via Hamachi/Tailscale — same
frontend, same backend, no code changes, just a different URL.

## How it fits together

- `src/api.ts` — REST calls for create/join/start/inspect room
  (`app/api/routes.py` on the backend). Mirrors it 1:1.
- `src/useGameSocket.ts` — owns the WebSocket connection to
  `app/api/websocket.py` once a game has started: sends `play_cards` /
  `draw` / `pass` / `say_niko_kadi` messages, receives a personalized
  game state + event log after every move.
- `src/types.ts` — TypeScript types mirroring the backend's JSON
  shapes (`app/game/serializers.py`, `app/rules/events.py`). Keep
  these in sync if the backend's response shapes change.
- `src/components/Lobby.tsx` — create/join a room, poll for other
  players, start the game once ready.
- `src/components/Table.tsx` — the live game view: hand, opponents,
  discard pile, phase-aware action bar (draw / pass), event log.
- `src/components/SuitPicker.tsx` — modal shown when playing an Ace or
  Joker, which require declaring the next suit.

## Known gaps (next steps)

- Only single-card plays are wired up in the UI. The backend/WS
  protocol already supports playing multiple cards of the same rank
  in one move (`cards: [...]` in the `play_cards` message) — the hand
  UI just doesn't offer multi-select yet.
- No visual card art, animations, sound, or mobile-specific layout.
- No *automatic* reconnect — a dropped socket shows a banner with a
  "Leave game" button; rejoining is a manual step (identity persists
  via `sessionStorage`, so rejoining restores your hand and the live
  game state).
- No lobby "browse open rooms" — joining requires knowing the room
  code.
