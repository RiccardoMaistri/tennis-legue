from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
import datetime

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    player1_id = Column(Integer, ForeignKey("users.id"))
    player2_id = Column(Integer, ForeignKey("users.id"))
    round = Column(Integer, nullable=True) # e.g., 1, 2, 3 for rounds, or specific like "quarterfinal"
    status = Column(String, default="pending") # e.g., "pending", "in_progress", "completed", "cancelled"
    score = Column(String, nullable=True) # e.g., "6-4, 6-3"
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    datetime = Column(DateTime, nullable=True)
    court = Column(String, nullable=True)

    tournament = relationship("Tournament", back_populates="matches")
    player1 = relationship("User", foreign_keys=[player1_id])
    player2 = relationship("User", foreign_keys=[player2_id])
    winner = relationship("User", foreign_keys=[winner_id])

    # To avoid issues with User having multiple relationship paths to Match (player1, player2, winner),
    # we don't define back_populates here that would point to a single attribute on User.
    # If we need to access matches a user played, it would be queried explicitly.
    # For example, from User:
    # matches_as_player1 = relationship("Match", foreign_keys="[Match.player1_id]", back_populates="player1")
    # matches_as_player2 = relationship("Match", foreign_keys="[Match.player2_id]", back_populates="player2")
    # won_matches = relationship("Match", foreign_keys="[Match.winner_id]", back_populates="winner")
    # These can be added to user.py if such direct navigation is frequently needed.
    # For now, keeping it simple.
