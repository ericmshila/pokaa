import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { useGameSocket } from "../useGameSocket";
import { PlayingCard } from "./PlayingCard";
import { SuitPicker } from "./SuitPicker";
import { QuitConfirm } from "./QuitConfirm";
import { ChatPanel } from "./ChatPanel";
import { EventLog } from "./EventLog";
import { ShuffleOverlay } from "./ShuffleOverlay";
import { NikoKadiBanner } from "./NikoKadiBanner";
import { OpponentPanel } from "./OpponentPanel";
import { Scoreboard } from "./Scoreboard";
import { CurrentCard } from "./CurrentCard";
import { DrawButton } from "./DrawButton";
import * as sound from "../sound";
import { isCardLegal } from "../legality";
import { colorForPlayer } from "../playerColors";
import type { CardView, GameStateView, Suit } from "../types";

interface TableProps {
  roomId: string;
  playerId: string;
  onLeave: () => void;
}

// Only Ace needs a suit declared before it goes out — Joker is a
// punishment card now (like a 2/3, just worth more), so it plays
// immediately with no suit picker.
const WILD_RANKS = new Set(["A"]);

// Falls back to the raw id (rather than throwing/blanking) if the
// player has somehow already dropped out of state.players by the
// time their event's banner renders — a queued NikoKadiBanner (see
// nikoKadiQueue above) can still be showing after someone leaves.
function nameOfPlayer(state: GameStateView, playerId: string): string {
  return state.players.find((p) => p.id === playerId)?.name ?? playerId;
}

// Who's next in turn order, skipping eliminated seats — mirrors
// engine._calculate_next_index. Only meaningful (and only called)
// during "awaiting_move": once a question/skip/draw obligation is
// pending, current_player IS the one under pressure, and who comes
// after them depends on how that resolves rather than just "the next
// seat over", so this would be a guess rather than a preview there.
function computeNextUpPlayerId(state: GameStateView): string | null {
  const total = state.players.length;
  const activeCount = state.players.filter((p) => !p.is_eliminated).length;

  if (activeCount <= 1) {
    return null;
  }

  const currentIndex = state.players.findIndex(
    (p) => p.id === state.current_player,
  );

  if (currentIndex === -1) {
    return null;
  }

  let index = currentIndex;

  for (let hops = 0; hops < total; hops += 1) {
    index = (index + state.direction + total) % total;

    if (!state.players[index].is_eliminated) {
      return state.players[index].id;
    }
  }

  return null;
}

export function Table({ roomId, playerId, onLeave }: TableProps) {
  const { status, room, lastEvents, eventHistory, chatMessages, error, send } =
    useGameSocket(roomId, playerId);
  // Indices into state.my_hand. Multi-card plays require same-rank
  // cards, so selecting a card of a different rank starts a fresh
  // selection rather than mixing ranks.
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(
    new Set(),
  );
  // Set once the player commits a play that includes a wild card, so
  // the suit picker can show before the message actually goes out.
  const [pendingCards, setPendingCards] = useState<CardView[] | null>(null);
  const [muted, setMuted] = useState<boolean>(() => sound.isMuted());
  const [showQuitConfirm, setShowQuitConfirm] = useState(false);
  // Set locally the moment this player confirms quitting, so the
  // "you're out" message can say "you left" rather than the
  // punishment-forfeit wording below — the server only tracks
  // eliminated-or-not, not why, so this distinction has to live
  // client-side.
  const [voluntarilyLeft, setVoluntarilyLeft] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  // Bumped for every chat message that arrives while the panel is
  // closed, shown as a badge on the toggle button; cleared the moment
  // the panel opens. Tracked separately from chatMessages.length so a
  // full history replay (there isn't one today, but future-proofing)
  // wouldn't spuriously count as "unread".
  const [unreadChatCount, setUnreadChatCount] = useState(0);
  const lastSeenChatCount = useRef(0);
  // Plays once, right when the table first mounts for a freshly
  // started game — a plain useState(true) rather than anything tied
  // to `status`, so a mid-game reconnect never replays it. Leaving
  // and rejoining a fresh game remounts Table entirely, which is
  // exactly when it should play again.
  const [showShuffle, setShowShuffle] = useState(true);
  // Bumped once per card_played batch — used purely as a React `key`
  // on the discard pile's top card so it remounts (and its landing
  // animation replays) every time, rather than tracking a separate
  // "is animating" boolean.
  const [landingPulse, setLandingPulse] = useState(0);
  // Same remount-key trick for the draw-pressure counter, plus a
  // magnitude so a bigger jump (e.g. a stacked Joker) visibly pulses
  // harder than a lone 2.
  const [pressurePulse, setPressurePulse] = useState(0);
  const [pressureDelta, setPressureDelta] = useState(1);
  const prevPendingDrawRef = useRef(0);
  // Whether the legal-card glow (see legality.ts) is allowed to show
  // yet. Deliberately withheld for a few seconds at the start of
  // every new decision, so the UI doesn't hand over the answer the
  // instant it becomes your turn — a moment to actually look at your
  // hand and think, not just react to what's lit up.
  const [hintsRevealed, setHintsRevealed] = useState(false);
  // A queue rather than a single value — declarations are rare but
  // not impossible to overlap (two players could each go down to one
  // card close together), and each one deserves its own full,
  // unmissable moment rather than getting stomped by the next. Table
  // shows only the front of the queue at a time; NikoKadiBanner pops
  // it once its own timer finishes (see NikoKadiBanner.tsx).
  const [nikoKadiQueue, setNikoKadiQueue] = useState<
    { key: number; playerId: string }[]
  >([]);
  const nikoKadiKeyRef = useRef(0);

  // Core-moment sound effects, driven straight off the same event
  // batch the EventLog renders — see sound.ts for what's covered
  // (deliberately not everything, to avoid constant noise) and why
  // this is safe to fire on every lastEvents change: the server only
  // ever sends the events from the action that just happened, never
  // history (a fresh connection starts with events: []), so this
  // never replays sounds for a game already in progress.
  useEffect(() => {
    // A punishment draw and a normal/voluntary draw both produce a
    // "cards_drawn" event with the same shape — the only thing that
    // tells them apart is a companion "draw_stack_cleared" event in
    // the same batch, which the engine only emits when the draw
    // resolved an active draw-pressure stack (see
    // engine._draw_cards_for_player). Checked once per batch rather
    // than per-event since it's a property of the whole batch, not
    // any single event.
    const wasPunishmentDraw = lastEvents.some(
      (event) => event.type === "draw_stack_cleared",
    );

    for (const event of lastEvents) {
      switch (event.type) {
        case "card_played":
          sound.playCardPlayed();
          setLandingPulse((prev) => prev + 1);
          break;

        case "cards_drawn":
          if (wasPunishmentDraw) {
            sound.playPunishmentDraw();
          } else {
            sound.playNormalDraw();
          }
          break;

        case "turn_advanced":
          if (event.payload.current_player_id === playerId) {
            sound.playYourTurn();
          }
          break;

        case "player_won":
          if (event.payload.player_id === playerId) {
            sound.playWin();
          } else {
            sound.playLose();
          }
          break;

        case "niko_kadi_declared":
          sound.playNikoKadi();
          nikoKadiKeyRef.current += 1;
          setNikoKadiQueue((queue) => [
            ...queue,
            {
              key: nikoKadiKeyRef.current,
              playerId: String(event.payload.player_id),
            },
          ]);
          break;

        case "game_started":
          // A fresh round (see GameRoom.restart) re-seats every
          // player with no one eliminated — but "I voluntarily
          // forfeited last round" is tracked client-side only (the
          // server just knows eliminated-or-not, not why), so
          // without this it would stay stuck true forever and hide
          // the Forfeit Match button in every round after the first
          // one this player ever forfeited.
          setVoluntarilyLeft(false);
          break;

        default:
          break;
      }
    }
  }, [lastEvents, playerId]);

  // Tracks how many chat messages have arrived since the panel was
  // last open, so the toggle button can show an unread badge without
  // the panel itself needing to be mounted while closed.
  useEffect(() => {
    if (chatOpen) {
      lastSeenChatCount.current = chatMessages.length;
      setUnreadChatCount(0);
      return;
    }

    if (chatMessages.length > lastSeenChatCount.current) {
      setUnreadChatCount(chatMessages.length - lastSeenChatCount.current);
    }
  }, [chatMessages.length, chatOpen]);

  // Fires whenever draw pressure actually goes UP (a 2/3/Joker got
  // stacked on) — never on a decrease (someone drew/countered), since
  // this is meant to telegraph a punishment growing, not every change.
  // Declared unconditionally (before the early returns below) per the
  // Rules of Hooks; `state` can still be null here on first render.
  useEffect(() => {
    const next = room?.state?.pending_draw_count ?? 0;
    const prev = prevPendingDrawRef.current;
    if (next > prev) {
      setPressureDelta(Math.max(1, Math.min(next - prev, 6)));
      setPressurePulse((count) => count + 1);
    }
    prevPendingDrawRef.current = next;
  }, [room?.state?.pending_draw_count]);

  // Starts (or restarts) a 3-second "thinking window" every time a
  // new decision begins for this player — a fresh turn, a phase
  // change mid-turn (e.g. you play a question card and immediately
  // owe an answer), or your hand changing size (you just drew).
  // Hints stay hidden for the whole window; only once it elapses does
  // the legal-play glow (see legality.ts) get allowed to show at all.
  // Gated on !showShuffle too — the underlying room state (and this
  // player's turn) can already be live while the shuffle animation is
  // still playing, and that animation isn't thinking time, so the
  // countdown shouldn't secretly burn down while the hand is still
  // hidden behind it. Declared unconditionally, before the early
  // returns below, per the Rules of Hooks — every value it reads is
  // read via optional chaining since `state` can still be null here.
  useEffect(() => {
    const isMyTurnNow = room?.state?.current_player === playerId;

    setHintsRevealed(false);

    if (!isMyTurnNow || showShuffle) {
      return;
    }

    const timer = setTimeout(() => setHintsRevealed(true), 3000);
    return () => clearTimeout(timer);
  }, [
    playerId,
    room?.state?.current_player,
    room?.state?.phase,
    room?.state?.my_hand.length,
    showShuffle,
  ]);

  const state = room?.state ?? null;

  if (showShuffle) {
    return (
      <div className="table">
        <ShuffleOverlay onDone={() => setShowShuffle(false)} />
      </div>
    );
  }

  if (status === "connecting" && !room) {
    return (
      <div className="status-line">
        <p>Connecting…</p>
        <button className="leave-link" onClick={onLeave}>
          Leave game
        </button>
      </div>
    );
  }

  if (status === "closed" && !room) {
    return (
      <div className="status-line">
        <p className="error">
          Couldn't reach the game (the server may have restarted).
        </p>
        <button className="leave-link" onClick={onLeave}>
          Leave game
        </button>
      </div>
    );
  }

  if (!state) {
    return <p className="status-line">Waiting for game state…</p>;
  }

  const isMyTurn = state.current_player === playerId;

  // Deliberately NOT sorted by hand position — a Set already preserves
  // insertion order in JS, so this keeps cards in the order the player
  // actually clicked them (and re-clicking a card after deselecting it
  // moves it to the end, as the most recently chosen).
  const selectedCards = [...selectedIndices]
    .map((index) => state.my_hand[index])
    .filter((card): card is CardView => card !== undefined);

  // Playing the current selection would leave exactly one card in
  // hand — Niko Kadi must be declared with this play.
  const willDeclareNikoKadi =
    selectedCards.length > 0 &&
    state.my_hand.length - selectedCards.length === 1;

  const commitPlay = (declaredSuit?: Suit) => {
    if (selectedCards.length === 0) {
      return;
    }

    send({
      type: "play_cards",
      cards: selectedCards.map((card) => ({
        rank: card.rank,
        suit: card.suit,
        joker_color: card.joker_color,
      })),
      declared_suit: declaredSuit ?? null,
      declare_niko_kadi: willDeclareNikoKadi,
    });
    setSelectedIndices(new Set());
    setPendingCards(null);
  };

  const handlePlayClick = () => {
    // The suit picker only makes sense when the Ace is being played
    // offensively, on a normal turn — countering a pending
    // question/draw/skip with it is reactive and doesn't grant the
    // "declare the next suit" power (see engine._apply_ace_effect),
    // so there's nothing to ask for in those phases.
    const isOffensiveTurn = state.phase === "awaiting_move";

    if (
      isOffensiveTurn &&
      selectedCards.some((card) => WILD_RANKS.has(card.rank))
    ) {
      setPendingCards(selectedCards);
    } else {
      commitPlay();
    }
  };

  const toggleCardSelection = (index: number) => {
    if (!isMyTurn) {
      return;
    }

    setSelectedIndices((prev) => {
      if (prev.has(index)) {
        const next = new Set(prev);
        next.delete(index);
        return next;
      }

      const [firstSelected] = prev;
      const selectedRank =
        firstSelected !== undefined
          ? state.my_hand[firstSelected]?.rank
          : undefined;
      const clickedRank = state.my_hand[index]?.rank;

      // A different rank than what's already selected starts a fresh
      // selection instead of mixing ranks (the server would reject
      // that anyway — this just avoids the round trip).
      if (selectedRank && clickedRank !== selectedRank) {
        return new Set([index]);
      }

      return new Set(prev).add(index);
    });
  };

  const opponents = state.players.filter((player) => player.id !== playerId);
  const me = state.players.find((player) => player.id === playerId);
  const winner = state.players.find((player) => player.id === state.winner_id);
  const currentPlayer = state.players.find(
    (player) => player.id === state.current_player,
  );

  // "In tension" = declared Niko Kadi AND still actually holding just
  // the one card — has_declared_niko_kadi alone can go stale (the
  // engine never un-sets it if a punishment draw pushes them back up
  // to a full hand), so card_count is what keeps this accurate.
  const isInNikoKadiTension = (player: (typeof state.players)[number]) =>
    player.has_declared_niko_kadi &&
    player.card_count === 1 &&
    !player.is_eliminated;

  const anyoneInNikoKadiTension = state.players.some(isInNikoKadiTension);

  const nextUpPlayerId =
    state.phase === "awaiting_move" ? computeNextUpPlayerId(state) : null;

  const canQuit =
    state.phase !== "finished" && !me?.is_eliminated && !voluntarilyLeft;

  const confirmQuit = () => {
    send({ type: "quit" });
    setVoluntarilyLeft(true);
    setShowQuitConfirm(false);
  };

  const sendChat = (text: string) => {
    send({ type: "chat", text });
  };

  return (
    <div
      className={
        anyoneInNikoKadiTension ? "table niko-kadi-ambient" : "table"
      }
    >
      {nikoKadiQueue[0] && (
        <NikoKadiBanner
          key={nikoKadiQueue[0].key}
          playerId={nikoKadiQueue[0].playerId}
          playerName={nameOfPlayer(state, nikoKadiQueue[0].playerId)}
          onDone={() =>
            setNikoKadiQueue((queue) => queue.slice(1))
          }
        />
      )}

      <div className="table-topbar">
        {canQuit && (
          <button
            type="button"
            className="forfeit-link"
            onClick={() => setShowQuitConfirm(true)}
            title="Forfeit the match — you'll lose immediately"
          >
            🏳️ Forfeit Match
          </button>
        )}
        <button
          type="button"
          className="chat-toggle"
          onClick={() => setChatOpen((prev) => !prev)}
          aria-label={chatOpen ? "Close chat" : "Open chat"}
          title={chatOpen ? "Close chat" : "Open chat"}
        >
          💬
          {!chatOpen && unreadChatCount > 0 && (
            <span className="chat-badge">
              {unreadChatCount > 9 ? "9+" : unreadChatCount}
            </span>
          )}
        </button>
        <button
          type="button"
          className="sound-toggle"
          onClick={() => setMuted(sound.toggleMuted())}
          aria-label={muted ? "Unmute sound" : "Mute sound"}
          title={muted ? "Unmute sound" : "Mute sound"}
        >
          {muted ? "🔇" : "🔊"}
        </button>
      </div>

      <div className="table-divider" aria-hidden="true" />

      {status === "closed" && (
        <div className="connection-banner">
          <p>Connection lost (the server may have restarted).</p>
          <button className="leave-link" onClick={onLeave}>
            Leave game
          </button>
        </div>
      )}

      <OpponentPanel
        opponents={opponents}
        nextUpPlayerId={nextUpPlayerId}
        isInTension={isInNikoKadiTension}
      />

      <Scoreboard scoreboard={room?.scoreboard ?? []} />

      <div className="board">
        <CurrentCard
          topCard={state.top_card}
          activeSuit={state.active_suit}
          requiredSuit={state.required_suit}
          drawPileCount={state.draw_pile_count}
          landingPulse={landingPulse}
        />

        <div className="table-status" aria-live="polite">
          {state.phase === "finished" ? (
            <>
              <p className="winner">
                {state.winner_id === playerId ? (
                  "You won! 🎉"
                ) : (
                  <>
                    <span style={winner ? { color: colorForPlayer(winner.id) } : undefined}>
                      {winner?.name ?? "A player"}
                    </span>{" "}
                    won.
                  </>
                )}
              </p>
              {/* Any player who was ever seated in this room can start
                  a fresh round now — not just the winner (see
                  GameRoom.restart). A round often ends because someone
                  forfeited rather than because anyone actually chose
                  to stop, so nobody should be stuck waiting on a
                  single player to click a button. */}
              <button
                type="button"
                className="play-again"
                onClick={() => send({ type: "restart" })}
              >
                {state.winner_id === playerId
                  ? "Play again"
                  : "Start new game"}
              </button>
            </>
          ) : me?.is_eliminated ? (
            <p className="hint">
              {voluntarilyLeft
                ? "You left the game. Watching the rest of the game play out."
                : `You were eliminated for reaching ${
                    me.card_count === 0 ? "too many" : me.card_count
                  } cards from an unavoidable draw. Watching the rest of the game play out.`}
            </p>
          ) : (
            <>
              <p className={isMyTurn ? "turn-status my-turn" : "turn-status"}>
                {isMyTurn ? (
                  "Your turn"
                ) : (
                  <>
                    Waiting on{" "}
                    <span
                      style={
                        currentPlayer
                          ? { color: colorForPlayer(currentPlayer.id) }
                          : undefined
                      }
                    >
                      {currentPlayer?.name ?? "…"}
                    </span>
                  </>
                )}
              </p>
              {isMyTurn && state.phase === "awaiting_move" && (
                <p className="hint">Draw a card or play from your hand</p>
              )}
              {state.phase === "awaiting_draw_response" && (
                <p
                  key={pressurePulse}
                  className="hint draw-pressure-pulse"
                  style={
                    {
                      "--pulse-scale": 1 + pressureDelta * 0.06,
                    } as CSSProperties
                  }
                >
                  Draw pressure: {state.pending_draw_count}
                </p>
              )}
              {state.phase === "awaiting_skip_response" && (
                <p className="hint">Skip pending</p>
              )}
              {state.phase === "awaiting_answer" && (
                <p className="hint">A question was asked</p>
              )}
            </>
          )}
        </div>

        <DrawButton
          phase={state.phase}
          isMyTurn={isMyTurn}
          pendingDrawCount={state.pending_draw_count}
          onDraw={() => send({ type: "draw" })}
          onPass={() => send({ type: "pass" })}
        />
      </div>

      <div
        className={
          me && isInNikoKadiTension(me) ? "my-hand niko-kadi-tension" : "my-hand"
        }
      >
        <p className="hand-label">
          <span style={me ? { color: colorForPlayer(me.id) } : undefined}>
            {me?.name ?? "You"}
          </span>{" "}
          ({state.my_hand.length} card
          {state.my_hand.length === 1 ? "" : "s"})
          {me && isInNikoKadiTension(me) && (
            <span className="tension-badge" title="You declared Niko Kadi">
              {" "}
              ✋
            </span>
          )}
          <span
            className="hand-info-icon"
            title="Same-rank cards play together. Take a moment — after a few seconds, a playable card will glow, but it's just a hint, not the only right answer."
          >
            ⓘ
          </span>
        </p>
        {!isMyTurn && me?.id === nextUpPlayerId && (
          <p className="hint up-next-hint">You're up next</p>
        )}
        <div className="hand-cards">
          {state.my_hand.map((card, index) => (
            <PlayingCard
              key={`${card.rank}-${card.suit ?? card.joker_color ?? "none"}-${index}`}
              card={card}
              disabled={!isMyTurn}
              selected={selectedIndices.has(index)}
              legal={
                isMyTurn && hintsRevealed && isCardLegal(card, state)
                  ? true
                  : undefined
              }
              onClick={() => toggleCardSelection(index)}
            />
          ))}
        </div>
        {isMyTurn && selectedCards.length > 0 && (
          <div className="selection-bar">
            <p className="hint">
              {selectedCards.length === 1
                ? "1 card selected"
                : `${selectedCards.length} cards selected (same rank, played together)`}
              {willDeclareNikoKadi && " — this will declare \"Niko Kadi\""}
            </p>
            <div className="selection-actions">
              <button type="button" onClick={handlePlayClick}>
                Play {selectedCards.length === 1 ? "card" : `${selectedCards.length} cards`}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setSelectedIndices(new Set())}
              >
                Clear
              </button>
            </div>
          </div>
        )}
        {isMyTurn && selectedCards.length === 0 && (
          <p className="hint">
            Tap a card to select it — tap more of the same rank to play
            them together.
          </p>
        )}
      </div>

      <EventLog entries={eventHistory} players={state.players} />

      {error && <p className="error toast">{error}</p>}

      {pendingCards && (
        <SuitPicker
          onPick={(suit) => commitPlay(suit)}
          onCancel={() => setPendingCards(null)}
        />
      )}

      {showQuitConfirm && (
        <QuitConfirm
          onConfirm={confirmQuit}
          onCancel={() => setShowQuitConfirm(false)}
        />
      )}

      <ChatPanel
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        messages={chatMessages}
        playerId={playerId}
        onSend={sendChat}
      />
    </div>
  );
}
