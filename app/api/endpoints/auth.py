from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.services import auth_service
from app.core import security
from app.schemas import auth_schemas
from app.api.dependencies import get_db # Corrected import path

router = APIRouter()

@router.post("/login", response_model=auth_schemas.Token)
async def login_with_google(
    request: auth_schemas.GoogleLoginRequest, 
    db: Session = Depends(get_db)
):
    user = auth_service.verify_google_id_token(token=request.token, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify Google token or create user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    # The subject of the token ('sub') should be something unique to the user. Email is a good choice.
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
