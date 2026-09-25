import { useEffect, useState } from "react";
import { createRoom, getRoom, joinRoom, startGame } from "../api";
import type { RoomSummary } from "../api";

function initialOf(name: string): string {
  return name.trim().charAt(0).toUpperCase() || "?";
}

interface LobbyProps {
  playerId: string;
  initialRoomId: string | null;
  initialPlayerName: string;
  onJoined: (roomId: string, playerName: string) => void;
  onGameStart: (roomId: string, playerName: string) => void;
  onLeave: () => void;
}

export function Lobby({
  playerId,
  initialRoomId,
  initialPlayerName,
  onJoined,
  onGameStart,
  onLeave,
}: LobbyProps) {
  const [playerName, setPlayerName] = useState(initialPlayerName);
  const [roomIdInput, setRoomIdInput] = useState("");
  const [joinedRoomId, setJoinedRoomId] = useState<string | null>(
    initialRoomId,
  );
  const [summary, setSummary] = useState<RoomSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!joinedRoomId) {
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const data = await getRoom(joinedRoomId);
        if (!cancelled) {
          setSummary(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message);
        }
      }
    };

    void poll();
    const interval = window.setInterval(() => void poll(), 1500);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [joinedRoomId]);

  useEffect(() => {
    if (summary?.started && joinedRoomId) {
      onGameStart(joinedRoomId, playerName);
    }
  }, [summary, joinedRoomId, playerName, onGameStart]);

  const handleCreate = async () => {
    if (!playerName.trim()) {
      setError("Enter your name first.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const { room_id: roomId } = await createRoom();
      await joinRoom(roomId, playerId, playerName.trim());
      setJoinedRoomId(roomId);
      onJoined(roomId, playerName.trim());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleJoin = async () => {
    if (!playerName.trim() || !roomIdInput.trim()) {
      setError("Enter your name and a room code.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const roomId = roomIdInput.trim();
      await joinRoom(roomId, playerId, playerName.trim());
      setJoinedRoomId(roomId);
      onJoined(roomId, playerName.trim());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleStart = async () => {
    if (!joinedRoomId) {
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await startGame(joinedRoomId);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // Resets this component's own local state back to the create/join
  // form and clears the persisted session (App.tsx). Needed because
  // the backend keeps rooms in memory only — if it restarts, every
  // room code still sitting in a browser tab's storage points at
  // nothing, and without this there's no way back to the form short
  // of manually clearing site data.
  const handleLeave = () => {
    setJoinedRoomId(null);
    setSummary(null);
    setError(null);
    setRoomIdInput("");
    onLeave();
  };

  if (joinedRoomId) {
    const playerCount = summary?.player_count ?? 0;
    const roomMissing = error === "Room not found";

    return (
      <div className="lobby">
        <h2>Waiting room</h2>
        <p>Share this room code with the other players:</p>
        <code className="room-code">{joinedRoomId}</code>

        <ul className="player-list">
          {(summary?.players ?? []).map((player) => (
            <li key={player.id}>
              <span className="avatar">{initialOf(player.name)}</span>
              {player.name}
              {player.id === playerId && (
                <span className="you-badge">You</span>
              )}
            </li>
          ))}
        </ul>

        {!roomMissing && (
          <p className="hint">
            {playerCount} player{playerCount === 1 ? "" : "s"} joined
            {playerCount < 2 ? " — need at least 2 to start." : "."}
          </p>
        )}

        {roomMissing ? (
          <p className="error">
            This room no longer exists on the server (it may have
            restarted). Leave and start a new one.
          </p>
        ) : (
          <button
            disabled={busy || playerCount < 2}
            onClick={() => void handleStart()}
          >
            Start game
          </button>
        )}

        {error && !roomMissing && <p className="error">{error}</p>}

        <button className="leave-link" onClick={handleLeave}>
          Leave room
        </button>
      </div>
    );
  }

  return (
    <div className="lobby">
      <h1>Kenyan Poker (Kadi)</h1>

      <label className="field">
        Your name
        <input
          value={playerName}
          onChange={(event) => setPlayerName(event.target.value)}
          placeholder="e.g. Amina"
        />
      </label>

      <div className="lobby-actions">
        <button disabled={busy} onClick={() => void handleCreate()}>
          Create room
        </button>

        <div className="join-row">
          <input
            placeholder="Room code"
            value={roomIdInput}
            // Codes are generated upper-case; matching that as they
            // type makes it obvious the code they're copying down is
            // the one that'll actually match (the server also
            // normalizes case, so this is just for clarity).
            onChange={(event) =>
              setRoomIdInput(event.target.value.toUpperCase())
            }
          />
          <button disabled={busy} onClick={() => void handleJoin()}>
            Join room
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
    </div>
  );
}
