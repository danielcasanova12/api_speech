import asyncio
from sqlalchemy import text
from database import engine

async def run_migration():
    async with engine.begin() as conn:
        print("Checking datasets table for dataset_type column...")
        try:
            await conn.execute(text("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS dataset_type VARCHAR(50) DEFAULT 'speech' NOT NULL"))
            print("Successfully ensured 'dataset_type' exists in 'datasets'.")
        except Exception as e:
            print("Error adding 'dataset_type':", e)

        print("Checking recordings table for extra_info column...")
        try:
            await conn.execute(text("ALTER TABLE recordings ADD COLUMN IF NOT EXISTS extra_info JSON"))
            print("Successfully ensured 'extra_info' exists in 'recordings'.")
        except Exception as e:
            print("Error adding 'extra_info':", e)

if __name__ == "__main__":
    asyncio.run(run_migration())
