import pytest
from unittest.mock import patch, mock_open, MagicMock
import os
import json

from app.models.user_model import UserModel
from app.services.user_service import UserService, USERS_FILE as ACTUAL_USERS_FILE

# Use a temporary file for testing that can be cleaned up or ignored
TEST_USERS_FILE = "test_users.json"

@pytest.fixture
def temp_users_file(tmp_path):
    # Create a temporary file path for user data
    return tmp_path / TEST_USERS_FILE

@pytest.fixture
def user_service(temp_users_file):
    # Patch the USERS_FILE constant within the user_service module for the duration of the test
    with patch('app.services.user_service.USERS_FILE', str(temp_users_file)):
        service = UserService(data_file_path=str(temp_users_file))
        # Ensure the file is empty before each test if it's created by UserService constructor
        if os.path.exists(str(temp_users_file)):
            os.remove(str(temp_users_file))
        # Re-initialize to ensure it creates a new empty file
        service = UserService(data_file_path=str(temp_users_file))
        yield service
        # Clean up the temporary file after tests if it exists
        if os.path.exists(str(temp_users_file)):
            os.remove(str(temp_users_file))


class TestUserService:

    def test_create_user_success(self, user_service: UserService, temp_users_file):
        user_data = UserModel(
            email="test@example.com",
            full_name="Test User",
            oauth_provider="google",
            oauth_provider_id="12345"
        )
        created_user = user_service.create_user(user_data)
        assert created_user.email == "test@example.com"
        assert created_user.id is not None

        # Verify it's saved
        with open(temp_users_file, "r") as f:
            users_in_file = json.load(f)
        assert len(users_in_file) == 1
        assert users_in_file[0]["email"] == "test@example.com"

    def test_create_user_duplicate_email(self, user_service: UserService):
        user_data1 = UserModel(
            email="duplicate@example.com",
            oauth_provider="google",
            oauth_provider_id="1"
        )
        user_service.create_user(user_data1)

        user_data2 = UserModel(
            email="duplicate@example.com", # Same email
            oauth_provider="google",
            oauth_provider_id="2" # Different oauth_id
        )
        with pytest.raises(ValueError, match="User with email duplicate@example.com already exists."):
            user_service.create_user(user_data2)

    def test_create_user_duplicate_oauth_id(self, user_service: UserService):
        user_data1 = UserModel(
            email="user1@example.com",
            oauth_provider="google",
            oauth_provider_id="123_abc"
        )
        user_service.create_user(user_data1)

        user_data2 = UserModel(
            email="user2@example.com", # Different email
            oauth_provider="google", # Same provider
            oauth_provider_id="123_abc" # Same oauth_id
        )
        with pytest.raises(ValueError, match="User with google ID 123_abc already exists."):
            user_service.create_user(user_data2)


    def test_get_user_by_email_found(self, user_service: UserService):
        user_data = UserModel(
            email="findme@example.com",
            oauth_provider="google",
            oauth_provider_id="find123"
        )
        user_service.create_user(user_data)

        found_user = user_service.get_user_by_email("findme@example.com")
        assert found_user is not None
        assert found_user.email == "findme@example.com"
        assert found_user.oauth_provider_id == "find123"

    def test_get_user_by_email_not_found(self, user_service: UserService):
        found_user = user_service.get_user_by_email("nonexistent@example.com")
        assert found_user is None

    def test_get_user_by_oauth_id_found(self, user_service: UserService):
        user_data = UserModel(
            email="oauthuser@example.com",
            oauth_provider="apple",
            oauth_provider_id="oauth_test_id"
        )
        user_service.create_user(user_data)

        found_user = user_service.get_user_by_oauth_id(provider="apple", oauth_id="oauth_test_id")
        assert found_user is not None
        assert found_user.email == "oauthuser@example.com"
        assert found_user.oauth_provider == "apple"

    def test_get_user_by_oauth_id_not_found(self, user_service: UserService):
        found_user = user_service.get_user_by_oauth_id(provider="google", oauth_id="nonexistent_oauth")
        assert found_user is None

    def test_get_user_by_oauth_id_wrong_provider(self, user_service: UserService):
        user_data = UserModel(
            email="oauthuser2@example.com",
            oauth_provider="google",
            oauth_provider_id="google_id_1"
        )
        user_service.create_user(user_data)
        
        found_user = user_service.get_user_by_oauth_id(provider="apple", oauth_id="google_id_1") # Correct ID, wrong provider
        assert found_user is None

    def test_load_users_file_not_found(self, user_service, temp_users_file):
        # Ensure file does not exist initially for this specific test
        if os.path.exists(temp_users_file):
            os.remove(temp_users_file)
        # UserService constructor might create it, so we test _load_users directly or re-instantiate
        service_new = UserService(data_file_path=str(temp_users_file)) # this will create it
        # to test the "if not os.path.exists" in _load_users, we need to remove it after construction
        if os.path.exists(str(temp_users_file)):
             os.remove(str(temp_users_file))
        
        users = service_new._load_users() # Call directly to bypass constructor's auto-creation
        assert users == []

    def test_load_users_json_decode_error(self, user_service, temp_users_file):
        with open(temp_users_file, "w") as f:
            f.write("this is not json")
        
        users = user_service._load_users()
        assert users == []

    def test_user_model_datetime_serialization(self, user_service: UserService):
        user_data = UserModel(
            email="datetime@example.com",
            oauth_provider="google",
            oauth_provider_id="dt123"
        )
        user_service.create_user(user_data)
        
        # Load raw data
        with open(user_service.data_file_path, "r") as f:
            raw_data = json.load(f)
        
        assert "created_at" in raw_data[0]
        # Check if it's a string in ISO format (Pydantic's default JSON export for datetime)
        assert isinstance(raw_data[0]["created_at"], str)
        
        # Check if it can be parsed back by UserModel
        loaded_user = user_service.get_user_by_email("datetime@example.com")
        assert loaded_user is not None
        assert isinstance(loaded_user.created_at, str) # Our model now stores it as string after model_dump
        # If we wanted datetime objects after loading, UserModel would need custom parsing or
        # the service would convert it. Pydantic v2 handles this better with `datetime_parse_str`
        # For now, our service returns UserModel which stores created_at as datetime.
        # The user_data.model_dump() in create_user uses json_encoders.
        # Let's re-verify the type from get_user_by_email
        
        # Re-create user_service for a clean load using the file just written
        new_service = UserService(data_file_path=user_service.data_file_path)
        retrieved_user = new_service.get_user_by_email("datetime@example.com")
        assert retrieved_user is not None
        # Pydantic should parse the ISO string back to a datetime object when creating UserModel instance
        from datetime import datetime
        assert isinstance(retrieved_user.created_at, datetime)

    def test_init_creates_directory_and_file(self, tmp_path):
        test_dir = tmp_path / "non_existent_dir"
        test_file_in_new_dir = test_dir / "users.json"
        
        assert not os.path.exists(test_dir)
        assert not os.path.exists(test_file_in_new_dir)
        
        UserService(data_file_path=str(test_file_in_new_dir))
        
        assert os.path.exists(test_dir)
        assert os.path.exists(test_file_in_new_dir)
        with open(test_file_in_new_dir, "r") as f:
            assert json.load(f) == [] # Should be an empty list
        
        # Clean up
        os.remove(test_file_in_new_dir)
        os.rmdir(test_dir)

pytest_plugins = ['pytester']
