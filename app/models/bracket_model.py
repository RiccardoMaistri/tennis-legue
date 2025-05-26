from uuid import uuid4 # Only uuid4 is needed for generating string UUIDs
from typing import List, Optional, Dict
from enum import Enum

from pydantic import BaseModel, Field

class MatchStatus(str, Enum):
    PENDING = "PENDING"
    PLAYER1_WIN = "PLAYER1_WIN"
    PLAYER2_WIN = "PLAYER2_WIN"
    DRAW = "DRAW"
    COMPLETED = "COMPLETED"
    BYE = "BYE"

class MatchModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    tournament_id: str # Changed to str
    round_number: int
    match_in_round: int
    
    player1_id: Optional[str] = None # Changed to str
    player2_id: Optional[str] = None # Changed to str
    
    winner_id: Optional[str] = None # Changed to str
    
    score_player1: Optional[int] = None
    score_player2: Optional[int] = None
    
    status: MatchStatus = MatchStatus.PENDING
    
    next_match_id: Optional[str] = None # Changed to str
    winner_to_player_slot: Optional[int] = None

    class Config:
        from_attributes = True
        use_enum_values = True

class BracketModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())) # Changed to str
    tournament_id: str # Changed to str
    tournament_type: str 
    
    matches: List[MatchModel] = Field(default_factory=list)
    
    rounds_structure: Dict[int, List[str]] = Field(default_factory=dict) # List of Match IDs (str)

    class Config:
        from_attributes = True
        use_enum_values = True
        # No specific json_encoders needed if IDs are strings
        pass
