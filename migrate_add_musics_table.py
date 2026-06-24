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
                    vocal_audio_filepath VARCHAR,
                    instrumental_audio_filepath VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            print("Successfully created 'musics' table.")
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
