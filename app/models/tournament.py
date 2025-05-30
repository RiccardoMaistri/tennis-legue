from sqlalchemy import Column, Integer, String, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    creator_id = Column(Integer, ForeignKey("users.id"))
    location = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    type = Column(String)  # e.g., "singles", "doubles"
    max_players = Column(Integer)
    rules = Column(String, nullable=True)
    status = Column(String, default="pending") # e.g., "pending", "active", "completed", "cancelled"
    invite_token = Column(String, unique=True, index=True)

    creator = relationship("User", back_populates="created_tournaments")
    participants = relationship("Participant", back_populates="tournament")
    matches = relationship("Match", back_populates="tournament")
