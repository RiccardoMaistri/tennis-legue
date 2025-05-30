from typing import Optional
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status

# Potentially install google-auth google-auth-oauthlib if not present
# Example: pip install google-auth google-auth-oauthlib
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


# Temporary models and schemas import for fake token handling (adjust path if needed)
from app.models import user as user_model # Already here
from app.schemas import user_schemas # Already here

from app.core.config import settings
from app.core import security # For oauth2_scheme and verify_token
from app.models import user as user_model
from app.schemas import user_schemas, auth_schemas
from app.core.database import SessionLocal # To query DB directly if needed, or use passed db session

def verify_google_id_token(token: str, db: Session) -> Optional[user_model.User]:
    # START TEMPORARY MODIFICATION FOR FAKE TOKEN
    if token == "fake_google_token_for_testing":
        user = db.query(user_model.User).filter(user_model.User.email == "testuser@example.com").first()
        if not user:
            # Ensure UserCreate schema is used correctly if it expects google_id
            user_create_data = user_schemas.UserCreate(
                name="Test User",
                email="testuser@example.com",
                google_id="fake_google_id_123", # This field is part of UserCreate
                avatar_url="http://example.com/avatar.png"
            )
            user = user_model.User(**user_create_data.model_dump())
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    # END TEMPORARY MODIFICATION FOR FAKE TOKEN

    try:
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        email = idinfo.get("email")
        google_id = idinfo.get("sub") # 'sub' is the standard field for Google ID
        name = idinfo.get("name")
        avatar_url = idinfo.get("picture")

        if not email or not google_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or Google ID missing from token payload",
            )

        # Check if user exists by google_id
        user = db.query(user_model.User).filter(user_model.User.google_id == google_id).first()

        if user:
            # Update user info if changed
            update_data = {}
            if user.name != name:
                update_data["name"] = name
            if user.avatar_url != avatar_url:
                update_data["avatar_url"] = avatar_url
            if user.email != email: # Google ID is primary, but email could change (rare)
                # Check if new email is already taken by another user (excluding current user)
                existing_email_user = db.query(user_model.User).filter(user_model.User.email == email, user_model.User.google_id != google_id).first()
                if existing_email_user:
                    # This case needs careful handling: email conflict.
                    # For now, let's prevent update and raise an error or log.
                    # Or, prioritize Google ID and maybe nullify email for the old account if policy allows.
                    # For simplicity, we'll just not update email if it conflicts.
                    pass # Or raise HTTPException(status_code=409, detail="Email already in use by another account")
                else:
                    update_data["email"] = email

            if update_data:
                for key, value in update_data.items():
                    setattr(user, key, value)
                db.commit()
                db.refresh(user)
            return user
        else:
            # Check if user exists by email (e.g., if they signed up differently before)
            user = db.query(user_model.User).filter(user_model.User.email == email).first()
            if user:
                # User exists with this email but different/no google_id. Link account.
                user.google_id = google_id
                user.name = name # Update name and avatar
                user.avatar_url = avatar_url
                db.commit()
                db.refresh(user)
                return user
            else:
                # Create new user
                user_create_data = user_schemas.UserCreate(
                    name=name,
                    email=email,
                    google_id=google_id,
                    avatar_url=avatar_url
                )
                new_user = user_model.User(**user_create_data.model_dump())
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                return new_user

    except ValueError as e:
        # Invalid token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Other exceptions
        # Log the error e for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying Google token: {e}",
        )


def get_current_user(token: str = Depends(security.oauth2_scheme), db: Session = Depends(SessionLocal)) -> user_model.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = security.verify_token(token, credentials_exception)
        if token_data.email is None: # Ensure email is present
            raise credentials_exception
    except Exception as e: # Catch if verify_token itself raises an error beyond JWTError
         raise credentials_exception

    user = db.query(user_model.User).filter(user_model.User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user
