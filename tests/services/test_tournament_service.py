import pytest
import os
import json
from datetime import datetime, timedelta

from app.models.tournament_model import TournamentConfig, TournamentType
from app.services.tournament_service import TournamentService, TOURNAMENTS_FILE as ACTUAL_TOURNAMENTS_FILE

TEST_TOURNAMENTS_FILE = "test_tournaments.json"

@pytest.fixture
def temp_tournaments_file(tmp_path):
    return tmp_path / TEST_TOURNAMENTS_FILE

@pytest.fixture
def tournament_service(temp_tournaments_file):
    original_file_path = ACTUAL_TOURNAMENTS_FILE
    try:
        # Temporarily patch the module-level constant
        TournamentService.data_file_path = str(temp_tournaments_file) # Not ideal, better to pass in constructor if possible
                                                                # Or patch 'app.services.tournament_service.TOURNAMENTS_FILE'
        
        # For this test structure, we'll rely on the constructor using the patched path if available,
        # or directly instantiate with the test path.
        # The current TournamentService constructor takes data_file_path.
        
        service = TournamentService(data_file_path=str(temp_tournaments_file))
        if os.path.exists(str(temp_tournaments_file)):
            os.remove(str(temp_tournaments_file))
        service = TournamentService(data_file_path=str(temp_tournaments_file)) # Re-initialize to ensure clean state
        yield service
    finally:
        if os.path.exists(str(temp_tournaments_file)):
            os.remove(str(temp_tournaments_file))
        # Restore original path if we were patching a global
        # For this setup, instance-level path is fine.


class TestTournamentService:

    def test_create_tournament_success(self, tournament_service: TournamentService, temp_tournaments_file):
        config_data = TournamentConfig(
            name="Test Tournament 1",
            tournament_type=TournamentType.SINGLE_ELIMINATION,
            admin_id="admin123",
            start_date=datetime.utcnow() + timedelta(days=1)
        )
        created_tournament = tournament_service.create_tournament(config_data)
        assert created_tournament.name == "Test Tournament 1"
        assert created_tournament.admin_id == "admin123"
        assert created_tournament.id is not None
        assert created_tournament.status == "PENDING"

        with open(temp_tournaments_file, "r") as f:
            tournaments_in_file = json.load(f)
        assert len(tournaments_in_file) == 1
        assert tournaments_in_file[0]["name"] == "Test Tournament 1"

    def test_get_tournament_by_id_found(self, tournament_service: TournamentService):
        config_data = TournamentConfig(
            name="FindMe Tournament",
            tournament_type=TournamentType.ROUND_ROBIN,
            admin_id="admin_find"
        )
        created_tournament = tournament_service.create_tournament(config_data)
        
        found_tournament = tournament_service.get_tournament_by_id(created_tournament.id)
        assert found_tournament is not None
        assert found_tournament.name == "FindMe Tournament"
        assert found_tournament.id == created_tournament.id

    def test_get_tournament_by_id_not_found(self, tournament_service: TournamentService):
        found_tournament = tournament_service.get_tournament_by_id("nonexistent_id")
        assert found_tournament is None

    def test_add_player_to_tournament_success(self, tournament_service: TournamentService):
        tournament = tournament_service.create_tournament(TournamentConfig(name="Player Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="admin_pt"))
        
        player_id = "player_xyz"
        updated_tournament = tournament_service.add_player_to_tournament(tournament.id, player_id)
        
        assert updated_tournament is not None
        assert player_id in updated_tournament.player_ids
        
        # Verify persistence
        retrieved = tournament_service.get_tournament_by_id(tournament.id)
        assert player_id in retrieved.player_ids

    def test_add_player_to_tournament_already_added(self, tournament_service: TournamentService):
        tournament = tournament_service.create_tournament(TournamentConfig(name="Player Test Again", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="admin_pta"))
        player_id = "player_abc"
        
        tournament_service.add_player_to_tournament(tournament.id, player_id) # First add
        updated_tournament = tournament_service.add_player_to_tournament(tournament.id, player_id) # Second add
        
        assert updated_tournament is not None
        assert len(updated_tournament.player_ids) == 1 # Should not add duplicate
        assert updated_tournament.player_ids.count(player_id) == 1


    def test_add_player_to_tournament_not_found(self, tournament_service: TournamentService):
        result = tournament_service.add_player_to_tournament("fake_tournament_id", "player1")
        assert result is None

    def test_generate_invite_token_success(self, tournament_service: TournamentService):
        admin_id = "admin_invite_test"
        tournament = tournament_service.create_tournament(TournamentConfig(name="Invite Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id))
        
        updated_tournament = tournament_service.generate_invite_token(tournament.id, admin_id)
        assert updated_tournament is not None
        assert updated_tournament.invite_token is not None
        assert len(updated_tournament.invite_token) > 10 # Check for a reasonable token length

        # Verify persistence
        retrieved = tournament_service.get_tournament_by_id(tournament.id)
        assert retrieved.invite_token == updated_tournament.invite_token

    def test_generate_invite_token_unauthorized(self, tournament_service: TournamentService):
        tournament = tournament_service.create_tournament(TournamentConfig(name="Invite Unauthorized", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="original_admin"))
        
        with pytest.raises(PermissionError, match="User is not authorized to generate an invite token"):
            tournament_service.generate_invite_token(tournament.id, "fake_admin_id")

    def test_generate_invite_token_already_exists(self, tournament_service: TournamentService):
        admin_id = "admin_token_exists"
        tournament = tournament_service.create_tournament(TournamentConfig(name="Token Exists Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id))
        
        first_gen = tournament_service.generate_invite_token(tournament.id, admin_id)
        second_gen = tournament_service.generate_invite_token(tournament.id, admin_id) # Should return existing
        
        assert first_gen.invite_token == second_gen.invite_token


    def test_join_tournament_with_token_success(self, tournament_service: TournamentService):
        admin_id = "admin_join_test"
        tournament = tournament_service.create_tournament(TournamentConfig(name="Join Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id, status="REGISTRATION_OPEN"))
        tournament_with_token = tournament_service.generate_invite_token(tournament.id, admin_id)
        
        user_id_to_join = "user_wants_to_join"
        joined_tournament = tournament_service.join_tournament_with_token(tournament_with_token.invite_token, user_id_to_join)
        
        assert joined_tournament is not None
        assert user_id_to_join in joined_tournament.player_ids

    def test_join_tournament_with_invalid_token(self, tournament_service: TournamentService):
        with pytest.raises(ValueError, match="Invalid or expired invite token."):
            tournament_service.join_tournament_with_token("nonexistent_token", "user1")
            
    def test_join_tournament_not_open_for_registration(self, tournament_service: TournamentService):
        admin_id = "admin_closed_reg"
        tournament = tournament_service.create_tournament(TournamentConfig(name="Closed Reg Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id, status="ACTIVE")) # Not PENDING or REGISTRATION_OPEN
        tournament_with_token = tournament_service.generate_invite_token(tournament.id, admin_id)

        with pytest.raises(ValueError, match="Tournament is not open for registration. Current status: ACTIVE"):
            tournament_service.join_tournament_with_token(tournament_with_token.invite_token, "user_late")

    def test_join_tournament_user_already_joined(self, tournament_service: TournamentService):
        admin_id = "admin_already_joined"
        user_id = "player_early_bird"
        tournament = tournament_service.create_tournament(TournamentConfig(name="Already Joined Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id, status="REGISTRATION_OPEN", player_ids=[user_id]))
        tournament_with_token = tournament_service.generate_invite_token(tournament.id, admin_id)

        # Attempt to join again
        result_tournament = tournament_service.join_tournament_with_token(tournament_with_token.invite_token, user_id)
        assert result_tournament is not None # Service returns the tournament if user already joined
        assert result_tournament.player_ids.count(user_id) == 1 # Ensure no duplicates

    def test_update_tournament_status(self, tournament_service: TournamentService):
        tournament = tournament_service.create_tournament(TournamentConfig(name="Status Update Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="admin_status"))
        assert tournament.status == "PENDING"

        updated_tournament = tournament_service.update_tournament_status(tournament.id, "ACTIVE")
        assert updated_tournament is not None
        assert updated_tournament.status == "ACTIVE"

        retrieved = tournament_service.get_tournament_by_id(tournament.id)
        assert retrieved.status == "ACTIVE"

    def test_update_tournament_status_invalid_value(self, tournament_service: TournamentService):
        tournament = tournament_service.create_tournament(TournamentConfig(name="Invalid Status Test", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="admin_invalid_status"))
        
        with pytest.raises(ValueError, match="Invalid status value: JIBBERISH"):
            tournament_service.update_tournament_status(tournament.id, "JIBBERISH")

    def test_delete_tournament_success(self, tournament_service: TournamentService):
        admin_id = "admin_delete_me"
        tournament = tournament_service.create_tournament(TournamentConfig(name="Delete Me", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id))
        
        assert tournament_service.get_tournament_by_id(tournament.id) is not None
        
        delete_success = tournament_service.delete_tournament(tournament.id, admin_id)
        assert delete_success is True
        assert tournament_service.get_tournament_by_id(tournament.id) is None

    def test_delete_tournament_unauthorized(self, tournament_service: TournamentService):
        tournament = tournament_service.create_tournament(TournamentConfig(name="Delete Unauthorized", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="real_admin"))
        
        with pytest.raises(PermissionError, match="User is not authorized to delete this tournament."):
            tournament_service.delete_tournament(tournament.id, "imposter_admin")
        
        assert tournament_service.get_tournament_by_id(tournament.id) is not None # Should still exist
        
    def test_delete_tournament_not_found(self, tournament_service: TournamentService):
        with pytest.raises(ValueError, match="Tournament not found."):
            tournament_service.delete_tournament("fake_id_no_delete", "any_admin")

    def test_update_tournament_full(self, tournament_service: TournamentService):
        admin_id = "admin_update_test"
        original_tournament = tournament_service.create_tournament(
            TournamentConfig(name="Original Name", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id)
        )

        updated_data = original_tournament.model_copy(deep=True) # Get a copy
        updated_data.name = "Updated Name"
        updated_data.status = "REGISTRATION_OPEN"
        new_start_date = datetime.utcnow() + timedelta(days=5)
        updated_data.start_date = new_start_date

        updated_tournament = tournament_service.update_tournament(original_tournament.id, updated_data)
        
        assert updated_tournament is not None
        assert updated_tournament.name == "Updated Name"
        assert updated_tournament.status == "REGISTRATION_OPEN"
        assert updated_tournament.start_date == new_start_date
        assert updated_tournament.admin_id == admin_id # Should not change
        assert updated_tournament.id == original_tournament.id # Should not change

        retrieved = tournament_service.get_tournament_by_id(original_tournament.id)
        assert retrieved.name == "Updated Name"

    def test_update_tournament_id_mismatch(self, tournament_service: TournamentService):
        admin_id = "admin_id_mismatch"
        t1 = tournament_service.create_tournament(TournamentConfig(name="T1", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id))
        
        t1_updated_data = t1.model_copy(deep=True)
        t1_updated_data.id = "some_other_id" # Attempt to change ID
        
        with pytest.raises(ValueError, match="Tournament ID cannot be changed."):
            tournament_service.update_tournament(t1.id, t1_updated_data)

    def test_update_tournament_admin_id_mismatch(self, tournament_service: TournamentService):
        admin_id = "admin_admin_mismatch"
        t1 = tournament_service.create_tournament(TournamentConfig(name="T1 admin change", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id=admin_id))
        
        t1_updated_data = t1.model_copy(deep=True)
        t1_updated_data.admin_id = "new_admin_id_attempt" # Attempt to change admin_id
        
        with pytest.raises(ValueError, match="Admin ID cannot be changed during update."):
            tournament_service.update_tournament(t1.id, t1_updated_data)

    def test_update_tournament_not_found(self, tournament_service: TournamentService):
        non_existent_data = TournamentConfig(id="fake_id", name="Fake", tournament_type=TournamentType.SINGLE_ELIMINATION, admin_id="fake_admin")
        result = tournament_service.update_tournament("fake_id", non_existent_data)
        assert result is None

pytest_plugins = ['pytester']
