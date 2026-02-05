from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import urlparse, parse_qs, urlunparse

from config import settings

# Parse the original connection string from the .env file
original_url = urlparse(settings.NEONDB_CONNECTION_STRING)
query_params = parse_qs(original_url.query)

# Move all query parameters from the URL to the connect_args dictionary.
# This handles 'sslmode' (converted to 'ssl') and any other parameters correctly.
connect_args = {key: value[0] for key, value in query_params.items()}

# The asyncpg driver expects the key for SSL to be 'ssl', not 'sslmode'.
# We check if 'sslmode' exists, and if so, rename it to 'ssl'.
if 'sslmode' in connect_args:
    connect_args['ssl'] = connect_args.pop('sslmode')

# Rebuild the URL without any query parameters, as they have all been moved to connect_args.
# The new URL will be clean, e.g., "postgresql://user:pass@host/db"
new_url_parts = (
    original_url.scheme,
    original_url.netloc,
    original_url.path,
    original_url.params,
    '',  # This empties the query string
    original_url.fragment,
)
db_url_clean = urlunparse(new_url_parts)

# Modify the connection string scheme for the asyncpg dialect, which SQLAlchemy requires.
DATABASE_URL = db_url_clean.replace("postgresql://", "postgresql+asyncpg://")

# Create the async engine, passing the clean URL and the extracted connection arguments.
engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session