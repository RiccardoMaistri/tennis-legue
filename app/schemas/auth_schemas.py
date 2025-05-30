from pydantic import BaseModel, EmailStr
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    # Using email as the identifier in the token, but could be user_id
    email: Optional[EmailStr] = None
    # user_id: Optional[int] = None # Alternative identifier

class GoogleLoginRequest(BaseModel):
    token: str # This will be the Google ID token received from the client
