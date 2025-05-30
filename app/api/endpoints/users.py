from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.services import auth_service
from app.models import user as user_model
from app.models import tournament as tournament_model
from app.models import match as match_model
from app.models import participant as participant_model
from app.schemas import user_schemas
from app.api.dependencies import get_db
from sqlalchemy import or_, and_, func

router = APIRouter()

@router.get("/me", response_model=user_schemas.UserRead)
async def read_users_me(
    current_user: user_model.User = Depends(auth_service.get_current_user)
):
    return current_user

@router.get("/{user_id}/stats", response_model=user_schemas.UserStats)
async def get_user_stats(
    user_id: int,
    db: Session = Depends(get_db)
    # current_user: user_model.User = Depends(auth_service.get_current_user) # Optional: for auth
):
    user = db.query(user_model.User).filter(user_model.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    matches_played = db.query(match_model.Match).filter(
        or_(match_model.Match.player1_id == user_id, match_model.Match.player2_id == user_id)
    ).count()

    matches_won = db.query(match_model.Match).filter(match_model.Match.winner_id == user_id).count()

    tournaments_created = db.query(tournament_model.Tournament).filter(
        tournament_model.Tournament.creator_id == user_id
    ).count()

    tournaments_participated = db.query(participant_model.Participant).filter(
        participant_model.Participant.user_id == user_id,
        participant_model.Participant.status == "accepted" # Only count accepted participations
    ).count()

    win_percentage = 0.0
    if matches_played > 0:
        win_percentage = (matches_won / matches_played) * 100

    return user_schemas.UserStats(
        id=user.id,
        name=user.name,
        matches_played=matches_played,
        matches_won=matches_won,
        tournaments_created=tournaments_created,
        tournaments_participated=tournaments_participated,
        win_percentage=win_percentage,
    )
