# API Documentation: Audio Recording Backend

This document provides the necessary information to interact with the audio recording API from a frontend application.

## Authentication

The API uses **HTTP Basic Authentication**.

You must include an `Authorization` header with every request. The value should be the word `Basic` followed by a space and a Base64-encoded string of `username:password`.

-   **Username:** `admin`
-   **Password:** `admin`

The encoded value for `admin:admin` is `YWRtaW46YWRtaW4=`.w

**Example Header:**
```
Authorization: Basic YWRtaW46YWRtaW4=
```

---

## Upload a Recording

This endpoint is used to upload a new audio recording along with its metadata.

-   **URL:** `/api/v1/recordings`
-   **Method:** `POST`
-   **Content-Type:** `multipart/form-data`

### Form Fields

The request body must be `multipart/form-data` and include the following fields:

| Field Name   | Type          | Required | Description                                                  | Example Value                               |
|--------------|---------------|----------|--------------------------------------------------------------|---------------------------------------------|
| `audio`      | File          | Yes      | The audio file to be uploaded.                               | (binary file data)                          |
| `userId`     | string        | Yes      | The ID of the user. **Must match the authenticated user.**   | `"admin"`                                   |
| `sessionId`  | string        | Yes      | The ID of the current recording session.                     | `"session-abc-123"`                         |
| `datasetId`  | integer       | Yes      | The ID of the dataset this recording belongs to.             | `1`                                         |
| `phraseId`   | integer       | Yes      | The ID of the phrase being recorded.                         | `101`                                       |
| `duration`   | float         | Yes      | The duration of the audio in seconds.                        | `3.5`                                       |
| `recordedAt` | string (ISO)  | Yes      | The UTC timestamp when the recording was made.               | `"2025-12-30T22:00:00Z"`                    |
| `emotionId`  | integer       | No       | The ID of the emotion being expressed.                       | `2`                                         |
| `format`     | string        | No       | The format of the audio file (e.g., "wav", "webm").          | `"wav"`                                     |
| `deviceInfo` | JSON string   | No       | A valid JSON string containing information about the device. | `'{"manufacturer":"Apple","model":"iPhone14,3"}'` |

### Example: Frontend JavaScript `fetch`

Here is how you can send the request from a JavaScript frontend.

```javascript
async function uploadAudio(audioFile) {
  const formData = new FormData();

  // Append the audio file
  formData.append("audio", audioFile, "my-recording.wav");

  // Append metadata fields
  formData.append("userId", "admin");
  formData.append("sessionId", "session-abc-123");
  formData.append("datasetId", "1");
  formData.append("phraseId", "101");
  formData.append("duration", "3.5");
  formData.append("recordedAt", new Date().toISOString());
  formData.append("emotionId", "2");
  formData.append("format", "wav");
  formData.append("deviceInfo", JSON.stringify({
    manufacturer: "Browser",
    userAgent: navigator.userAgent
  }));

  const credentials = btoa("admin:admin"); // Base64 encode "admin:admin"

  try {
    const response = await fetch("/api/v1/recordings", {
      method: "POST",
      headers: {
        "Authorization": `Basic ${credentials}`
      },
      body: formData
    });

    if (!response.ok) {
      // Handle HTTP errors (e.g., 4xx, 5xx)
      const errorData = await response.json();
      console.error(`Error ${response.status}:`, errorData.detail);
      return;
    }

    const result = await response.json();
    console.log("Upload successful:", result);
    // {
    //   "recordingId": "rec_...",
    //   "driveFileId": "...",
    //   "uploadedAt": "..."
    // }

  } catch (error) {
    console.error("An error occurred during the upload:", error);
  }
}

// Example usage:
// const myAudioBlob = new Blob([...], { type: 'audio/wav' });
// uploadAudio(myAudioBlob);
```

### Success Response (201 Created)

On a successful upload, the API will return a JSON object with the following structure:

```json
{
  "recordingId": "rec_651902913d2b",
  "driveFileId": "1CplDzuQ7haD1QfULOIjwTPbiF13Nj9sI",
  "uploadedAt": "2025-12-30T21:45:53.852132"
}
```
