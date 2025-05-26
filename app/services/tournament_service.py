import json
import os
import secrets # Added for token generation
from typing import List, Optional, Dict, Any
from app.models.tournament_model import TournamentConfig, TournamentType

DATA_DIR = "app/data"
TOURNAMENTS_FILE = os.path.join(DATA_DIR, "tournaments.json")

class TournamentService:
    def __init__(self, data_file_path: str = TOURNAMENTS_FILE):
        self.data_file_path = data_file_path
        os.makedirs(os.path.dirname(self.data_file_path), exist_ok=True)
        if not os.path.exists(self.data_file_path):
            self._save_tournaments([])

    def _load_tournaments(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.data_file_path):
            return []
        try:
            with open(self.data_file_path, "r") as f:
                tournaments = json.load(f)
                return tournaments
        except json.JSONDecodeError:
            return []

    def _save_tournaments(self, tournaments: List[Dict[str, Any]]):
        with open(self.data_file_path, "w") as f:
            json.dump(tournaments, f, indent=4, default=str) # Use default=str for datetime

    def create_tournament(self, config_data: TournamentConfig) -> TournamentConfig:
        tournaments = self._load_tournaments()
        
        # Optional: Check for duplicate tournament names by the same admin, if desired
        # for t_dict in tournaments:
        #     if t_dict.get("name") == config_data.name and t_dict.get("admin_id") == config_data.admin_id:
        #         raise ValueError(f"Tournament with name '{config_data.name}' already exists for this admin.")

        tournament_dict = config_data.model_dump()
        tournaments.append(tournament_dict)
        self._save_tournaments(tournaments)
        return config_data

    def get_tournament_by_id(self, tournament_id: str) -> Optional[TournamentConfig]:
        tournaments = self._load_tournaments()
        for t_dict in tournaments:
            if t_dict.get("id") == tournament_id:
                return TournamentConfig(**t_dict)
        return None

    def add_player_to_tournament(self, tournament_id: str, player_id: str) -> Optional[TournamentConfig]:
        tournaments = self._load_tournaments()
        updated_tournament_dict = None
        for i, t_dict in enumerate(tournaments):
            if t_dict.get("id") == tournament_id:
                tournament = TournamentConfig(**t_dict) # Validate existing data
                if player_id not in tournament.player_ids:
                    tournament.player_ids.append(player_id)
                    # Optional: Check tournament status before allowing player addition
                    # if tournament.status not in ["PENDING", "REGISTRATION_OPEN"]:
                    #     raise ValueError("Players can only be added when tournament is PENDING or REGISTRATION_OPEN.")
                    tournaments[i] = tournament.model_dump()
                    updated_tournament_dict = tournaments[i]
                    break
                else:
                    # Player already in tournament, return current state
                    return tournament 
        
        if updated_tournament_dict:
            self._save_tournaments(tournaments)
            return TournamentConfig(**updated_tournament_dict)
        # If player was already in, we returned the tournament earlier.
        # If tournament was not found by id, this will return None.
        # This logic path means tournament_id was valid, but player_id might already be in.
        # The current implementation returns the tournament object if player_id is already present.
        # If tournament_id itself is invalid, loop completes, updated_tournament_dict is None, returns None.
        
        # To clarify: if tournament ID is found, but player is already in it, it returns the existing tournament object.
        # If tournament ID is not found, it returns None.
        tournament_to_return = None
        for t_dict in tournaments:
            if t_dict.get("id") == tournament_id:
                tournament_to_return = TournamentConfig(**t_dict)
                break
        return tournament_to_return


    def get_tournaments_by_admin(self, admin_id: str) -> List[TournamentConfig]:
        tournaments = self._load_tournaments()
        admin_tournaments = []
        for t_dict in tournaments:
            if t_dict.get("admin_id") == admin_id:
                admin_tournaments.append(TournamentConfig(**t_dict))
        return admin_tournaments

    def update_tournament_status(self, tournament_id: str, status: str) -> Optional[TournamentConfig]:
        tournaments = self._load_tournaments()
        updated_tournament_dict = None

        # Validate status using the model's validator implicitly by trying to set it
        try:
            TournamentConfig(id="temp", name="temp", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="temp", status=status)
        except ValueError as e:
            raise ValueError(f"Invalid status value: {status}. {str(e)}")


        for i, t_dict in enumerate(tournaments):
            if t_dict.get("id") == tournament_id:
                # Create a TournamentConfig instance to leverage Pydantic validation
                tournament = TournamentConfig(**t_dict)
                tournament.status = status # This will use the validator in TournamentConfig
                tournaments[i] = tournament.model_dump()
                updated_tournament_dict = tournaments[i]
                break
        
        if updated_tournament_dict:
            self._save_tournaments(tournaments)
            return TournamentConfig(**updated_tournament_dict)
        return None

    def get_all_tournaments(self) -> List[TournamentConfig]:
        """Helper function to get all tournaments, useful for general listing."""
        tournaments_data = self._load_tournaments()
        return [TournamentConfig(**t_data) for t_data in tournaments_data]

    def update_tournament(self, tournament_id: str, updated_data: TournamentConfig) -> Optional[TournamentConfig]:
        """Updates an existing tournament with new data."""
        tournaments = self._load_tournaments()
        tournament_found = False
        for i, t_dict in enumerate(tournaments):
            if t_dict.get("id") == tournament_id:
                # Ensure IDs are not changed, admin_id also should not change via this method
                if updated_data.id != tournament_id:
                    raise ValueError("Tournament ID cannot be changed.")
                if updated_data.admin_id != t_dict.get("admin_id"):
                    raise ValueError("Admin ID cannot be changed during update.")
                
                tournaments[i] = updated_data.model_dump()
                tournament_found = True
                break
        
        if tournament_found:
            self._save_tournaments(tournaments)
            return updated_data
        return None

    def delete_tournament(self, tournament_id: str, admin_id: str) -> bool:
        """Deletes a tournament if the requesting user is the admin."""
        tournaments = self._load_tournaments()
        original_len = len(tournaments)
        
        # Only allow deletion if the tournament exists and admin_id matches
        tournaments_to_keep = []
        deleted = False
        for t_dict in tournaments:
            if t_dict.get("id") == tournament_id:
                if t_dict.get("admin_id") == admin_id:
                    # Optional: Check status, e.g., cannot delete "ACTIVE" or "COMPLETED" tournaments
                    # if t_dict.get("status") in ["ACTIVE", "COMPLETED"]:
                    #     raise ValueError(f"Cannot delete a tournament with status '{t_dict.get('status')}'.")
                    deleted = True
                    continue # Skip adding this tournament to the new list
            tournaments_to_keep.append(t_dict)
            
        if deleted:
            self._save_tournaments(tournaments_to_keep)
            return True
        
        if not any(t_dict.get("id") == tournament_id for t_dict in tournaments):
             raise ValueError("Tournament not found.")
        # If tournament exists but admin_id doesn't match
        if any(t_dict.get("id") == tournament_id and t_dict.get("admin_id") != admin_id for t_dict in tournaments):
            raise PermissionError("User is not authorized to delete this tournament.")
            
        return False

    # --- Invite Token Methods ---

    def generate_invite_token(self, tournament_id: str, admin_id: str) -> Optional[TournamentConfig]:
        tournaments = self._load_tournaments()
        updated_tournament_config = None

        for i, t_dict in enumerate(tournaments):
            if t_dict.get("id") == tournament_id:
                if t_dict.get("admin_id") != admin_id:
                    raise PermissionError("User is not authorized to generate an invite token for this tournament.")
                
                tournament = TournamentConfig(**t_dict)
                
                # If token exists and is not empty, return current tournament (or optionally regenerate)
                if tournament.invite_token:
                    return tournament 
                
                tournament.invite_token = secrets.token_urlsafe(16)
                tournaments[i] = tournament.model_dump()
                updated_tournament_config = tournament
                break
        
        if updated_tournament_config:
            self._save_tournaments(tournaments)
            return updated_tournament_config
        
        # If tournament not found by ID
        if not any(t_dict.get("id") == tournament_id for t_dict in tournaments):
            raise ValueError("Tournament not found.")
            
        return None # Should be covered by ValueError or PermissionError above

    def get_tournament_by_invite_token(self, token: str) -> Optional[TournamentConfig]:
        if not token: # Ensure token is not empty or None
            return None
        tournaments = self._load_tournaments()
        for t_dict in tournaments:
            if t_dict.get("invite_token") == token:
                return TournamentConfig(**t_dict)
        return None

    def join_tournament_with_token(self, token: str, user_id: str) -> Optional[TournamentConfig]:
        tournament = self.get_tournament_by_invite_token(token)
        
        if not tournament:
            raise ValueError("Invalid or expired invite token.") # Or return None

        # Check tournament status - e.g., can only join if PENDING or REGISTRATION_OPEN
        if tournament.status not in ["PENDING", "REGISTRATION_OPEN"]:
            raise ValueError(f"Tournament is not open for registration. Current status: {tournament.status}")

        if user_id in tournament.player_ids:
            # User is already part of the tournament
            return tournament # Or raise ValueError("User already in tournament.")

        tournament.player_ids.append(user_id)
        
        # Now update the tournament in the list
        tournaments = self._load_tournaments()
        found_and_updated = False
        for i, t_dict in enumerate(tournaments):
            if t_dict.get("id") == tournament.id:
                tournaments[i] = tournament.model_dump()
                found_and_updated = True
                break
        
        if found_and_updated:
            self._save_tournaments(tournaments)
            return tournament
        else:
            # This should ideally not happen if get_tournament_by_invite_token worked
            raise RuntimeError("Failed to update tournament after adding player. Tournament consistency error.")
