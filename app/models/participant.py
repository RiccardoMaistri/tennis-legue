from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    status = Column(String, default="pending")  # e.g., "accepted", "pending", "withdrawn"

    user = relationship("User", back_populates="participations")
    tournament = relationship("Tournament", back_populates="participants")
