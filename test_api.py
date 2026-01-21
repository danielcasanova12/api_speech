import requests
from datetime import datetime
import json

# The URL of the API endpoint
url = "https://34.204.18.104/api/v1/recordings"

# The basic auth credentials
auth = ("admin", "admin")

# The path to the dummy audio file
file_path = "dummy_audio.wav"

# The origin from which you are making the request
origin = "https://dataset-1239123123.web.app"

# The headers for the request
headers = {
    "Origin": origin,
}

# The form data
form_data = {
    "userId": "admin",
    "sessionId": "test-session-123",
    "datasetId": 1,
    "phraseId": 1,
    "recordedAt": datetime.utcnow().isoformat(),
    "emotionId": 0,
    "format": "wav",
}

# The device info
device_info = {
    "browser": "test-script",
    "os": "linux",
}

# The files to upload and other form data
files = {
    "audio": (file_path, open(file_path, "rb"), "audio/wav"),
    "userId": (None, form_data["userId"]),
    "sessionId": (None, form_data["sessionId"]),
    "datasetId": (None, str(form_data["datasetId"])),
    "phraseId": (None, str(form_data["phraseId"])),
    "recordedAt": (None, form_data["recordedAt"]),
    "emotionId": (None, str(form_data["emotionId"])),
    "format": (None, form_data["format"]),
    "deviceInfo": (None, json.dumps(device_info)),
}


try:
    # Make the POST request
    # We use verify=False to ignore SSL certificate verification for self-signed certificates
    response = requests.post(url, auth=auth, headers=headers, files=files, verify=False)

    # Print the response status code
    print(f"Status Code: {response.status_code}")

    # Print the response headers
    print("Response Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")

    # Print the response content
    try:
        print("Response JSON:")
        print(response.json())
    except requests.exceptions.JSONDecodeError:
        print("Response Content (not JSON):")
        print(response.text)

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")