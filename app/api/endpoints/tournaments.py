from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.services import tournament_service, auth_service
from app.models import user as user_model
from app.schemas import tournament_schemas, participant_schemas
from app.api.dependencies import get_db

router = APIRouter()

@router.post("/", response_model=tournament_schemas.TournamentRead, status_code=status.HTTP_201_CREATED)
async def create_tournament_endpoint(
    tournament_in: tournament_schemas.TournamentCreate,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    tournament = tournament_service.create_tournament(db=db, tournament=tournament_in, creator_id=current_user.id)
    return tournament

@router.get("/", response_model=List[tournament_schemas.TournamentRead])
async def get_user_tournaments_endpoint(
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    tournaments = tournament_service.get_user_tournaments(db=db, user_id=current_user.id)
    return tournaments

@router.get("/{tournament_id}", response_model=tournament_schemas.TournamentRead)
async def get_tournament_endpoint(
    tournament_id: int,
    db: Session = Depends(get_db),
    # current_user: user_model.User = Depends(auth_service.get_current_user), # Optional: if details are private
):
    tournament = tournament_service.get_tournament(db=db, tournament_id=tournament_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return tournament

@router.put("/{tournament_id}", response_model=tournament_schemas.TournamentRead)
async def update_tournament_endpoint(
    tournament_id: int,
    tournament_in: tournament_schemas.TournamentUpdate,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    updated_tournament = tournament_service.update_tournament(
        db=db, tournament_id=tournament_id, tournament_update=tournament_in, current_user_id=current_user.id
    )
    if not updated_tournament: # Should be handled by service raising 404, but good practice
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found or not updated")
    return updated_tournament

@router.delete("/{tournament_id}", response_model=Dict[str, str])
async def delete_tournament_endpoint(
    tournament_id: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    success = tournament_service.delete_tournament(db=db, tournament_id=tournament_id, current_user_id=current_user.id)
    if not success: # Should be handled by service raising 404/403
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found or deletion failed")
    return {"message": "Tournament deleted successfully"}

@router.post("/{tournament_id}/invite", response_model=Dict[str, str])
async def generate_invite_link_endpoint(
    tournament_id: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    invite_token = tournament_service.generate_invite_link(db=db, tournament_id=tournament_id, current_user_id=current_user.id)
    if not invite_token: # Service raises exceptions if not found or unauthorized
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not generate invite token")
    return {"invite_token": invite_token}

@router.post("/join/{invite_token}", response_model=participant_schemas.ParticipantRead)
async def join_tournament_with_invite_endpoint(
    invite_token: str,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    participant = tournament_service.join_tournament_with_invite(db=db, invite_token=invite_token, user_id=current_user.id)
    if not participant: # Service raises exceptions
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not join tournament")
    return participant

@router.get("/{tournament_id}/players", response_model=List[participant_schemas.ParticipantRead])
async def list_participants_endpoint( # Function name can remain list_participants_endpoint
    tournament_id: int,
    db: Session = Depends(get_db),
):
    participants = tournament_service.list_participants(db=db, tournament_id=tournament_id)
    return participants

@router.patch("/{tournament_id}/players/{user_id}", response_model=participant_schemas.ParticipantRead)
async def update_participant_status_endpoint( # Function name can remain
    tournament_id: int,
    user_id: int, # This is the user_id of the participant whose status is being changed
    participant_in: participant_schemas.ParticipantUpdate,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user), # This is the tournament creator
):
    updated_participant = tournament_service.update_participant_status(
        db=db,
        tournament_id=tournament_id,
        participant_user_id=user_id,
        participant_update=participant_in,
        current_user_id=current_user.id
    )
    if not updated_participant: # Service raises exceptions
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not update participant status")
    return updated_participant
