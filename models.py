from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class User(BaseModel):
    user_id: str  # Unique identifier, could be generated or from OAuth provider
    email: str
    display_name: Optional[str] = None
    google_id: Optional[str] = None
    # apple_id: Optional[str] = None # Add if Apple sign-in is implemented

class Match(BaseModel):
    match_id: str
    # tournament_id: str # Not strictly needed if matches are embedded in tournaments
    player1_id: str
    player2_id: Optional[str] = None  # Optional for bye scenarios or round robin placeholder
    score1: Optional[int] = None
    score2: Optional[int] = None
    winner_id: Optional[str] = None
    round_number: Optional[int] = None
    match_status: str  # e.g., "scheduled", "completed", "pending_opponent"

class Tournament(BaseModel):
    tournament_id: str
    name: str
    format: str  # "round_robin" or "single_elimination"
    admin_user_id: str
    participants: List[str] = []  # List of user_ids
    invitation_code: str
    matches: List[Match] = []
    status: str  # e.g., "pending_setup", "active", "completed"
    created_at: datetime

class TournamentCreate(BaseModel):
    name: str
    format: str
