from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    google_id = Column(String, unique=True, index=True)
    avatar_url = Column(String, nullable=True)

    created_tournaments = relationship("Tournament", back_populates="creator")
    participations = relationship("Participant", back_populates="user")
    # Relationships for matches (player1, player2, winner) will be defined in the Match model
    # and accessed via back_populates if needed, or can be added here explicitly if direct
    # access like user.matches_as_player1 is desired.
    # For now, we'll rely on Match model's relationships.
    notifications = relationship("Notification", back_populates="user")
