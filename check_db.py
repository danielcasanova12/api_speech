import asyncio
from database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'frases'"))
        print(result.fetchall())

asyncio.run(main())
