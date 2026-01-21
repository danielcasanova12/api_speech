
import requests
import json
from datetime import datetime
from database import init_db

# --- Initialize DB ---
init_db()

# --- Configuration ---
BASE_URL = "http://localhost:8000"
ENDPOINT = "/api/v1/recordings"
FILE_PATH = "dummy_audio.wav"
AUTH = ("admin", "admin")

# --- Payload ---
form_data = {
    "userId": "admin",
    "sessionId": "test-session-from-script",
    "datasetId": 1,
    "phraseId": 102,
    "duration": 1.8,
    "recordedAt": datetime.utcnow().isoformat() + "Z",
    "format": "wav",
    "deviceInfo": json.dumps({"manufacturer": "python_script", "model": "requests"}),
}

# --- File Upload ---
try:
    with open(FILE_PATH, "rb") as audio_file:
        files = {
            "audio": (FILE_PATH, audio_file, "audio/wav")
        }

        # --- Send Request ---
        print(f"Sending POST request to {BASE_URL}{ENDPOINT}...")
        response = requests.post(
            url=f"{BASE_URL}{ENDPOINT}",
            auth=AUTH,
            data=form_data,
            files=files
        )

        # --- Print Response ---
        print(f"Status Code: {response.status_code}")
        try:
            print("Response JSON:")
            print(response.json())
        except json.JSONDecodeError:
            print("Response Content:")
            print(response.text)

except FileNotFoundError:
    print(f"Error: The file '{FILE_PATH}' was not found.")
except requests.exceptions.ConnectionError as e:
    print(f"Connection Error: Could not connect to the server at {BASE_URL}.")
    print("Please ensure the FastAPI server is running.")
    print(f"Details: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
