import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Adjust the import path based on your project structure
# Assuming your FastAPI app instance is in 'app.main.app'
from app.main import app 
from app.services.tournament_service import TournamentService
from app.services.bracket_service import BracketService
from app.models.tournament_model import TournamentConfig, TournamentType
from app.models.bracket_model import BracketModel
from app.routes.tournament_routes import get_current_user_id # To override

# --- Test Client Fixture ---
@pytest.fixture
def client():
    return TestClient(app)

# --- Mocked Dependencies ---
@pytest.fixture
def mock_tournament_service_routes():
    # This mock will be injected into the routes
    mock = MagicMock(spec=TournamentService)
    return mock

@pytest.fixture
def mock_bracket_service_routes():
    mock = MagicMock(spec=BracketService)
    return mock

# Override authentication dependency for all tests in this file
MOCK_USER_ID = "test_user_admin_123"

def override_get_current_user_id():
    return MOCK_USER_ID

app.dependency_overrides[get_current_user_id] = override_get_current_user_id


class TestTournamentRoutesSmoke:

    def test_create_tournament_smoke(self, client: TestClient, mock_tournament_service_routes: MagicMock):
        # Replace the actual service instance used by the router with the mock
        # The tournament_routes.py creates its own instance: tournament_service = TournamentService()
        # We need to patch *that* instance.
        with patch('app.routes.tournament_routes.tournament_service', mock_tournament_service_routes):
            mock_tournament_config = TournamentConfig(
                id="tournament_smoke_1",
                name="Smoke Test Tournament",
                tournament_type=TournamentType.SINGLE_ELIMINATION,
                admin_id=MOCK_USER_ID,
                status="PENDING"
            )
            mock_tournament_service_routes.create_tournament.return_value = mock_tournament_config

            response = client.post(
                "/api/tournaments", # Prefix defined in main.py for tournament_routes
                json={
                    "name": "Smoke Test Tournament",
                    "tournament_type": "SINGLE_ELIMINATION",
                    # start_date and end_date are optional in DTO
                }
            )
            assert response.status_code == 201
            response_data = response.json()
            assert response_data["name"] == "Smoke Test Tournament"
            assert response_data["admin_id"] == MOCK_USER_ID
            assert response_data["id"] == "tournament_smoke_1"
            
            # Check that the service method was called with a TournamentConfig object
            # The actual argument to create_tournament in the route is a TournamentConfig instance.
            # We need to check that the call was made and the important fields match.
            args, kwargs = mock_tournament_service_routes.create_tournament.call_args
            assert args # Should have one positional argument (the TournamentConfig object)
            called_config_arg = args[0]
            assert isinstance(called_config_arg, TournamentConfig)
            assert called_config_arg.name == "Smoke Test Tournament"
            assert called_config_arg.admin_id == MOCK_USER_ID


    def test_generate_bracket_smoke(self, client: TestClient, mock_tournament_service_routes: MagicMock, mock_bracket_service_routes: MagicMock):
        tournament_id = "tourney_for_bracket_smoke"

        # Mock for get_tournament_if_admin dependency (which uses tournament_service directly)
        # The dependency `get_tournament_if_admin` calls `service.get_tournament_by_id`
        # where service is `tournament_service` from `tournament_routes.py`
        mock_admin_tournament_config = TournamentConfig(
            id=tournament_id,
            name="Bracket Smoke Tournament",
            tournament_type=TournamentType.SINGLE_ELIMINATION,
            admin_id=MOCK_USER_ID, # Ensures admin check passes
            status="REGISTRATION_OPEN" 
        )

        # Mock for the bracket service call
        mock_generated_bracket = BracketModel(
            id="bracket_smoke_1",
            tournament_id=tournament_id,
            tournament_type=TournamentType.SINGLE_ELIMINATION.value,
            matches=[], # Simplified for smoke test
            rounds_structure={}
        )
        
        # Patch the globally instantiated services in tournament_routes.py
        with patch('app.routes.tournament_routes.tournament_service', mock_tournament_service_routes):
            with patch('app.routes.tournament_routes.bracket_service_instance', mock_bracket_service_routes):
                
                # Setup the mock for the get_tournament_if_admin dependency
                mock_tournament_service_routes.get_tournament_by_id.return_value = mock_admin_tournament_config
                
                # Setup the mock for the bracket_service call
                mock_bracket_service_routes.create_bracket_for_tournament.return_value = mock_generated_bracket

                response = client.post(
                    f"/api/tournaments/{tournament_id}/generate-bracket"
                )

                assert response.status_code == 200
                response_data = response.json()
                assert response_data["id"] == "bracket_smoke_1"
                assert response_data["tournament_id"] == tournament_id
                
                mock_bracket_service_routes.create_bracket_for_tournament.assert_called_once_with(tournament_id)
                # Ensure get_tournament_by_id was called by the dependency
                mock_tournament_service_routes.get_tournament_by_id.assert_called_with(tournament_id)


# Cleanup the override after tests in this module are done
def reset_dependency_overrides():
    app.dependency_overrides = {}

# You can use a finalizer for this, or just call it if needed.
# For pytest, a fixture with module scope could handle this.
@pytest.fixture(scope="module", autouse=True)
def cleanup_overrides():
    yield
    reset_dependency_overrides()

pytest_plugins = ['pytester']
