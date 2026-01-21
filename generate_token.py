import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# --- CONFIGURATION ---
# This is the file you downloaded from Google Cloud Console
CLIENT_SECRETS_FILE = "client_secret.json" 
# This is the file that will be created with your refresh token
TOKEN_FILE = "token.json"
# This defines what the script is allowed to do.
SCOPES = ["https://www.googleapis.com/auth/drive"]

def generate_token():
    """
    Starts the OAuth 2.0 flow to get a refresh token.
    """
    creds = None
    # Check if token file already exists
    if os.path.exists(TOKEN_FILE):
        print(f"'{TOKEN_FILE}' already exists. Delete it if you want to re-authenticate.")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Credentials expired, refreshing...")
            creds.refresh(Request())
        else:
            print("Starting new user authentication...")
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"ERROR: Client secrets file not found at '{CLIENT_SECRETS_FILE}'")
                print("Please download it from Google Cloud Console and place it in this directory.")
                return

            # This starts a local web server to handle the auth redirect.
            # It will open a new tab in your default browser.
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        print(f"Authentication successful. Token saved to '{TOKEN_FILE}'!")

if __name__ == "__main__":
    generate_token()
