import sqlite3
import json
import os

DATABASE_FILE = "recordings.db"

def show_all_recordings():
    """Connects to the database and prints all recordings."""
    if not os.path.exists(DATABASE_FILE):
        print(f"Error: The database file '{DATABASE_FILE}' was not found.")
        print("Please run the FastAPI server and upload a file first to create the database.")
        return

    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM recordings")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("The 'recordings' table is empty. No recordings have been saved yet.")
            return

        print(f"Found {len(rows)} recording(s):\n")
        for i, row in enumerate(rows):
            print(f"--- Recording {i+1} ---")
            for key in row.keys():
                value = row[key]
                if key == 'device_info' and value:
                    try:
                        device_info_dict = json.loads(value)
                        print(f"{key}:")
                        # Indent the JSON for readability
                        print(json.dumps(device_info_dict, indent=2))
                    except json.JSONDecodeError:
                        print(f"{key}: {value} (Invalid JSON in DB)")
                else:
                    print(f"{key}: {value}")
            print("-" * 20)
            print()

    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print("Error: The 'recordings' table was not found in the database.")
            print("This might happen if the server was started before the database code was added.")
            print("Try deleting the 'recordings.db' file and restarting the server.")
        else:
            print(f"A database error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    show_all_recordings()
