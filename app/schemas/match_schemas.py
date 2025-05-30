from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .user_schemas import UserRead # Import UserRead

class MatchBase(BaseModel):
    player1_id: int
    player2_id: int
    tournament_id: int
    round: Optional[int] = None
    datetime: Optional[datetime] = None
    court: Optional[str] = None

class MatchCreate(MatchBase):
    pass

class MatchRead(MatchBase):
    id: int
    status: str
    score: Optional[str] = None
    winner_id: Optional[int] = None
    player1: UserRead
    player2: UserRead
    winner: Optional[UserRead] = None

    class Config:
        orm_mode = True

class MatchResultUpdate(BaseModel):
    score: Optional[str] = None
    status: Optional[str] = None # e.g., "completed", "cancelled"
    winner_id: Optional[int] = None # Could be determined from score, or set directly

    class Config:
        orm_mode = True
