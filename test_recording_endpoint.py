import requests
import json
from datetime import datetime

# --- Configuration ---
BASE_URL = "https://34.204.18.104"  # Production API URL
AUTH = ("admin", "admin")  # Basic auth credentials
FILE_PATH = "audio.wav" # Ensure this file exists in the same directory

def create_session_for_test():
    """
    Creates a new session and returns its ID.
    """
    print("Attempting to create a new session...")
    create_session_url = f"{BASE_URL}/api/v1/sessions"
    session_data = {
        "genero": "male",
        "dataset": "common_voice"
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(
            create_session_url, 
            auth=AUTH, 
            data=json.dumps(session_data), 
            headers=headers,
            verify=False # Disable SSL verification for self-signed certs
        )
        response.raise_for_status()
        
        session_id = response.json().get("id")
        if not session_id:
            raise ValueError("Failed to get session_id from creation response.")
            
        print(f"Session created successfully with ID: {session_id}")
        return session_id

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not create a session. Reason: {e}")
        return None
    except ValueError as e:
        print(f"ERROR: {e}")
        return None

def test_recording_upload_endpoint():
    """
    Tests the POST /api/v1/recordings endpoint.
    """
    print("--- Testing POST /api/v1/recordings ---")
    
    session_id = create_session_for_test()
    if session_id is None:
        print("Recording upload test SKIPPED due to session creation failure.")
        print("-" * 25)
        return

    try:
        with open(FILE_PATH, "rb") as audio_file:
            # The form data for the recording
            form_data = {
                "id_session": str(session_id), # FastAPI expects form fields as strings
                "emocao": "neutral",
            }

            files = {
                "audio": (FILE_PATH, audio_file, "audio/wav")
            }

            # Send the POST request
            print(f"Sending POST request to {BASE_URL}/api/v1/recordings...")
            response = requests.post(
                url=f"{BASE_URL}/api/v1/recordings",
                auth=AUTH,
                data=form_data,
                files=files,
                verify=False # Disable SSL verification
            )
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            # Print the response
            print(f"Status Code: {response.status_code}")
            try:
                print("Response JSON:")
                print(response.json())
                print("Recording upload test PASSED.")
            except json.JSONDecodeError:
                print("Response Content (not JSON):")
                print(response.text)

    except FileNotFoundError:
        print(f"ERROR: The file '{FILE_PATH}' was not found. Please ensure 'dummy_audio.wav' exists.")
        print("Recording upload test FAILED.")
    except requests.exceptions.RequestException as e:
        print(f"Recording upload test FAILED: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during recording upload test: {e}")
    finally:
        print("-" * 25)

if __name__ == "__main__":
    print("Starting recording endpoint test...")
    test_recording_upload_endpoint()
    print("Recording endpoint test finished.")
