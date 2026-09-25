"""
Room Manager

Responsible for:

- Creating rooms
- Finding rooms
- Removing rooms
- Tracking active games

No networking code here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .room import GameRoom, create_room
from app.rules.config import RuleConfig

# Room codes are short (see room.generate_room_code) precisely so
# they're easy to read aloud/type — short enough that, across many
# concurrent rooms, an accidental collision becomes plausible. This
# manager is the one place that actually knows every code already in
# use, so it's the one place that can regenerate on a collision.
_MAX_CODE_GENERATION_ATTEMPTS = 25


def _normalize(room_id: str) -> str:
    """
    Codes are generated upper-case (see room.generate_room_code).
    Someone typing a code in by hand — on a phone, off a whiteboard —
    shouldn't get "room not found" just for using lowercase, so every
    lookup normalizes the same way the codes were generated.
    """

    return room_id.strip().upper()


@dataclass
class RoomManager:
    rooms: dict[str, GameRoom] = field(default_factory=dict)

    # ---------------------------------------------------------
    # Room Lifecycle
    # ---------------------------------------------------------

    def create_room(
        self,
        rules: RuleConfig | None = None,
    ) -> GameRoom:

        room = create_room(rules=rules)

        attempts = 1
        while room.room_id in self.rooms and attempts < _MAX_CODE_GENERATION_ATTEMPTS:
            room = create_room(rules=rules)
            attempts += 1

        if room.room_id in self.rooms:
            raise RuntimeError(
                "Could not generate a free room code — too many active rooms."
            )

        self.rooms[room.room_id] = room

        return room

    def get_room(
        self,
        room_id: str,
    ) -> GameRoom:

        room_id = _normalize(room_id)

        if room_id not in self.rooms:
            raise KeyError(f"Room not found: {room_id}")

        return self.rooms[room_id]

    def room_exists(
        self,
        room_id: str,
    ) -> bool:

        return _normalize(room_id) in self.rooms

    def remove_room(
        self,
        room_id: str,
    ) -> None:

        room_id = _normalize(room_id)

        if room_id in self.rooms:
            del self.rooms[room_id]

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------

    def active_room_count(self) -> int:
        return len(self.rooms)

    def clear(self) -> None:
        self.rooms.clear()