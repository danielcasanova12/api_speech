
import asyncio
import os
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from config import settings
from storage import get_gdrive_service

# --- Configuration ---
TEST_FILE_NAME = "test_upload_from_script.txt"
TEST_FILE_CONTENT = "This is a test file to verify Google Drive API access."

async def test_gdrive_upload():
    """
    Tests the full Google Drive upload process.
    1. Creates a local test file.
    2. Gets the Google Drive service.
    3. Uploads the file.
    4. Deletes the local test file.
    """
    print("--- Starting Google Drive Upload Test ---")

    # 1. Create a local test file
    print(f"1. Creating local test file: '{TEST_FILE_NAME}'")
    with open(TEST_FILE_NAME, "w") as f:
        f.write(TEST_FILE_CONTENT)

    media = None
    try:
        # 2. Get the Google Drive service
        print("2. Authenticating with Google Drive...")
        service = await get_gdrive_service()
        print("   Authentication successful.")

        # 3. Upload the file
        print(f"3. Uploading file to Drive Folder ID: ...{settings.GDRIVE_FOLDER_ID[-10:]}")
        file_metadata = {
            'name': TEST_FILE_NAME,
            'parents': [settings.GDRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(TEST_FILE_NAME, mimetype='text/plain')
        
        # The execute() call is blocking, so it should be run in a thread pool
        # but for a simple script, a direct call might be acceptable for testing.
        # However, to reuse get_gdrive_service, we are in an async context.
        # The service object itself is not async, but its methods are blocking.
        # For this test, we'll call it directly as it's simpler than setting up a thread pool here.
        # This is NOT best practice for an async app, but fine for a synchronous test script.
        
        # To properly call the blocking `execute` within our async test function,
        # we should use `run_in_threadpool`.
        loop = asyncio.get_running_loop()
        file = await loop.run_in_executor(
            None, 
            lambda: service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        )

        drive_file_id = file.get('id')
        print(f"   Upload successful! File ID: {drive_file_id}")
        print("\n--- TEST SUCCEEDED ---")
        return drive_file_id

    except HttpError as e:
        print(f"\n--- TEST FAILED ---")
        print(f"A Google API error occurred: {e}")
        if e.resp.status == 403:
            print("\n[!] This might be an API access issue.")
            print("Please ensure the Google Drive API is enabled for your project in the Google Cloud Console.")
            print("You might need to visit a URL similar to this:")
            print("https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=YOUR_PROJECT_ID")
        return None
    except Exception as e:
        print(f"\n--- TEST FAILED ---")
        print(f"An unexpected error occurred: {e}")
        return None

    finally:
        # 4. Clean up media object and local file
        # The MediaFileUpload object holds the file handle, which needs to be closed on Windows
        # before the file can be deleted.
        if media and hasattr(media, '_fd') and media._fd:
            media._fd.close()
        
        if os.path.exists(TEST_FILE_NAME):
            print(f"\n4. Cleaning up local file: '{TEST_FILE_NAME}'")
            os.remove(TEST_FILE_NAME)

if __name__ == "__main__":
    # Since the function is async, we need to run it in an event loop.
    asyncio.run(test_gdrive_upload())
