import json
import os

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
TOURNAMENTS_FILE = os.path.join(DATA_DIR, "tournaments.json")

def initialize_data_files():
    # DATA_DIR is already created in a previous step, but this ensures it
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump([], f)
    if not os.path.exists(TOURNAMENTS_FILE):
        with open(TOURNAMENTS_FILE, 'w') as f:
            json.dump([], f)

initialize_data_files() # Call it to ensure files are there when module is imported

def read_json_file(filename: str) -> list:
    """
    Reads a JSON file and returns the list of objects.
    Returns an empty list if the file doesn't exist or is empty.
    Handles potential FileNotFoundError and json.JSONDecodeError.
    """
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            # Handle empty file case before json.load
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        # Log this error or handle more gracefully if needed
        print(f"Warning: Could not decode JSON from {filepath}. Returning empty list.")
        return []

def write_json_file(filename: str, data: list):
    """
    Writes the data to the JSON file with an indent for readability.
    """
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
