from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, EmailStr

class UserModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: EmailStr
    full_name: Optional[str] = None
    oauth_provider: str
    oauth_provider_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        from_attributes = True # For SQLAlchemy compatibility if needed later, and good practice
        # Ensure email is unique - this will be handled at the service layer for JSON
        # Pydantic itself doesn't enforce uniqueness across a collection of models
        pass
