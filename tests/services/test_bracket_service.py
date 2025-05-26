import pytest
import os
import json
import uuid
from unittest.mock import MagicMock, patch

from app.models.bracket_model import BracketModel, MatchModel, MatchStatus
from app.models.tournament_model import TournamentConfig, TournamentType
from app.services.bracket_service import BracketService, BRACKETS_FILE as ACTUAL_BRACKETS_FILE
from app.services.tournament_service import TournamentService
from app.services.user_service import UserService

TEST_BRACKETS_FILE = "test_brackets.json"

# Helper to generate unique player IDs
def new_player_id():
    return str(uuid.uuid4())

@pytest.fixture
def temp_brackets_file(tmp_path):
    return tmp_path / TEST_BRACKETS_FILE

@pytest.fixture
def mock_tournament_service():
    service = MagicMock(spec=TournamentService)
    # Default mock behaviors
    service.get_tournament_by_id.return_value = None # Default to not found
    service.update_tournament_status = MagicMock() # Ensure it can be called
    return service

@pytest.fixture
def mock_user_service():
    return MagicMock(spec=UserService)

@pytest.fixture
def bracket_service(temp_brackets_file, mock_tournament_service, mock_user_service):
    # It's important that BracketService uses the MOCKED TournamentService instance
    with patch('app.services.bracket_service.TournamentService', return_value=mock_tournament_service):
        with patch('app.services.bracket_service.UserService', return_value=mock_user_service):
            service = BracketService(
                brackets_file_path=str(temp_brackets_file),
                tournament_service=mock_tournament_service, # Explicitly pass mock
                user_service=mock_user_service      # Explicitly pass mock
            )
            if os.path.exists(str(temp_brackets_file)):
                os.remove(str(temp_brackets_file))
            # Re-initialize to ensure clean state with the mocked path
            service = BracketService(
                brackets_file_path=str(temp_brackets_file),
                tournament_service=mock_tournament_service,
                user_service=mock_user_service
            )
            yield service
            if os.path.exists(str(temp_brackets_file)):
                os.remove(str(temp_brackets_file))


class TestBracketServiceGenerateSingleElimination:

    def test_generate_4_players(self, bracket_service: BracketService):
        player_ids = [new_player_id() for _ in range(4)]
        tournament_id = str(uuid.uuid4())
        
        matches, rounds = bracket_service._generate_single_elimination_matches(player_ids, tournament_id)
        
        assert len(matches) == 3 # 2 first round, 1 final
        assert len(rounds) == 2 # 2 rounds
        assert len(rounds[1]) == 2 # 2 matches in round 1
        assert len(rounds[2]) == 1 # 1 match in round 2 (final)

        # Check first round matches
        r1m1 = next(m for m in matches if m.round_number == 1 and m.match_in_round == 1)
        r1m2 = next(m for m in matches if m.round_number == 1 and m.match_in_round == 2)
        
        # Check final match
        final_match = next(m for m in matches if m.round_number == 2 and m.match_in_round == 1)

        assert r1m1.next_match_id == final_match.id
        assert r1m1.winner_to_player_slot == 1
        assert r1m2.next_match_id == final_match.id
        assert r1m2.winner_to_player_slot == 2
        
        assert final_match.player1_id is None # To be filled by winner of r1m1
        assert final_match.player2_id is None # To be filled by winner of r1m2
        assert final_match.next_match_id is None # It's the final

        # Ensure all players from player_ids are in the first round matches
        initial_players_in_matches = {r1m1.player1_id, r1m1.player2_id, r1m2.player1_id, r1m2.player2_id}
        assert initial_players_in_matches == set(player_ids)


    def test_generate_5_players_with_byes(self, bracket_service: BracketService):
        player_ids = [new_player_id() for _ in range(5)]
        tournament_id = str(uuid.uuid4())

        matches, rounds = bracket_service._generate_single_elimination_matches(player_ids, tournament_id)
        
        # Bracket size: 8. Byes: 8 - 5 = 3.
        # Round 1: 3 BYE matches, 1 actual match ((5-3)/2 = 1)
        # Total matches: bracket_size - 1 = 7
        assert len(matches) == 7 
        assert len(rounds) == 3 # log2(8) = 3 rounds

        round1_matches = [m for m in matches if m.round_number == 1]
        assert len(round1_matches) == 4 # 3 byes + 1 actual match
        
        bye_matches_r1 = [m for m in round1_matches if m.status == MatchStatus.BYE]
        actual_matches_r1 = [m for m in round1_matches if m.status == MatchStatus.PENDING]
        assert len(bye_matches_r1) == 3
        assert len(actual_matches_r1) == 1

        # Verify byes players are among the initial player_ids
        bye_player_ids_r1 = {m.player1_id for m in bye_matches_r1}
        assert len(bye_player_ids_r1) == 3
        for pid in bye_player_ids_r1:
            assert pid in player_ids

        # Verify players in the actual match are also from the initial list and distinct from byes
        actual_match_pids = {actual_matches_r1[0].player1_id, actual_matches_r1[0].player2_id}
        assert len(actual_match_pids) == 2
        for pid in actual_match_pids:
            assert pid in player_ids
        assert not bye_player_ids_r1.intersection(actual_match_pids)


        # Check linking for round 2 matches
        round2_matches = [m for m in matches if m.round_number == 2]
        assert len(round2_matches) == 2 
        
        # One R2 match will take winner of actual R1 match + one bye
        # The other R2 match will take two byes
        
        # Find the R1 actual match
        r1_actual_match = actual_matches_r1[0]
        
        # Find R2 matches and their sources
        for r2_match in round2_matches:
            # Check if r1_actual_match feeds into this r2_match
            if r1_actual_match.next_match_id == r2_match.id:
                if r1_actual_match.winner_to_player_slot == 1:
                    assert r2_match.player1_id is None # From match
                    assert r2_match.player2_id in bye_player_ids_r1 # From bye
                else: # slot == 2
                    assert r2_match.player2_id is None # From match
                    assert r2_match.player1_id in bye_player_ids_r1 # From bye
            else: # This r2_match must be formed by two byes
                assert r2_match.player1_id in bye_player_ids_r1
                assert r2_match.player2_id in bye_player_ids_r1
                assert r2_match.player1_id != r2_match.player2_id
        
        # Check linking to final (round 3)
        round3_matches = [m for m in matches if m.round_number == 3]
        assert len(round3_matches) == 1
        final_match = round3_matches[0]
        
        for r2_match in round2_matches:
            assert r2_match.next_match_id == final_match.id
            assert r2_match.winner_to_player_slot in [1, 2]


class TestBracketServiceRecordMatchResultAndAdvancement:

    @pytest.fixture
    def setup_3_player_tournament(self, bracket_service: BracketService, mock_tournament_service):
        tournament_id = str(uuid.uuid4())
        admin_user_id = "admin_3p"
        player_ids = [new_player_id() for _ in range(3)] # P1, P2, P3

        # Mock TournamentService to return this specific tournament
        mock_tournament_config = TournamentConfig(
            id=tournament_id,
            name="3 Player Test Tournament",
            tournament_type=TournamentType.SINGLE_ELIMINATION,
            admin_id=admin_user_id,
            player_ids=player_ids,
            status="ACTIVE" # Assume bracket already generated
        )
        mock_tournament_service.get_tournament_by_id.return_value = mock_tournament_config
        
        # Generate bracket (bracket_size 4, 1 bye)
        # Player P1 gets a bye (shuffled_players[0])
        # P2 vs P3 play in M1 (shuffled_players[1] vs shuffled_players[2])
        # Winner of M1 plays P1 in M2 (Final)
        
        # To control who gets bye, we can patch random.shuffle or pre-sort player_ids
        # For this test, let's assume player_ids[0] gets the bye
        with patch('random.shuffle', side_effect=lambda x: x): # Keep original order
             bracket = bracket_service.create_bracket_for_tournament(tournament_id)
        
        assert bracket is not None
        # M0: P0 vs BYE (P0 wins, status BYE)
        # M1: P1 vs P2 (PENDING)
        # M2: (Winner M0) vs (Winner M1) (PENDING, FINAL)

        bye_match = next(m for m in bracket.matches if m.status == MatchStatus.BYE)
        first_playable_match = next(m for m in bracket.matches if m.status == MatchStatus.PENDING and m.round_number == 1)
        final_match = next(m for m in bracket.matches if m.round_number == 2) # Should be only one

        assert bye_match.player1_id == player_ids[0] # P0 gets bye
        assert first_playable_match.player1_id == player_ids[1] # P1
        assert first_playable_match.player2_id == player_ids[2] # P2

        assert bye_match.next_match_id == final_match.id
        assert bye_match.winner_to_player_slot == 1 # P0 (bye winner) goes to slot 1 of final
        
        assert first_playable_match.next_match_id == final_match.id
        assert first_playable_match.winner_to_player_slot == 2 # Winner of P1vP2 goes to slot 2 of final

        assert final_match.player1_id == player_ids[0] # P0 advanced from bye
        assert final_match.player2_id is None # Waiting for winner of P1vP2
        
        return tournament_id, admin_user_id, player_ids, bracket, first_playable_match, final_match

    def test_record_first_match_and_advance(self, bracket_service: BracketService, mock_tournament_service, setup_3_player_tournament):
        tournament_id, admin_user_id, player_ids, _, first_playable_match, final_match = setup_3_player_tournament
        
        # P1 (player_ids[1]) vs P2 (player_ids[2]). Let P1 win.
        winner_of_first_match = player_ids[1] 
        
        updated_match = bracket_service.record_match_result(
            tournament_id, first_playable_match.id, 10, 5, admin_user_id
        )
        assert updated_match is not None
        assert updated_match.status == MatchStatus.PLAYER1_WIN
        assert updated_match.winner_id == winner_of_first_match

        # Verify advancement
        # Reload bracket to see changes
        updated_bracket = bracket_service.get_bracket_by_tournament_id(tournament_id)
        assert updated_bracket is not None
        
        final_match_reloaded = next(m for m in updated_bracket.matches if m.id == final_match.id)
        assert final_match_reloaded.player1_id == player_ids[0] # Bye player
        assert final_match_reloaded.player2_id == winner_of_first_match # Winner advanced

        # Tournament status should not be COMPLETED yet
        mock_tournament_service.update_tournament_status.assert_not_called()

    def test_record_final_match_and_complete_tournament(self, bracket_service: BracketService, mock_tournament_service, setup_3_player_tournament):
        tournament_id, admin_user_id, player_ids, _, first_playable_match, final_match = setup_3_player_tournament

        # First, P1 (player_ids[1]) wins against P2 (player_ids[2]) in the first match
        winner_of_first_match = player_ids[1]
        bracket_service.record_match_result(tournament_id, first_playable_match.id, 10, 5, admin_user_id)
        
        # Now, record result for the final match: P0 (player_ids[0]) vs Winner of M1 (player_ids[1])
        # Let P0 (bye player) win the final.
        tournament_winner = player_ids[0]
        
        updated_final_match = bracket_service.record_match_result(
            tournament_id, final_match.id, 10, 3, admin_user_id # P0 is player1 in final_match
        )
        assert updated_final_match is not None
        assert updated_final_match.status == MatchStatus.PLAYER1_WIN
        assert updated_final_match.winner_id == tournament_winner
        
        # Verify tournament status is updated to COMPLETED
        mock_tournament_service.update_tournament_status.assert_called_once_with(tournament_id, "COMPLETED")

    def test_record_match_result_unauthorized(self, bracket_service: BracketService, mock_tournament_service, setup_3_player_tournament):
        tournament_id, _, _, _, first_playable_match, _ = setup_3_player_tournament
        
        with pytest.raises(PermissionError, match="User is not authorized to record match results"):
            bracket_service.record_match_result(tournament_id, first_playable_match.id, 10, 5, "not_the_admin_user")

    def test_record_match_result_draw_error_single_elim(self, bracket_service: BracketService, mock_tournament_service, setup_3_player_tournament):
        tournament_id, admin_user_id, _, _, first_playable_match, _ = setup_3_player_tournament
        
        with pytest.raises(ValueError, match="Scores cannot be equal in a single elimination match"):
            bracket_service.record_match_result(tournament_id, first_playable_match.id, 5, 5, admin_user_id)

    def test_record_match_result_already_completed(self, bracket_service: BracketService, mock_tournament_service, setup_3_player_tournament):
        tournament_id, admin_user_id, _, _, first_playable_match, _ = setup_3_player_tournament
        
        # Record it once
        bracket_service.record_match_result(tournament_id, first_playable_match.id, 10, 5, admin_user_id)
        
        # Try to record again
        with pytest.raises(ValueError, match="Match status is 'PLAYER1_WIN'. Only PENDING matches can be updated."):
            bracket_service.record_match_result(tournament_id, first_playable_match.id, 11, 6, admin_user_id)

pytest_plugins = ['pytester']
