import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from database import DATABASE_URL, connect_args

async def migrate():
    print("Starting migration to add musics table...")
    try:
        engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS musics (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(255) NOT NULL,
                    genero VARCHAR(100) NOT NULL,
                    texto TEXT,
                    bpm INTEGER,
                    time_signature VARCHAR(50),
                    vocal_audio_filepath VARCHAR,
                    instrumental_audio_filepath VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            print("Successfully created 'musics' table.")

            # Alter table in case it already exists but doesn't have the new columns
            try:
                await conn.execute(text("ALTER TABLE musics ADD COLUMN bpm INTEGER;"))
                print("Added 'bpm' column.")
            except Exception as e:
                # Ignore if column already exists
                pass

            try:
                await conn.execute(text("ALTER TABLE musics ADD COLUMN time_signature VARCHAR(50);"))
                print("Added 'time_signature' column.")
            except Exception as e:
                # Ignore if column already exists
                pass

    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
