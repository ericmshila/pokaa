/**
 * REST client for room/lobby actions.
 *
 * Live gameplay (play/draw/pass) happens over the WebSocket — see
 * useGameSocket.ts. This module only covers create/join/start/inspect,
 * which mirror app/api/routes.py on the backend.
 */

import type { RoomPlayerSummary } from "./types";

// Same-machine setup (localhost, a LAN IP, or a Hamachi/Tailscale
// virtual IP) all work with zero config: whatever host the browser
// used to load this page is also where the backend lives, since both
// are started on the same machine. Set VITE_API_BASE_URL in
// .env.local only if the backend runs somewhere else.
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  `${window.location.protocol}//${window.location.hostname}:8000`;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export interface CreateRoomResponse {
  room_id: string;
}

export function createRoom(): Promise<CreateRoomResponse> {
  return request<CreateRoomResponse>("/api/rooms", { method: "POST" });
}

export interface JoinRoomResponse {
  room_id: string;
  player_count: number;
}

export function joinRoom(
  roomId: string,
  playerId: string,
  playerName: string,
): Promise<JoinRoomResponse> {
  return request<JoinRoomResponse>(`/api/rooms/${roomId}/join`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, player_name: playerName }),
  });
}

export interface StartGameResponse {
  started: boolean;
  event_count: number;
  current_player: string;
}

export function startGame(roomId: string): Promise<StartGameResponse> {
  return request<StartGameResponse>(`/api/rooms/${roomId}/start`, {
    method: "POST",
  });
}

export interface RoomSummary {
  room_id: string;
  player_count: number;
  started: boolean;
  players: RoomPlayerSummary[];
}

export function getRoom(roomId: string): Promise<RoomSummary> {
  return request<RoomSummary>(`/api/rooms/${roomId}`);
}
