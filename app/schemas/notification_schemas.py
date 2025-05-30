from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationBase(BaseModel):
    message: str
    type: str # e.g., "tournament_invite", "match_update", "general"

class NotificationCreate(NotificationBase):
    user_id: int

class NotificationRead(NotificationBase):
    id: int
    user_id: int
    read_status: bool
    created_at: datetime

    class Config:
        orm_mode = True
