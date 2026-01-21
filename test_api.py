import requests
import json

# --- Configuration ---
BASE_URL = "https://34.204.18.104"  # Production API URL
AUTH = ("admin", "admin")  # Basic auth credentials from security.py

def test_root_endpoint():
    """Tests the root GET / endpoint."""
    print("--- Testing GET / ---")
    try:
        response = requests.get(f"{BASE_URL}/", verify=False)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(response.json())
        print("Root endpoint test PASSED.")
        
    except requests.exceptions.RequestException as e:
        print(f"Root endpoint test FAILED: {e}")
    print("-" * 25)

def test_get_session_endpoint():
    """
    Tests the GET /api/v1/sessions/{session_id} endpoint.
    This test first creates a session to ensure there is a session to fetch.
    """
    print("--- Testing GET /api/v1/sessions/{session_id} ---")
    session_id = None
    
    # 1. Create a new session to get a valid session_id
    try:
        print("Step 1: Creating a new session...")
        create_session_url = f"{BASE_URL}/api/v1/sessions"
        session_data = {
            "genero": "male",
            "dataset": "common_voice"
        }
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(
            create_session_url, 
            auth=AUTH, 
            data=json.dumps(session_data), 
            headers=headers,
            verify=False
        )
        response.raise_for_status()
        
        session_id = response.json().get("id")
        if not session_id:
            raise ValueError("Failed to get session_id from creation response.")
            
        print(f"Session created successfully with ID: {session_id}")

    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"Step 1 FAILED: Could not create a session to test against. Reason: {e}")
        # If we can't create a session, we can't test getting one.
        print("GET session test SKIPPED.")
        print("-" * 25)
        return

    # 2. Test the GET endpoint with the new session_id
    try:
        print(f"Step 2: Fetching session with ID {session_id}...")
        get_session_url = f"{BASE_URL}/api/v1/sessions/{session_id}"
        
        response = requests.get(get_session_url, auth=AUTH, verify=False)
        response.raise_for_status()
        
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(response.json())
        
        # Basic validation
        assert response.json()["id"] == session_id
        print("GET session test PASSED.")

    except requests.exceptions.RequestException as e:
        print(f"Step 2 FAILED: Could not fetch the session. Reason: {e}")
    except AssertionError:
        print("Step 2 FAILED: Response validation failed. The returned ID did not match the requested ID.")
    finally:
        print("-" * 25)


if __name__ == "__main__":
    print("Starting API tests...")
    test_root_endpoint()
    test_get_session_endpoint()
    print("All tests finished.")
