from pydantic import BaseModel
from typing import Optional
from .user_schemas import UserRead
from .tournament_schemas import TournamentRead # Import TournamentRead

class ParticipantBase(BaseModel):
    user_id: int
    tournament_id: int
    status: str = "pending"

class ParticipantCreate(ParticipantBase):
    pass

class ParticipantRead(ParticipantBase):
    id: int
    user: UserRead
    # For now, TournamentRead does not contain a list of participants, so direct import is fine.
    # If TournamentRead is updated to include participants, this might create a circular dependency.
    # In that case, we might use a forward reference: tournament: 'TournamentRead'
    # and then call ParticipantRead.update_forward_refs() later.
    # Or use a simplified Tournament schema here.
    tournament: TournamentRead

    class Config:
        orm_mode = True

class ParticipantUpdate(BaseModel):
    status: str

    class Config:
        orm_mode = True
