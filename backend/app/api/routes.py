from fastapi import APIRouter, HTTPException

from app import db
from app.game.dependencies import room_manager
from app.game.game_results import maybe_record_game_result
from app.game.serializers import serialize_scoreboard

from app.rules.state import Player
from app.api.schemas import (
    CreateRoomResponse,
    JoinRoomRequest,
    StartGameResponse,
    PlayCardRequest,
    DrawRequest,
    PassRequest,
)

from app.rules.actions import (
    ActionType,
    PlayCardsAction,
    DrawAction,
    PassAction,
)

from app.rules.cards import (
    Card,
    Rank,
    Suit,
)

from app.rules.engine import IllegalMove


router = APIRouter(
    prefix="/api",
    tags=["rooms"],
)


@router.get("/health")
def health():
    return {
        "status": "ok"
    }


@router.post(
    "/rooms",
    response_model=CreateRoomResponse,
)
def create_room():

    room = room_manager.create_room()

    return CreateRoomResponse(
        room_id=room.room_id,
    )


@router.get("/rooms/{room_id}")
def get_room(room_id: str):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    return {
        "room_id": room.room_id,
        "player_count": len(room.players),
        "started": room.started,
        "players": [
            {"id": player.id, "name": player.name}
            for player in room.players
        ],
        "scoreboard": serialize_scoreboard(room, db.get_scoreboard(room_id)),
    }

@router.post("/rooms/{room_id}/join")
def join_room(
    room_id: str,
    payload: JoinRoomRequest,
):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    already_seated = any(
        player.id == payload.player_id for player in room.players
    )

    if not already_seated:
        try:
            room.add_player(
                Player(
                    id=payload.player_id,
                    name=payload.player_name,
                )
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

    return {
        "room_id": room.room_id,
        "player_count": len(room.players),
        "already_seated": already_seated,
    }
    
@router.post(
    "/rooms/{room_id}/start",
    response_model=StartGameResponse,
)
def start_game(room_id: str):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    try:
        events = room.start_game()

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return StartGameResponse(
        started=True,
        event_count=len(events),
        current_player=room.state.current_player.id,
    )
    
@router.get("/rooms/{room_id}/state")
def get_game_state(room_id: str):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    if room.state is None:
        raise HTTPException(
            status_code=400,
            detail="Game has not started",
        )

    return {
        "current_player": room.state.current_player.id,
        "phase": room.state.phase.value,
        "top_card": room.state.top_card.label(),
        "direction": room.state.direction,
        "winner_id": room.state.winner_id,
        "players": [
            {
                "id": player.id,
                "card_count": len(
                    room.state.hand_of(player.id)
                ),
                "is_eliminated": player.id in room.state.eliminated_player_ids,
            }
            for player in room.state.players
        ],
    }

@router.get("/rooms/{room_id}/debug")
def debug_room(room_id: str):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    if room.state is None:
        raise HTTPException(
            status_code=400,
            detail="Game has not started",
        )

    return {
        "room_id": room.room_id,
        "current_player": room.state.current_player.id,
        "phase": room.state.phase.value,
        "top_card": room.state.top_card.label(),
        "direction": room.state.direction,
        "winner_id": room.state.winner_id,
        "hands": {
            player.id: [
                card.label()
                for card in room.state.hand_of(player.id)
            ]
            for player in room.state.players
        },
        "draw_pile_count": len(room.state.draw_pile),
        "discard_pile_count": len(room.state.discard_pile),
        "pending_draw_count": room.state.pending_draw_count,
        "pending_question_player_id": room.state.pending_question_player_id,
        "pending_skip_player_id": room.state.pending_skip_player_id,
        "active_suit": (
            room.state.active_suit.value
            if room.state.active_suit
            else None
        ),
        "eliminated_player_ids": sorted(room.state.eliminated_player_ids),
    }

@router.post("/rooms/{room_id}/play")
def play_card(
    room_id: str,
    payload: PlayCardRequest,
):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    if room.state is None:
        raise HTTPException(
            status_code=400,
            detail="Game has not started",
        )

    try:
        card = Card(
            rank=Rank(payload.rank),
            suit=Suit(payload.suit)
            if payload.suit is not None
            else None,
        )

        declared_suit = (
            Suit(payload.declared_suit)
            if payload.declared_suit is not None
            else None
        )

        action = PlayCardsAction(
            player_id=payload.player_id,
            type=ActionType.PLAY_CARDS,
            cards=(card,),
            declared_suit=declared_suit,
            declare_niko_kadi=payload.declare_niko_kadi,
        )

        events = room.apply(action)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid card: {exc}",
        )

    except IllegalMove as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    maybe_record_game_result(room, room_id, events)

    return {
        "success": True,
        "event_count": len(events),
        "events": [
            {
                "type": event.type.value,
                "payload": event.payload,
            }
            for event in events
        ],
    }


@router.post("/rooms/{room_id}/draw")
def draw_card(
    room_id: str,
    payload: DrawRequest,
):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    if room.state is None:
        raise HTTPException(
            status_code=400,
            detail="Game has not started",
        )

    try:
        action = DrawAction(
            player_id=payload.player_id,
            type=ActionType.DRAW,
        )

        events = room.apply(action)

    except IllegalMove as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    maybe_record_game_result(room, room_id, events)

    return {
        "success": True,
        "event_count": len(events),
        "events": [
            {
                "type": event.type.value,
                "payload": event.payload,
            }
            for event in events
        ],
    }

@router.post("/rooms/{room_id}/pass")
def pass_turn(
    room_id: str,
    payload: PassRequest,
):

    try:
        room = room_manager.get_room(room_id)

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )

    if room.state is None:
        raise HTTPException(
            status_code=400,
            detail="Game has not started",
        )

    try:
        action = PassAction(
            player_id=payload.player_id,
            type=ActionType.PASS,
        )

        events = room.apply(action)

    except IllegalMove as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    maybe_record_game_result(room, room_id, events)

    return {
        "success": True,
        "event_count": len(events),
        "events": [
            {
                "type": event.type.value,
                "payload": event.payload,
            }
            for event in events
        ],
    }