from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.services import match_service, auth_service
from app.models import user as user_model
from app.schemas import match_schemas
from app.api.dependencies import get_db

router = APIRouter()

@router.post("/auto-generate/{tournament_id}", response_model=List[match_schemas.MatchRead], status_code=status.HTTP_201_CREATED)
async def auto_generate_matches_endpoint(
    tournament_id: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    matches = match_service.generate_matches_for_tournament(
        db=db, tournament_id=tournament_id, current_user_id=current_user.id
    )
    return matches

@router.get("/tournament/{tournament_id}", response_model=List[match_schemas.MatchRead])
async def get_tournament_matches_endpoint(
    tournament_id: int,
    db: Session = Depends(get_db),
    # current_user: user_model.User = Depends(auth_service.get_current_user), # Optional auth
):
    matches = match_service.get_tournament_matches(db=db, tournament_id=tournament_id)
    return matches

@router.get("/{match_id}", response_model=match_schemas.MatchRead)
async def get_match_details_endpoint(
    match_id: int,
    db: Session = Depends(get_db),
    # current_user: user_model.User = Depends(auth_service.get_current_user), # Optional auth
):
    match = match_service.get_match_details(db=db, match_id=match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return match

@router.post("/{match_id}/result", response_model=match_schemas.MatchRead)
async def submit_match_result_endpoint(
    match_id: int,
    result_in: match_schemas.MatchResultUpdate,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    updated_match = match_service.submit_match_result(
        db=db, match_id=match_id, result=result_in, current_user_id=current_user.id
    )
    if not updated_match: # Service layer should raise specific HTTPExceptions
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to submit match result")
    return updated_match
