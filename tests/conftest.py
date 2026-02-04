
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app

# Use a base URL that the test client will recognize
BASE_URL = "http://test"

@pytest_asyncio.fixture(scope="session")
async def async_client():
    """
    Fixture to create an AsyncClient for the app, handling startup and shutdown events.
    Scope is 'session' so it's created only once for the entire test session.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        yield client
