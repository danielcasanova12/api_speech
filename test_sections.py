import requests
import json
import os

# The URL of the API endpoint
url = "http://127.0.0.1:8000/api/v1/sections"

# The basic auth credentials
auth = ("admin", "admin")

# The headers for the request
headers = {
    "Content-Type": "application/json",
}

# The data for the new section
section_data = {
    "gender": "male",
    "dataset_type": "test"
}

try:
    # Make the POST request
    response = requests.post(url, auth=auth, headers=headers, data=json.dumps(section_data))

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
