from typing import Optional

from pydantic import BaseModel

class DrawRequest(BaseModel):
    player_id: str
    
class PassRequest(BaseModel):
    player_id: str


class PlayCardRequest(BaseModel):
    player_id: str

    rank: str

    suit: Optional[str] = None

    declared_suit: Optional[str] = None

    declare_niko_kadi: bool = False

class CreateRoomResponse(BaseModel):
    room_id: str


class JoinRoomRequest(BaseModel):
    player_id: str
    player_name: str


class StartGameResponse(BaseModel):
    started: bool
    event_count: int
    current_player: str
    
    
    
    
    