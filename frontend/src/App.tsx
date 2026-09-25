import { useState } from "react";
import { Lobby } from "./components/Lobby";
import { Table } from "./components/Table";
import "./App.css";

const PLAYER_ID_KEY = "kenyan-poker:player-id";
const PLAYER_NAME_KEY = "kenyan-poker:player-name";
const SESSION_KEY = "kenyan-poker:session";

interface Session {
  roomId: string;
  playerName: string;
}

// crypto.randomUUID() only exists in "secure contexts" (https:// or
// localhost) — a plain http:// LAN/Hamachi/Tailscale address doesn't
// qualify, and the call throws there. crypto.getRandomValues() has
// no such restriction, so build a v4 UUID from that when randomUUID
// isn't available; if even that's missing, fall back to a
// non-cryptographic id (fine for a casual game room's identity).
function generateId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
    return [
      hex.slice(0, 4).join(""),
      hex.slice(4, 6).join(""),
      hex.slice(6, 8).join(""),
      hex.slice(8, 10).join(""),
      hex.slice(10, 16).join(""),
    ].join("-");
  }

  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getOrCreatePlayerId(): string {
  const existing = sessionStorage.getItem(PLAYER_ID_KEY);
  if (existing) {
    return existing;
  }

  const id = generateId();
  sessionStorage.setItem(PLAYER_ID_KEY, id);
  return id;
}

// Kept separately from Session so a name typed once survives leaving
// a room — Session is cleared on leave, but re-typing your name every
// time you get bounced back to the join screen is just friction.
function readStoredPlayerName(): string {
  return sessionStorage.getItem(PLAYER_NAME_KEY) ?? "";
}

function storePlayerName(name: string): void {
  sessionStorage.setItem(PLAYER_NAME_KEY, name);
}

function readStoredSession(): Session | null {
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

function storeSession(session: Session | null): void {
  if (session) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } else {
    sessionStorage.removeItem(SESSION_KEY);
  }
}

export default function App() {
  const [playerId] = useState<string>(getOrCreatePlayerId);
  const [session, setSession] = useState<Session | null>(readStoredSession);
  const [playerName, setPlayerName] = useState<string>(readStoredPlayerName);
  const [gameStarted, setGameStarted] = useState<boolean>(false);

  const handleJoined = (roomId: string, name: string) => {
    const next = { roomId, playerName: name };
    setSession(next);
    storeSession(next);
    setPlayerName(name);
    storePlayerName(name);
  };

  const handleGameStart = (roomId: string, name: string) => {
    const next = { roomId, playerName: name };
    setSession(next);
    storeSession(next);
    setPlayerName(name);
    storePlayerName(name);
    setGameStarted(true);
  };

  // Clears the persisted room pairing (but keeps the player's name).
  // Used to escape a stale room — e.g. the backend restarted and
  // lost its in-memory rooms, so this browser tab is stuck polling a
  // room that no longer exists — or to back out of a dead WebSocket
  // connection to rejoin cleanly.
  const handleLeave = () => {
    setSession(null);
    storeSession(null);
    setGameStarted(false);
  };

  if (session && gameStarted) {
    return (
      <div className="app">
        <Table
          roomId={session.roomId}
          playerId={playerId}
          onLeave={handleLeave}
        />
      </div>
    );
  }

  return (
    <div className="app">
      <Lobby
        playerId={playerId}
        initialRoomId={session?.roomId ?? null}
        initialPlayerName={session?.playerName ?? playerName}
        onJoined={handleJoined}
        onGameStart={handleGameStart}
        onLeave={handleLeave}
      />
    </div>
  );
}
