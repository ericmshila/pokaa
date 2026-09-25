"""
Application-level shared dependencies.

For MVP we keep a single in-memory RoomManager and a single
ConnectionManager, shared by the REST routes and the WebSocket route.
"""

from app.game.connection_manager import ConnectionManager
from app.game.room_manager import RoomManager

room_manager = RoomManager()
connection_manager = ConnectionManager()