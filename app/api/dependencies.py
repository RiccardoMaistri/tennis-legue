from sqlalchemy.orm import Session
from app.core.database import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Re-export get_current_user if it were moved here.
# from app.services.auth_service import get_current_user
