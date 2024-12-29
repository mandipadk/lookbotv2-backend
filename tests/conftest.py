import os
import sys
from pathlib import Path
import pytest
from dotenv import load_dotenv
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to Python path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Set up environment variables
env_file = Path(__file__).parent / ".env.test"
if env_file.exists():
    load_dotenv(env_file)

os.environ.update({
    "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "test_secret_key",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_key",
    "REDIS_URL": "redis://localhost:6379/0",
    "ALPHA_VANTAGE_API_KEY": "test_alpha_vantage_key",
    "FINNHUB_API_KEY": "test_finnhub_key",
    "FMP_API_KEY": "test_fmp_key",
    "NEWS_API_KEY": "test_news_key",
    "SEC_API_KEY": "test_sec_key"
})

# Create mock functions before importing app
def mock_get_supabase_client():
    mock = MagicMock()
    mock.auth.get_user.return_value = {"id": "test_user_id", "email": "test@example.com"}
    mock.auth.sign_in.return_value = {"access_token": "test_token"}
    mock.auth.sign_up.return_value = {"user": {"id": "test_user_id"}}
    mock.table().select().execute.return_value = {"data": []}
    return mock

# Apply mocks
with patch('app.db.supabase.get_supabase_client', mock_get_supabase_client):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.redis import redis_client

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def mock_redis():
    """Mock Redis for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.get_market_data = AsyncMock(return_value=None)
    mock.cache_market_data = AsyncMock(return_value=True)
    mock.pipeline = MagicMock(return_value=mock)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.execute = AsyncMock(return_value=[1, True])
    
    redis_client._redis = mock
    return mock

@pytest.fixture
def client(mock_redis):
    """Test client fixture."""
    with TestClient(app) as test_client:
        yield test_client
