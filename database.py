from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings
from database_url import normalize_asyncpg_url

DATABASE_URL, connect_args = normalize_asyncpg_url(
    settings.NEONDB_CONNECTION_STRING
)

# Create the async engine, passing the clean URL and the extracted connection arguments.
engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
