"""Create missing database tables without deleting existing data.

This is a bootstrap helper, not a replacement for versioned migrations.
"""

import asyncio

import models  # noqa: F401 - importing registers every model on Base.metadata
from database import Base, engine


async def create_missing_tables() -> None:
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_missing_tables())
