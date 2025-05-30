import random
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import match as match_model
from app.models import tournament as tournament_model
from app.models import participant as participant_model
from app.models import user as user_model
from app.schemas import match_schemas

def _parse_score_to_determine_winner(score: str, player1_id: int, player2_id: int) -> Optional[int]:
    """
    Parses a score string (e.g., "6-4, 6-3" or "2-1") to determine the winner.
    Assumes player1_id's score components are listed first in each set/game count.
    Returns player1_id if player1 won, player2_id if player2 won, None if draw or unparseable.
    This is a simplified parser. A more robust one would handle various score formats.
    """
    if not score:
        return None

    p1_sets_won = 0
    p2_sets_won = 0

    # Try parsing comma-separated set scores (e.g., "6-4, 6-3")
    if ',' in score:
        sets = score.split(',')
        for s in sets:
            s = s.strip()
            if '-' not in s: continue # Skip malformed set strings
            parts = s.split('-')
            try:
                p1_games = int(parts[0])
                p2_games = int(parts[1])
                if p1_games > p2_games:
                    p1_sets_won += 1
                elif p2_games > p1_games:
                    p2_sets_won += 1
            except (ValueError, IndexError):
                continue # Skip malformed set scores
    # Try parsing simple game wins (e.g., "2-1" for a best-of-3 match)
    elif '-' in score:
        parts = score.split('-')
        try:
            p1_total_score = int(parts[0])
            p2_total_score = int(parts[1])
            if p1_total_score > p2_total_score:
                return player1_id
            elif p2_total_score > p1_total_score:
                return player2_id
            else: # Draw
                return None
        except (ValueError, IndexError):
            return None # Unparseable
    else: # Unparseable format
        return None

    if p1_sets_won > p2_sets_won:
        return player1_id
    elif p2_sets_won > p1_sets_won:
        return player2_id
    return None # Draw or unparseable overall


def generate_matches_for_tournament(db: Session, tournament_id: int, current_user_id: int) -> List[match_model.Match]:
    tournament = db.query(tournament_model.Tournament).filter(tournament_model.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    if tournament.creator_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to generate matches for this tournament")

    existing_matches_count = db.query(match_model.Match).filter(match_model.Match.tournament_id == tournament_id).count()
    if existing_matches_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Matches have already been generated for this tournament")

    participants_query = db.query(participant_model.Participant).filter(
        participant_model.Participant.tournament_id == tournament_id,
        participant_model.Participant.status == "accepted"
    ).all()
    
    participant_ids = [p.user_id for p in participants_query]

    if len(participant_ids) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough accepted participants (minimum 2) to generate matches")

    new_matches: List[match_model.Match] = []
    
    if tournament.type == "knockout":
        shuffled_participants = random.sample(participant_ids, len(participant_ids))
        num_participants = len(shuffled_participants)
        round_num = 1
        
        # Handle byes if odd number of players
        if num_participants % 2 != 0:
            bye_player_id = shuffled_participants.pop()
            # Create a "bye" match - advances player directly
            bye_match = match_model.Match(
                tournament_id=tournament_id,
                player1_id=bye_player_id,
                player2_id=None, # Indicates a bye
                round=round_num,
                status="completed", # Or "upcoming" and auto-win
                winner_id=bye_player_id,
                score="BYE"
            )
            new_matches.append(bye_match)
            # Proceed with the rest for pairing
        
        for i in range(0, len(shuffled_participants), 2):
            if i + 1 < len(shuffled_participants):
                match = match_model.Match(
                    tournament_id=tournament_id,
                    player1_id=shuffled_participants[i],
                    player2_id=shuffled_participants[i+1],
                    round=round_num,
                    status="pending"
                )
                new_matches.append(match)

    elif tournament.type == "round_robin" or tournament.type == "andata_ritorno": # Home and Away
        for i in range(len(participant_ids)):
            for j in range(i + 1, len(participant_ids)):
                # First leg
                match1 = match_model.Match(
                    tournament_id=tournament_id,
                    player1_id=participant_ids[i],
                    player2_id=participant_ids[j],
                    status="pending"
                    # round can be set if play days are defined, otherwise null
                )
                new_matches.append(match1)
                
                if tournament.type == "andata_ritorno":
                    # Second leg (players swapped)
                    match2 = match_model.Match(
                        tournament_id=tournament_id,
                        player1_id=participant_ids[j],
                        player2_id=participant_ids[i],
                        status="pending"
                    )
                    new_matches.append(match2)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported tournament type: {tournament.type}")

    if not new_matches:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No matches generated, check participants or tournament type.")

    db.add_all(new_matches)
    db.commit()
    # Refresh each match to get IDs, etc.
    for match in new_matches:
        db.refresh(match)
    return new_matches


def get_tournament_matches(db: Session, tournament_id: int) -> List[match_model.Match]:
    tournament = db.query(tournament_model.Tournament).filter(tournament_model.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return db.query(match_model.Match).filter(match_model.Match.tournament_id == tournament_id).all()

def get_match_details(db: Session, match_id: int) -> Optional[match_model.Match]:
    return db.query(match_model.Match).filter(match_model.Match.id == match_id).first()

def submit_match_result(db: Session, match_id: int, result: match_schemas.MatchResultUpdate, current_user_id: int) -> Optional[match_model.Match]:
    db_match = get_match_details(db, match_id)
    if not db_match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    tournament = db.query(tournament_model.Tournament).filter(tournament_model.Tournament.id == db_match.tournament_id).first()
    if not tournament: # Should not happen if match exists
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tournament associated with match not found")

    is_player_in_match = db_match.player1_id == current_user_id or (db_match.player2_id and db_match.player2_id == current_user_id)
    is_tournament_creator = tournament.creator_id == current_user_id

    if not is_player_in_match and not is_tournament_creator:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to submit result for this match")

    if db_match.status == "completed" and not is_tournament_creator: # Allow creator to override
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Match result already submitted and completed")
    
    update_data = result.model_dump(exclude_unset=True)

    if 'score' in update_data:
        db_match.score = update_data['score']
        # Try to determine winner from score if winner_id not explicitly provided or needs validation
        if 'winner_id' not in update_data or update_data.get('winner_id') is None:
            if db_match.player1_id and db_match.player2_id : # Need two players for score parsing
                 winner_from_score = _parse_score_to_determine_winner(db_match.score, db_match.player1_id, db_match.player2_id)
                 if winner_from_score:
                     db_match.winner_id = winner_from_score
                 # if score indicates a draw and tournament type doesn't allow it, this could be an issue
            elif db_match.player1_id and db_match.player2_id is None and db_match.score == "BYE": # Bye match
                db_match.winner_id = db_match.player1_id


    if 'winner_id' in update_data:
        winner_id_provided = update_data['winner_id']
        if winner_id_provided is not None and winner_id_provided not in [db_match.player1_id, db_match.player2_id]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Winner must be one of the players in the match.")
        db_match.winner_id = winner_id_provided
    
    if 'status' in update_data:
        db_match.status = update_data['status']
    else: # If status not provided, but score/winner is, mark as completed
        if db_match.winner_id is not None:
            db_match.status = "completed"

    # If match is completed and winner is set, handle knockout advancement (simplified)
    # Full auto-advancement is complex and typically involves bracket management.
    # This is a placeholder for where that logic would go or be triggered.
    # if tournament.type == "knockout" and db_match.status == "completed" and db_match.winner_id:
    #     # Potential: find next match for this winner (e.g., if round 1, match X, winner goes to round 2, match Y)
    #     # This requires knowing the bracket structure.
    #     pass

    db.commit()
    db.refresh(db_match)
    return db_match
