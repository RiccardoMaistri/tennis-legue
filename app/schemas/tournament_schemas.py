from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from .user_schemas import UserRead # Import UserRead

class TournamentBase(BaseModel):
    name: str
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    type: str # e.g., "singles", "doubles"
    max_players: int
    rules: Optional[str] = None

class TournamentCreate(TournamentBase):
    pass

class TournamentRead(TournamentBase):
    id: int
    creator_id: int
    status: str
    invite_token: str
    creator: UserRead # Nested UserRead schema

    class Config:
        orm_mode = True

class TournamentUpdate(TournamentBase):
    name: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    type: Optional[str] = None
    max_players: Optional[int] = None
    rules: Optional[str] = None
    status: Optional[str] = None

    class Config:
        orm_mode = True
