import asyncio
from sqlalchemy import text
from database import engine


async def migrate():
    try:
        print("Starting migration to add musics table...")
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
            await conn.execute(
                text("ALTER TABLE musics ADD COLUMN IF NOT EXISTS bpm INTEGER")
            )
            await conn.execute(
                text(
                    "ALTER TABLE musics "
                    "ADD COLUMN IF NOT EXISTS time_signature VARCHAR(50)"
                )
            )
        print("Music table migration completed successfully.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
