import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import tournament as tournament_model
from app.models import user as user_model
from app.models import participant as participant_model
from app.schemas import tournament_schemas, participant_schemas

def create_tournament(db: Session, tournament: tournament_schemas.TournamentCreate, creator_id: int) -> tournament_model.Tournament:
    invite_token = str(uuid.uuid4())
    db_tournament = tournament_model.Tournament(
        **tournament.model_dump(),
        creator_id=creator_id,
        invite_token=invite_token,
        status="pending" # Default status
    )
    db.add(db_tournament)
    db.commit()
    db.refresh(db_tournament)
    return db_tournament

def get_tournament(db: Session, tournament_id: int) -> Optional[tournament_model.Tournament]:
    return db.query(tournament_model.Tournament).filter(tournament_model.Tournament.id == tournament_id).first()

def get_user_tournaments(db: Session, user_id: int) -> List[tournament_model.Tournament]:
    # Tournaments created by the user OR tournaments the user is an accepted participant in
    return db.query(tournament_model.Tournament).outerjoin(participant_model.Participant, 
        (participant_model.Participant.tournament_id == tournament_model.Tournament.id) &
        (participant_model.Participant.user_id == user_id)
    ).filter(
        or_(
            tournament_model.Tournament.creator_id == user_id,
            participant_model.Participant.status == "accepted" # Or any other relevant statuses
        )
    ).distinct().all()


def update_tournament(db: Session, tournament_id: int, tournament_update: tournament_schemas.TournamentUpdate, current_user_id: int) -> Optional[tournament_model.Tournament]:
    db_tournament = get_tournament(db, tournament_id)
    if not db_tournament:
        return None
    if db_tournament.creator_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this tournament")

    update_data = tournament_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tournament, key, value)
    
    db.commit()
    db.refresh(db_tournament)
    return db_tournament

def delete_tournament(db: Session, tournament_id: int, current_user_id: int) -> bool:
    db_tournament = get_tournament(db, tournament_id)
    if not db_tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    if db_tournament.creator_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this tournament")
    
    # Consider related entities: participants, matches.
    # Depending on cascading rules in DB or app logic, these might need to be handled.
    # For now, direct delete:
    db.delete(db_tournament)
    db.commit()
    return True

def generate_invite_link(db: Session, tournament_id: int, current_user_id: int) -> Optional[str]:
    db_tournament = get_tournament(db, tournament_id)
    if not db_tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    if db_tournament.creator_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to generate invite link for this tournament")
    return db_tournament.invite_token

def join_tournament_with_invite(db: Session, invite_token: str, user_id: int) -> Optional[participant_model.Participant]:
    tournament = db.query(tournament_model.Tournament).filter(tournament_model.Tournament.invite_token == invite_token).first()
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invite token")

    existing_participant = db.query(participant_model.Participant).filter(
        participant_model.Participant.tournament_id == tournament.id,
        participant_model.Participant.user_id == user_id
    ).first()
    if existing_participant:
        # Can either raise error or return existing participant based on desired UX
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already a participant in this tournament")

    current_participants_count = db.query(participant_model.Participant).filter(
        participant_model.Participant.tournament_id == tournament.id,
        participant_model.Participant.status == "accepted" # Count only accepted participants towards max_players
    ).count()
    if current_participants_count >= tournament.max_players:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament is full")

    # Default status for new participant, could be "pending" if creator approval is needed
    participant_data = participant_schemas.ParticipantCreate(
        user_id=user_id,
        tournament_id=tournament.id,
        status="accepted" # Or "pending"
    )
    db_participant = participant_model.Participant(**participant_data.model_dump())
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return db_participant

def list_participants(db: Session, tournament_id: int) -> List[participant_model.Participant]:
    # Ensure tournament exists
    db_tournament = get_tournament(db, tournament_id)
    if not db_tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return db.query(participant_model.Participant).filter(participant_model.Participant.tournament_id == tournament_id).all()

def update_participant_status(db: Session, tournament_id: int, participant_user_id: int, participant_update: participant_schemas.ParticipantUpdate, current_user_id: int) -> Optional[participant_model.Participant]:
    db_tournament = get_tournament(db, tournament_id)
    if not db_tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    
    if db_tournament.creator_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update participant status for this tournament")

    participant = db.query(participant_model.Participant).filter(
        participant_model.Participant.tournament_id == tournament_id,
        participant_model.Participant.user_id == participant_user_id
    ).first()

    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    participant.status = participant_update.status
    db.commit()
    db.refresh(participant)
    return participant
