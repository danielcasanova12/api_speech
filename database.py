
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from urllib.parse import urlparse, parse_qs, urlunparse

from config import settings

# Parse the original connection string
original_url = urlparse(settings.NEONDB_CONNECTION_STRING)
query_params = parse_qs(original_url.query)

# Extract sslmode for connect_args and remove it from the query params
connect_args = {}
if 'sslmode' in query_params:
    connect_args['ssl'] = query_params['sslmode'][0]
    del query_params['sslmode']

# Rebuild the URL without sslmode in the query string
# urlunparse expects a 6-tuple; we need to create one from the parsed URL
# We also need to re-encode the query parameters
from urllib.parse import urlencode
new_query = urlencode(query_params, doseq=True)
new_url_parts = (
    original_url.scheme,
    original_url.netloc,
    original_url.path,
    original_url.params,
    new_query,
    original_url.fragment,
)
db_url_without_sslmode = urlunparse(new_url_parts)


# Modify the connection string for the asyncpg dialect
DATABASE_URL = db_url_without_sslmode.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
