import sqlite3
import json
from datetime import datetime

DATABASE_FILE = "recordings.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database and creates the 'sessions' and 'recordings' tables if they don't exist.
    """
    print("Initializing database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Drop existing tables for a clean setup
    cursor.execute("DROP TABLE IF EXISTS recordings")
    cursor.execute("DROP TABLE IF EXISTS sections")
    cursor.execute("DROP TABLE IF EXISTS sessions")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gender TEXT NOT NULL,
            dataset TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id_audio INTEGER PRIMARY KEY AUTOINCREMENT,
            id_session INTEGER NOT NULL,
            emotion TEXT,
            FOREIGN KEY (id_session) REFERENCES sessions (id)
        )
    """)
    
    # Set autoincrement starting value to a large number
    cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('sessions', 99999)")
    cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('recordings', 99999)")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def add_session(
    gender: str,
    dataset: str
):
    """
    Adds a new session to the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO sessions (
            gender, dataset
        ) VALUES (?, ?)
        """,
        (
            gender,
            dataset,
        )
    )
    
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    print(f"Session {session_id} saved to database.")
    return session_id


def add_recording(
    id_session: int,
    emotion: str,
):
    """
    Adds a new recording's metadata to the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO recordings (
            id_session, emotion
        ) VALUES (?, ?)
        """,
        (
            id_session,
            emotion,
        )
    )
    
    conn.commit()
    audio_id = cursor.lastrowid
    conn.close()
    print(f"Recording {audio_id} saved to database.")
    return audio_id