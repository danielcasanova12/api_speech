import sqlite3
from datetime import datetime
import psycopg2
from psycopg2 import Error as Psycopg2Error
from config import settings

DATABASE_FILE = "data/recordings.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_neondb_connection():
    """Establishes a connection to the NeonDB PostgreSQL database."""
    try:
        conn = psycopg2.connect(settings.NEONDB_CONNECTION_STRING)
        return conn
    except Psycopg2Error as e:
        print(f"Error connecting to NeonDB: {e}")
        return None

def init_db():
    """
    Initializes the database and creates the 'sessions' and 'recordings' tables if they don't exist.
    """
    print("Initializing SQLite database...")
    sqlite_conn = get_db_connection()
    sqlite_cursor = sqlite_conn.cursor()
    
    # Create SQLite tables
    sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            genero TEXT NOT NULL,
            dataset TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    sqlite_cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordings (
            id_audio INTEGER PRIMARY KEY AUTOINCREMENT,
            id_session INTEGER NOT NULL,
            emocao TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_session) REFERENCES sessions (id)
        )
    """)
    
    sqlite_conn.commit()
    sqlite_conn.close()
    print("SQLite database initialized successfully.")

    print("Initializing NeonDB database...")
    neondb_conn = get_neondb_connection()
    if neondb_conn:
        neondb_cursor = neondb_conn.cursor()
        # Create NeonDB tables
        neondb_cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                genero VARCHAR(255) NOT NULL,
                dataset VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        neondb_cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordings (
                id_audio SERIAL PRIMARY KEY,
                id_session INTEGER NOT NULL,
                emocao VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_session) REFERENCES sessions (id)
            )
        """)
        neondb_conn.commit()
        neondb_conn.close()
        print("NeonDB database initialized successfully.")
    else:
        print("Skipping NeonDB initialization due to connection error.")

def add_session(gender: str, dataset: str) -> int:
    """
    Adds a new session to both SQLite and NeonDB databases and returns the new session ID from SQLite.
    """
    # Save to SQLite
    sqlite_conn = get_db_connection()
    sqlite_cursor = sqlite_conn.cursor()
    
    current_timestamp = datetime.utcnow()
    sqlite_cursor.execute(
        "INSERT INTO sessions (genero, dataset, created_at) VALUES (?, ?, ?)",
        (gender, dataset, current_timestamp)
    )
    
    session_id = sqlite_cursor.lastrowid
    sqlite_conn.commit()
    sqlite_conn.close()
    print(f"Session {session_id} saved to SQLite database.")

    # Save to NeonDB
    neondb_conn = get_neondb_connection()
    if neondb_conn:
        neondb_cursor = neondb_conn.cursor()
        try:
            neondb_cursor.execute(
                "INSERT INTO sessions (id, genero, dataset, created_at) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (session_id, gender, dataset, current_timestamp)
            )
            neondb_conn.commit()
            print(f"Session {session_id} saved to NeonDB database.")
        except Psycopg2Error as e:
            neondb_conn.rollback()
            print(f"Error saving session {session_id} to NeonDB: {e}")
        finally:
            neondb_conn.close()
    else:
        print(f"Skipping NeonDB save for session {session_id} due to connection error.")

    return session_id

def add_recording(id_session: int, emotion: str) -> int:
    """
    Adds a new recording's metadata to both SQLite and NeonDB databases and returns the new audio ID from SQLite.
    """
    # Save to SQLite
    sqlite_conn = get_db_connection()
    sqlite_cursor = sqlite_conn.cursor()
    
    current_timestamp = datetime.utcnow()
    sqlite_cursor.execute(
        "INSERT INTO recordings (id_session, emocao, created_at) VALUES (?, ?, ?)",
        (id_session, emotion, current_timestamp)
    )
    
    audio_id = sqlite_cursor.lastrowid
    sqlite_conn.commit()
    sqlite_conn.close()
    print(f"Recording metadata for {audio_id} saved to SQLite database.")

    # Save to NeonDB
    neondb_conn = get_neondb_connection()
    if neondb_conn:
        neondb_cursor = neondb_conn.cursor()
        try:
            neondb_cursor.execute(
                "INSERT INTO recordings (id_audio, id_session, emocao, created_at) VALUES (%s, %s, %s, %s) ON CONFLICT (id_audio) DO NOTHING",
                (audio_id, id_session, emotion, current_timestamp)
            )
            neondb_conn.commit()
            print(f"Recording metadata for {audio_id} saved to NeonDB database.")
        except Psycopg2Error as e:
            neondb_conn.rollback()
            print(f"Error saving recording {audio_id} to NeonDB: {e}")
        finally:
            neondb_conn.close()
    else:
        print(f"Skipping NeonDB save for recording {audio_id} due to connection error.")

    return audio_id

def get_session_by_id(session_id: int):
    """
    Retrieves session details by session ID from SQLite.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, genero, dataset FROM sessions WHERE id = ?", (session_id,))
    session = cursor.fetchone()
    conn.close()
    return session

if __name__ == "__main__":
    init_db()