import json
import os
import math # For calculating rounds, byes
import random # For shuffling players
from typing import List, Optional, Dict, Any

from app.models.bracket_model import BracketModel, MatchModel, MatchStatus
from app.models.tournament_model import TournamentConfig, TournamentType
# Assuming UserService and TournamentService will be injected or accessible
# For now, direct instantiation for structure, but ideally injected.
from app.services.tournament_service import TournamentService
from app.services.user_service import UserService

DATA_DIR = "app/data"
BRACKETS_FILE = os.path.join(DATA_DIR, "brackets.json")

class BracketService:
    def __init__(self, 
                 brackets_file_path: str = BRACKETS_FILE,
                 tournament_service: TournamentService = TournamentService(), # Default instance
                 user_service: UserService = UserService() # Default instance
                ):
        self.brackets_file_path = brackets_file_path
        self.tournament_service = tournament_service
        self.user_service = user_service # To fetch player details if needed, though player_ids are often sufficient

        os.makedirs(os.path.dirname(self.brackets_file_path), exist_ok=True)
        if not os.path.exists(self.brackets_file_path):
            self._save_brackets_to_file([])

    def _load_brackets_from_file(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.brackets_file_path):
            return []
        try:
            with open(self.brackets_file_path, "r") as f:
                brackets_data = json.load(f)
                return brackets_data
        except json.JSONDecodeError:
            return []

    def _save_brackets_to_file(self, brackets_data: List[Dict[str, Any]]):
        with open(self.brackets_file_path, "w") as f:
            json.dump(brackets_data, f, indent=4, default=str) # Use default=str for UUIDs if they were objects

    def get_bracket_by_tournament_id(self, tournament_id: str) -> Optional[BracketModel]:
        brackets_data = self._load_brackets_from_file()
        for bracket_dict in brackets_data:
            if bracket_dict.get("tournament_id") == tournament_id:
                return BracketModel(**bracket_dict)
        return None

    def create_bracket_for_tournament(self, tournament_id: str) -> Optional[BracketModel]:
        """
        Creates a bracket for a given tournament.
        Currently supports SINGLE_ELIMINATION.
        """
        tournament_config = self.tournament_service.get_tournament_by_id(tournament_id)
        if not tournament_config:
            raise ValueError(f"Tournament with ID {tournament_id} not found.")

        if tournament_config.status == "ACTIVE" or tournament_config.status == "COMPLETED":
             existing_bracket = self.get_bracket_by_tournament_id(tournament_id)
             if existing_bracket:
                 return existing_bracket # Do not regenerate if already active/completed

        if not tournament_config.player_ids:
            raise ValueError("Tournament has no players. Cannot generate bracket.")

        # For simplicity, we'll assume player_ids are valid User IDs.
        # In a real app, you might fetch UserModel for each player_id if more info is needed.
        player_ids = tournament_config.player_ids

        matches: List[MatchModel] = []
        rounds_structure: Dict[int, List[str]] = {}

        if tournament_config.tournament_type == TournamentType.SINGLE_ELIMINATION:
            matches, rounds_structure = self._generate_single_elimination_matches(
                player_ids=list(player_ids), # Pass a copy
                tournament_id=tournament_id
            )
        # elif tournament_config.tournament_type == TournamentType.ROUND_ROBIN:
        #     matches, rounds_structure = self._generate_round_robin_matches(list(player_ids), tournament_id)
        else:
            raise NotImplementedError(f"Bracket generation for {tournament_config.tournament_type} is not implemented.")

        bracket = BracketModel(
            tournament_id=tournament_id,
            tournament_type=tournament_config.tournament_type.value, # Store enum value
            matches=matches,
            rounds_structure=rounds_structure
            # id for BracketModel will be auto-generated
        )
        
        brackets_data = self._load_brackets_from_file()
        # Remove existing bracket for this tournament if regenerating
        brackets_data = [b for b in brackets_data if b.get("tournament_id") != tournament_id]
        brackets_data.append(bracket.model_dump())
        self._save_brackets_to_file(brackets_data)
        
        # Optionally update tournament status
        self.tournament_service.update_tournament_status(tournament_id, "ACTIVE") # Or "BRACKET_GENERATED"

        return bracket

    def _generate_single_elimination_matches(self, player_ids: List[str], tournament_id: str) -> (List[MatchModel], Dict[int, List[str]]):
        """
        Generates matches for a single elimination bracket.
        Returns a list of MatchModel instances and the rounds structure.
        """
        num_players = len(player_ids)
        if num_players < 2:
            raise ValueError("Single elimination bracket requires at least 2 players.")

        # Shuffle players for random seeding (can be replaced with a proper seeding later)
        shuffled_players = random.sample(player_ids, num_players)

        # Calculate number of rounds and byes
        num_rounds = math.ceil(math.log2(num_players))
        num_matches_first_round_ideal = 2**num_rounds // 2 
        # total_slots_in_bracket = 2**num_rounds
        # num_byes = total_slots_in_bracket - num_players
        
        # Simplified: first round might not be full, players advance
        # More standard: calculate total slots for a power-of-2 bracket, then fill byes
        
        # Number of players in the first "true" round (power of 2)
        num_players_pow2 = 1
        while num_players_pow2 < num_players:
            num_players_pow2 *= 2
        
        num_byes = num_players_pow2 - num_players

        current_round_players = []
        matches: List[MatchModel] = []
        rounds_structure: Dict[int, List[str]] = {}
        
        round_number = 1
        rounds_structure[round_number] = []

        # Handle initial round (with byes if any)
        # Players who get a bye advance directly.
        # Matches are created for players who don't get a bye.
        
        # Distribute byes among the first `num_byes` players in the shuffled list
        # These players will advance directly to round 2.
        # The remaining players (num_players - num_byes) will play in round 1.
        
        players_for_round1 = shuffled_players[num_byes:]
        byes_players = shuffled_players[:num_byes]

        match_in_round_counter = 1
        
        # Create matches for players in round 1
        for i in range(0, len(players_for_round1), 2):
            match = MatchModel(
                tournament_id=tournament_id,
                round_number=round_number,
                match_in_round=match_in_round_counter,
                player1_id=players_for_round1[i],
                player2_id=players_for_round1[i+1] if (i+1) < len(players_for_round1) else None, # Should always have p2
                status=MatchStatus.PENDING
            )
            matches.append(match)
            rounds_structure[round_number].append(match.id)
            match_in_round_counter += 1

        # Prepare for next rounds
        # Winners of round 1 matches + players with byes proceed to round 2
        
        # Placeholder for linking matches (next_match_id) - this requires full bracket generation logic
        # This simplified version only creates the first round matches correctly if num_players is power of 2.
        # A full implementation would build all rounds and link them.

        # For now, let's focus on just getting the first round matches set up
        # and byes if num_players is not a power of 2.
        
        # If byes exist, these players conceptually "win" their first match.
        # We can create "BYE" matches for them or handle advancement differently.
        # For simplicity, let's assume _generate_single_elimination_matches focuses on creating all match objects
        # and linking them. This is a complex task.
        
        # --- More complete (but still simplified) single elimination logic ---
        
        all_matches: List[MatchModel] = []
        current_round_match_ids: List[str] = []
        
        # Round 1 setup
        round_1_players = list(shuffled_players) # Use a copy
        
        # Fill with BYE placeholders if not a power of 2, to make pairing easy
        # This isn't standard for byes, byes usually mean a player skips a match.
        # A better way:
        #   num_first_round_matches = num_players - (2**math.floor(math.log2(num_players)))
        #   If num_first_round_matches is 0, it means num_players is a power of 2.
        #   Then, num_first_round_matches = num_players // 2
        
        # Let's use the standard model: some players play in round 1, some get byes to round 2.
        # Number of matches in the first round: num_players - (number of byes) / 2 is not quite right.
        # Number of players playing in round 1 = 2 * (num_players - num_byes_needed_for_pow2)
        
        n = len(shuffled_players)
        num_rounds = math.ceil(math.log2(n))
        
        # Calculate number of players in the first round that play (not byes)
        # Number of slots in the full bracket (next power of 2)
        bracket_size = 1
        while bracket_size < n:
            bracket_size *= 2
        
        num_byes_in_bracket = bracket_size - n
        
        # First round matches: (n - num_byes_in_bracket) players will play
        num_players_in_round1_matches = n - num_byes_in_bracket
        
        # These players are at the "end" of the shuffled list for pairing
        round1_playing_pool = shuffled_players[num_byes_in_bracket:]
        
        # These players get byes
        round1_bye_pool = shuffled_players[:num_byes_in_bracket]

        # --- Generate all match shells for the bracket ---
        total_matches_in_bracket = bracket_size - 1
        match_id_map = {i: str(uuid4()) for i in range(total_matches_in_bracket)}
        
        match_objects: Dict[str, MatchModel] = {} # Store match objects by their new string ID
        
        # Create all match objects (shells)
        # This is a bit abstract, normally you build round by round.
        # Let's try building round by round.
        
        # Round 1
        round_num = 1
        rounds_structure[round_num] = []
        next_round_advancers: List[Optional[str]] = [] # Stores player_ids or Match.id for who advances

        match_idx_in_round = 0
        # Pair players for round 1 matches
        for i in range(0, num_players_in_round1_matches, 2):
            p1 = round1_playing_pool[i]
            p2 = round1_playing_pool[i+1]
            match = MatchModel(
                tournament_id=tournament_id,
                round_number=round_num,
                match_in_round=match_idx_in_round,
                player1_id=p1,
                player2_id=p2,
                status=MatchStatus.PENDING
            )
            all_matches.append(match)
            rounds_structure[round_num].append(match.id)
            next_round_advancers.append(match.id) # Winner of this match advances
            match_idx_in_round += 1
            
        # Add players with byes to the list of advancers for the next round
        for player_id_with_bye in round1_bye_pool:
            # Create a "BYE" match for them, or just advance them.
            # If creating a BYE match:
            bye_match = MatchModel(
                tournament_id=tournament_id,
                round_number=round_num, # Conceptually in round 1
                match_in_round=match_idx_in_round,
                player1_id=player_id_with_bye,
                status=MatchStatus.BYE,
                winner_id=player_id_with_bye # Winner is the player themselves
            )
            all_matches.append(bye_match)
            rounds_structure[round_num].append(bye_match.id)
            # This player advances directly
            next_round_advancers.append(player_id_with_bye) # The player_id advances
            match_idx_in_round += 1

        # Subsequent rounds
        # `current_round_participants` can be a mix of player_ids (from byes) and match_ids (winners of previous matches)
        current_round_participants = list(next_round_advancers)
        
        while len(current_round_participants) > 1: # Loop until one winner (or one final match)
            round_num += 1
            rounds_structure[round_num] = []
            next_round_participants_temp: List[Optional[str]] = []
            match_idx_in_round = 0

            if len(current_round_participants) % 2 != 0 and round_num > 1:
                 # This should not happen in a well-formed single elimination bracket after round 1
                 # unless there's an issue with bye handling or advancement.
                 # For safety, if an odd number, the last one gets a "bye" to the next pairing stage.
                 # This implies an error in logic if not the final match.
                 # For now, assume pairs are always possible.
                 pass

            for i in range(0, len(current_round_participants), 2):
                p1_source = current_round_participants[i]
                p2_source = current_round_participants[i+1] if (i+1) < len(current_round_participants) else None

                # Create new match
                new_match = MatchModel(
                    tournament_id=tournament_id,
                    round_number=round_num,
                    match_in_round=match_idx_in_round,
                    status=MatchStatus.PENDING
                    # player1_id and player2_id will be set if sources are direct player_ids
                    # or will be populated later when previous matches complete.
                )

                # Link previous matches/byes to this new match
                # If p1_source is a player_id (from a bye), set player1_id directly
                # If p1_source is a match_id, this new_match is the next_match for p1_source
                
                # This logic is getting complex and needs to be precise.
                # The core idea: each new match takes winners from two previous matches (or byes).
                # The `next_match_id` and `winner_to_player_slot` are key.
                
                # Let's simplify: this function generates the structure.
                # Player assignment to matches beyond round 1 happens as winners are determined.
                # So, for rounds > 1, player1_id and player2_id are initially None.

                all_matches.append(new_match)
                rounds_structure[round_num].append(new_match.id)
                next_round_participants_temp.append(new_match.id) # Winner of this new_match advances
                match_idx_in_round += 1

                # Now, link the sources (previous matches) to this new_match
                # This requires finding the match objects for p1_source and p2_source if they are match_ids
                # For this to work, all_matches should be a dict for quick lookup, or iterate.
                
                # This part is crucial for `next_match_id`
                # Simplified: assume we have match objects from previous round
                # For placeholder, this detailed linking is deferred.
                # A full bracket generator would trace paths.

            current_round_participants = list(next_round_participants_temp)
            if len(current_round_participants) == 1 and isinstance(current_round_participants[0], str): 
                # This means we have the ID of the final match.
                # If it's a player ID, it means they won through byes, which is only if 1 player.
                break 


        # This simplified generation mostly sets up the matches and round structure.
        # Linking `next_match_id` and `winner_to_player_slot` needs a pass *after* all match objects are created.
        # For now, `_generate_single_elimination_matches` will return the list of matches and the rounds_structure.
        # The actual assignment of players to matches beyond round 1, and setting `next_match_id`,
        # would be part of a more sophisticated bracket generation or update process.
        
        # --- Full Single Elimination Logic ---
        num_players = len(player_ids)
        if num_players < 2:
            raise ValueError("Single elimination bracket requires at least 2 players.")

        # Shuffle players for random seeding
        random.shuffle(player_ids)

        # Calculate bracket size and byes
        bracket_size = 1
        while bracket_size < num_players:
            bracket_size *= 2
        
        num_byes = bracket_size - num_players

        all_matches_list: List[MatchModel] = []
        rounds_structure_dict: Dict[int, List[str]] = {}
        
        # --- Round 1: Create initial matches and BYE matches ---
        current_round_advancers: List[Optional[str]] = [] # Stores player_ids (from byes) or Match.id (from played matches)
        round_num = 1
        rounds_structure_dict[round_num] = []
        
        match_in_round_idx = 1

        # Assign byes to the first `num_byes` players
        for i in range(num_byes):
            player_id_with_bye = player_ids[i]
            bye_match = MatchModel(
                tournament_id=tournament_id,
                round_number=round_num,
                match_in_round=match_in_round_idx,
                player1_id=player_id_with_bye,
                status=MatchStatus.BYE,
                winner_id=player_id_with_bye
            )
            all_matches_list.append(bye_match)
            rounds_structure_dict[round_num].append(bye_match.id)
            current_round_advancers.append(player_id_with_bye) # Player directly advances
            match_in_round_idx += 1

        # Create matches for the remaining players in the first round
        players_for_round1_matches = player_ids[num_byes:]
        for i in range(0, len(players_for_round1_matches), 2):
            p1_id = players_for_round1_matches[i]
            p2_id = players_for_round1_matches[i+1] # Should always exist due to bracket_size logic
            
            match = MatchModel(
                tournament_id=tournament_id,
                round_number=round_num,
                match_in_round=match_in_round_idx,
                player1_id=p1_id,
                player2_id=p2_id,
                status=MatchStatus.PENDING
            )
            all_matches_list.append(match)
            rounds_structure_dict[round_num].append(match.id)
            current_round_advancers.append(match.id) # Winner of this match (identified by match.id) advances
            match_in_round_idx += 1
            
        # --- Subsequent Rounds ---
        # `current_round_advancers` now contains a mix of player_ids (from byes) and match_ids (from round 1 played matches)
        
        # This list will hold match objects from the previous round, used for linking
        previous_round_match_objects = {m.id: m for m in all_matches_list if m.round_number == round_num}

        while len(current_round_advancers) > 1:
            round_num += 1
            rounds_structure_dict[round_num] = []
            next_round_advancers_temp: List[str] = [] # Will only contain match_ids for future rounds
            match_in_round_idx = 1
            
            newly_created_matches_this_round: Dict[str, MatchModel] = {}

            for i in range(0, len(current_round_advancers), 2):
                source1 = current_round_advancers[i] # Either a player_id (bye) or a match_id
                source2 = current_round_advancers[i+1] # Either a player_id (bye) or a match_id

                # Create the new match for the current round
                new_match = MatchModel(
                    tournament_id=tournament_id,
                    round_number=round_num,
                    match_in_round=match_in_round_idx,
                    status=MatchStatus.PENDING
                    # player1_id and player2_id will be set if sources are direct player_ids (only possible in round 2 from byes)
                    # or will be populated later when previous matches complete.
                )
                all_matches_list.append(new_match)
                rounds_structure_dict[round_num].append(new_match.id)
                next_round_advancers_temp.append(new_match.id)
                newly_created_matches_this_round[new_match.id] = new_match
                match_in_round_idx += 1

                # Link source1 to new_match
                if source1 in previous_round_match_objects: # source1 was a match from the previous round
                    prev_match1 = previous_round_match_objects[source1]
                    prev_match1.next_match_id = new_match.id
                    prev_match1.winner_to_player_slot = 1
                else: # source1 was a player_id (from a bye in the conceptual "round 0")
                    new_match.player1_id = source1
                
                # Link source2 to new_match
                if source2 in previous_round_match_objects: # source2 was a match from the previous round
                    prev_match2 = previous_round_match_objects[source2]
                    prev_match2.next_match_id = new_match.id
                    prev_match2.winner_to_player_slot = 2
                else: # source2 was a player_id (from a bye)
                    new_match.player2_id = source2
            
            current_round_advancers = next_round_advancers_temp
            previous_round_match_objects = newly_created_matches_this_round

        return all_matches_list, rounds_structure_dict

    def record_match_result(self, tournament_id: str, match_id: str, p1_score: int, p2_score: int, current_user_id: str) -> Optional[MatchModel]:
        # Verify admin
        tournament_config = self.tournament_service.get_tournament_by_id(tournament_id)
        if not tournament_config:
            raise ValueError(f"Tournament with ID {tournament_id} not found.")
        if tournament_config.admin_id != current_user_id:
            # In a real HTTP context, this would be an HTTPException(status_code=403)
            # For service layer, raising PermissionError or ValueError is common.
            raise PermissionError("User is not authorized to record match results for this tournament.")

        brackets_list = self._load_brackets_from_file()
        bracket_found = False
        updated_match_model = None

        for i, bracket_dict in enumerate(brackets_list):
            if bracket_dict.get("tournament_id") == tournament_id:
                bracket = BracketModel(**bracket_dict)
                bracket_found = True
                match_found_in_bracket = False
                for j, match_dict_in_list in enumerate(bracket.matches):
                    # Pydantic models might have already converted to MatchModel,
                    # but if it's still a dict from _load_brackets_from_file raw output:
                    # current_match_id = match_dict_in_list.get("id")
                    # For BracketModel, bracket.matches are List[MatchModel]
                    current_match = bracket.matches[j]
                    if current_match.id == match_id:
                        match_found_in_bracket = True
                        
                        # Check if match can be updated
                        if current_match.status not in [MatchStatus.PENDING]:
                            raise ValueError(f"Match status is '{current_match.status}'. Only PENDING matches can be updated.")
                        if not current_match.player1_id or not current_match.player2_id:
                            raise ValueError("Match does not have two players assigned.")
                        if p1_score == p2_score:
                            # For single elimination, a winner must be decided.
                            # If draws are allowed by tournament rules (e.g. for points in group stage),
                            # this logic would need to adapt.
                            raise ValueError("Scores cannot be equal in a single elimination match. A winner must be determined.")

                        # Determine winner and update status
                        current_match.score_player1 = p1_score
                        current_match.score_player2 = p2_score
                        
                        if p1_score > p2_score:
                            current_match.winner_id = current_match.player1_id
                            current_match.status = MatchStatus.PLAYER1_WIN
                        elif p2_score > p1_score:
                            current_match.winner_id = current_match.player2_id
                            current_match.status = MatchStatus.PLAYER2_WIN
                        
                        # The problem statement implies PLAYER1_WIN/PLAYER2_WIN are the final states for a completed match with a winner.
                        # A general "COMPLETED" status might be used if the flow was more complex,
                        # e.g. pending verification, or if draws were possible and processed differently.
                        # For now, PLAYER1_WIN or PLAYER2_WIN implies completion.

                        updated_match_model = current_match
                        bracket.matches[j] = updated_match_model # Update the match in the bracket's list
                        
                        # --- Advancement Logic ---
                        if updated_match_model.winner_id:
                            if updated_match_model.next_match_id:
                                next_match_found_for_advancement = False
                                for k, potential_next_match in enumerate(bracket.matches):
                                    if potential_next_match.id == updated_match_model.next_match_id:
                                        next_match_object = bracket.matches[k]
                                        next_match_found_for_advancement = True
                                        if updated_match_model.winner_to_player_slot == 1:
                                            next_match_object.player1_id = updated_match_model.winner_id
                                        elif updated_match_model.winner_to_player_slot == 2:
                                            next_match_object.player2_id = updated_match_model.winner_id
                                        else:
                                            # This case should not happen if bracket generation is correct
                                            raise RuntimeError(
                                                f"Invalid winner_to_player_slot value '{updated_match_model.winner_to_player_slot}' "
                                                f"for match {updated_match_model.id}."
                                            )
                                        
                                        # If the next match now has both players, it could transition status,
                                        # but for now, PENDING is fine. It becomes playable.
                                        # If one of the players in the next_match was a BYE that auto-advanced,
                                        # this logic correctly populates the other slot.
                                        break # Next match updated
                                if not next_match_found_for_advancement:
                                    raise RuntimeError(
                                        f"Consistency error: next_match_id {updated_match_model.next_match_id} "
                                        f"not found in bracket for tournament {tournament_id}."
                                    )
                            else:
                                # This was the final match
                                # Update TournamentConfig status to COMPLETED
                                try:
                                    self.tournament_service.update_tournament_status(tournament_id, "COMPLETED")
                                    # Optional: Set tournament winner
                                    # tournament_config.winner_user_id = updated_match_model.winner_id
                                    # self.tournament_service.update_tournament(tournament_id, tournament_config) # Needs an update_tournament method
                                except ValueError as e:
                                    # Log or handle error if tournament status update fails
                                    print(f"Error updating tournament status to COMPLETED: {e}")
                                    # Potentially raise a specific error or just log
                        # --- End Advancement Logic ---
                        
                        brackets_list[i] = bracket.model_dump() # Update the bracket in the main list
                        self._save_brackets_to_file(brackets_list)
                        break # Match updated
                
                if not match_found_in_bracket:
                    raise ValueError(f"Match with ID {match_id} not found in tournament {tournament_id}.")
                break # Bracket found and processed
        
        if not bracket_found:
            # This should ideally be caught by the tournament check, but as a safeguard for bracket data integrity:
            raise ValueError(f"Bracket for tournament ID {tournament_id} not found, though tournament exists.")
            
        return updated_match_model

    # Placeholder for Round Robin
    # def _generate_round_robin_matches(self, player_ids: List[str], tournament_id: str) -> (List[MatchModel], Dict[int, List[str]]):
    #     # Logic for round robin pairing (e.g., circle method)
    #     pass

```
