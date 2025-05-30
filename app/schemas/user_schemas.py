from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional

class UserBase(BaseModel):
    name: str
    email: EmailStr
    avatar_url: Optional[HttpUrl] = None

class UserCreate(UserBase):
    google_id: str

class UserRead(UserBase):
    id: int

    class Config:
        orm_mode = True

class UserStats(BaseModel):
    id: int
    name: str
    matches_played: int
    matches_won: int
    tournaments_created: int
    tournaments_participated: int
    win_percentage: float

    class Config:
        orm_mode = True
