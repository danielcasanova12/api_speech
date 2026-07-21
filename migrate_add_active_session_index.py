"""Add the database guard that prevents concurrent active sessions per user."""

import asyncio

from sqlalchemy import text

from database import engine


CREATE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_one_active_per_user
ON sessions (user_id)
WHERE finished_at IS NULL AND (status = 'active' OR status IS NULL)
"""


async def migrate() -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(text(CREATE_INDEX_SQL))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
