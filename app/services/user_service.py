import json
import os
from typing import List, Optional, Dict, Any
from app.models.user_model import UserModel

DATA_DIR = "app/data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")

class UserService:
    def __init__(self, data_file_path: str = USERS_FILE):
        self.data_file_path = data_file_path
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.data_file_path), exist_ok=True)
        # Create the file if it doesn't exist
        if not os.path.exists(self.data_file_path):
            self._save_users([])

    def _load_users(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.data_file_path):
            return []
        try:
            with open(self.data_file_path, "r") as f:
                users = json.load(f)
                # Convert created_at back to datetime objects if needed, Pydantic does this on validation
                return users
        except json.JSONDecodeError:
            # Handle case where file is empty or corrupted
            return []

    def _save_users(self, users: List[Dict[str, Any]]):
        with open(self.data_file_path, "w") as f:
            json.dump(users, f, indent=4, default=str) # Use default=str for datetime serialization

    def create_user(self, user_data: UserModel) -> UserModel:
        users = self._load_users()
        
        # Check for email uniqueness
        for u_dict in users:
            if u_dict.get("email") == user_data.email:
                raise ValueError(f"User with email {user_data.email} already exists.")
        
        # Check for OAuth ID uniqueness (optional, but good practice)
        for u_dict in users:
            if u_dict.get("oauth_provider") == user_data.oauth_provider and \
               u_dict.get("oauth_provider_id") == user_data.oauth_provider_id:
                raise ValueError(
                    f"User with {user_data.oauth_provider} ID {user_data.oauth_provider_id} already exists."
                )

        user_dict = user_data.model_dump()
        users.append(user_dict)
        self._save_users(users)
        return user_data

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        users = self._load_users()
        for user_dict in users:
            if user_dict.get("email") == email:
                return UserModel(**user_dict)
        return None

    def get_user_by_oauth_id(self, provider: str, oauth_id: str) -> Optional[UserModel]:
        users = self._load_users()
        for user_dict in users:
            if user_dict.get("oauth_provider") == provider and user_dict.get("oauth_provider_id") == oauth_id:
                return UserModel(**user_dict)
        return None
