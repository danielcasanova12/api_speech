
import sqlite3
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
    cursor.execute("DROP TABLE IF EXISTS sessions")
    # Drop the old sections table if it exists
    cursor.execute("DROP TABLE IF EXISTS sections")

    # Create tables with the new schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            genero TEXT NOT NULL,
            dataset TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id_audio INTEGER PRIMARY KEY AUTOINCREMENT,
            id_session INTEGER NOT NULL,
            emocao TEXT,
            FOREIGN KEY (id_session) REFERENCES sessions (id)
        )
    """)
    
    # Set autoincrement starting value to a large number
    cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('sessions', 99999)")
    cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('recordings', 99999)")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def add_session(gender: str, dataset: str) -> int:
    """
    Adds a new session to the database and returns the new session ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO sessions (genero, dataset) VALUES (?, ?)",
        (gender, dataset)
    )
    
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"Session {session_id} saved to database.")
    return session_id

def add_recording(id_session: int, emotion: str) -> int:
    """
    Adds a new recording's metadata to the database and returns the new audio ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO recordings (id_session, emocao) VALUES (?, ?)",
        (id_session, emotion)
    )
    
    audio_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"Recording metadata for {audio_id} saved to database.")
    return audio_id

def get_session_by_id(session_id: int):
    """
    Retrieves session details by session ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, genero, dataset FROM sessions WHERE id = ?", (session_id,))
    session = cursor.fetchone()
    conn.close()
    return session
