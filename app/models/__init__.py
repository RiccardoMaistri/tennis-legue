from app.core.database import Base, engine

# Import all models here to ensure they are registered with Base
from .user import User
from .tournament import Tournament
from .participant import Participant
from .match import Match
from .notification import Notification

# Create all tables in the database.
# This is often done in a migration tool like Alembic in larger applications,
# or can be triggered from main.py on startup.
# For simplicity in this step, we include it here.
# Ensure this is called after all model definitions.
Base.metadata.create_all(bind=engine)
