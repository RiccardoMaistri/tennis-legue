from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from enum import Enum

from pydantic import BaseModel, Field, validator

class TournamentType(str, Enum):
    SINGLE_ELIMINATION = "SINGLE_ELIMINATION"
    ROUND_ROBIN = "ROUND_ROBIN"
    # Add other types as needed, e.g., DOUBLE_ELIMINATION, SWISS

class TournamentConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=3, max_length=100)
    tournament_type: TournamentType
    admin_id: str # References User.id
    created_at: datetime = Field(default_factory=datetime.utcnow)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    player_ids: List[str] = Field(default_factory=list) # List of User.id
    status: str = Field(default="PENDING") # e.g., "PENDING", "REGISTRATION_OPEN", "ACTIVE", "COMPLETED", "CANCELLED"
    invite_token: Optional[str] = None # For invitation links

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }
        from_attributes = True # Good practice for Pydantic models
        use_enum_values = True # Ensures enum values are used in serialization

    @validator('end_date')
    def end_date_after_start_date(cls, v, values, **kwargs):
        if v and values.get('start_date') and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v

    @validator('status')
    def valid_status(cls, v):
        allowed_statuses = {"PENDING", "REGISTRATION_OPEN", "ACTIVE", "COMPLETED", "CANCELLED"}
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of {allowed_statuses}")
        return v
