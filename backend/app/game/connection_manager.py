"""
WebSocket connection manager.

Keeps track of connected players per room.

No game rules live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import WebSocket


@dataclass
class ConnectionManager:
    active_connections: dict[str, dict[str, WebSocket]] = field(
        default_factory=dict
    )

    async def connect(
        self,
        room_id: str,
        player_id: str,
        websocket: WebSocket,
    ) -> None:

        await websocket.accept()

        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}

        self.active_connections[room_id][player_id] = websocket

    def disconnect(
        self,
        room_id: str,
        player_id: str,
    ) -> None:

        if room_id not in self.active_connections:
            return

        self.active_connections[room_id].pop(
            player_id,
            None,
        )

        if not self.active_connections[room_id]:
            self.active_connections.pop(
                room_id,
                None,
            )

    async def send_to_player(
        self,
        room_id: str,
        player_id: str,
        message: dict,
    ) -> None:

        websocket = (
            self.active_connections
            .get(room_id, {})
            .get(player_id)
        )

        if websocket is None:
            return

        await websocket.send_json(message)

    async def broadcast_to_room(
        self,
        room_id: str,
        message: dict,
        exclude_player_id: str | None = None,
    ) -> None:

        connections = self.active_connections.get(room_id, {})

        for player_id, websocket in connections.items():
            if exclude_player_id is not None and player_id == exclude_player_id:
                continue

            await websocket.send_json(message)

    def connected_player_count(
        self,
        room_id: str,
    ) -> int:

        return len(
            self.active_connections.get(room_id, {})
        )