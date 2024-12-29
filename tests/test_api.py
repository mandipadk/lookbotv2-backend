import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timedelta
import datetime as dt

from app.main import app
from app.api.dependencies.auth import get_current_user
from app.models.technical import (
    TimeFrame,
    VolumeProfile,
    OrderFlowAnalysis,
    DarkPoolAnalysis,
    OptionsFlowAnalysis,
    TrendDirection,
    SignalStrength
)

client = TestClient(app)

@pytest.fixture
def mock_auth():
    """Mock authentication for testing."""
    async def override_get_current_user():
        return {"id": "test_user_id", "email": "test@example.com"}
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides = {}

@pytest.fixture
def mock_services():
    """Mock all technical analysis services."""
    with patch('app.services.technical.technical_service') as tech_mock, \
         patch('app.services.order_flow.order_flow_service') as flow_mock, \
         patch('app.services.dark_pool.dark_pool_service') as dark_mock, \
         patch('app.services.options_flow.options_flow_service') as opt_mock:
        
        # Mock volume profile
        tech_mock.get_volume_profile.return_value = VolumeProfile(
            symbol="AAPL",
            timeframe=TimeFrame.MINUTE_1,
            timestamp=datetime.now(dt.UTC),
            price_levels=[100.0 + i for i in range(10)],
            volume_at_price={str(100.0 + i): 1000 for i in range(10)},
            value_area_high=110.0,
            value_area_low=100.0,
            point_of_control=105.0
        )
        
        # Mock order flow
        flow_mock.get_order_flow_analysis.return_value = OrderFlowAnalysis(
            symbol="AAPL",
            timeframe=TimeFrame.MINUTE_1,
            start_time=datetime.now(dt.UTC) - timedelta(hours=1),
            end_time=datetime.now(dt.UTC),
            trades=[],
            imbalances=[],
            cumulative_volume_delta=1000,
            buy_volume_ratio=0.6,
            sell_volume_ratio=0.4,
            large_trade_threshold=10000,
            block_trade_count=5,
            aggressive_buy_ratio=0.7,
            aggressive_sell_ratio=0.3
        )
        
        # Mock dark pool
        dark_mock.get_dark_pool_analysis.return_value = DarkPoolAnalysis(
            symbol="AAPL",
            timestamp=datetime.now(dt.UTC),
            timeframe=TimeFrame.MINUTE_1,
            total_volume=1000000,
            total_trades=100,
            avg_trade_size=10000,
            block_trade_count=5,
            block_volume_ratio=0.4,
            recent_trades=[],
            venues=[],
            price_levels=[],
            significant_levels=[],
            volume_distribution={}
        )
        
        # Mock options flow
        opt_mock.get_options_flow_analysis.return_value = OptionsFlowAnalysis(
            symbol="AAPL",
            timestamp=datetime.now(dt.UTC),
            underlying_price=100.0,
            total_volume=10000,
            total_open_interest=50000,
            put_call_ratio=0.7,
            implied_volatility_rank=50,
            implied_volatility_percentile=60,
            recent_flows=[],
            expiries=[],
            unusual_activity=[],
            sentiment_metrics={},
            greeks_exposure={},
            bullish_flow_ratio=0.6,
            bearish_flow_ratio=0.4,
            smart_money_indicator=0.7,
            gamma_exposure=1000000,
            vanna_exposure=500000,
            charm_exposure=100000
        )
        
        yield {
            'technical': tech_mock,
            'order_flow': flow_mock,
            'dark_pool': dark_mock,
            'options_flow': opt_mock
        }

def test_technical_endpoints(mock_auth, mock_services):
    """Test technical analysis endpoints."""
    # Test volume profile
    response = client.get(
        "/api/v1/technical/AAPL/volume-profile",
        params={"timeframe": TimeFrame.MINUTE_1.value}
    )
    assert response.status_code == 200
    data = response.json()
    assert "price_levels" in data
    assert "volume_at_price" in data
    assert "value_area_high" in data
    assert "value_area_low" in data
    assert "point_of_control" in data

    # Test order flow
    response = client.get(
        "/api/v1/technical/AAPL/order-flow",
        params={"timeframe": TimeFrame.MINUTE_1.value}
    )
    assert response.status_code == 200
    data = response.json()
    assert "trades" in data
    assert "imbalances" in data

    # Test dark pool
    response = client.get(
        "/api/v1/technical/AAPL/dark-pool",
        params={"timeframe": TimeFrame.MINUTE_1.value}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_volume" in data
    assert "block_volume_ratio" in data
    assert "venues" in data

    # Test options flow
    response = client.get(
        "/api/v1/technical/AAPL/options-flow"
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_volume" in data
    assert "put_call_ratio" in data
    assert "implied_volatility_rank" in data

def test_error_handling(mock_auth):
    """Test error handling in endpoints."""
    # Test invalid symbol
    response = client.get(
        "/api/v1/technical/INVALID/volume-profile",
        params={"timeframe": TimeFrame.MINUTE_1.value}
    )
    assert response.status_code == 404

    # Test invalid timeframe
    response = client.get(
        "/api/v1/technical/AAPL/volume-profile",
        params={"timeframe": "invalid"}
    )
    assert response.status_code == 422

def test_authentication():
    """Test authentication requirements."""
    # Test without auth
    app.dependency_overrides = {}
    response = client.get(
        "/api/v1/technical/AAPL/volume-profile",
        params={"timeframe": TimeFrame.MINUTE_1.value}
    )
    assert response.status_code == 401

    # Test with auth
    app.dependency_overrides[get_current_user] = lambda: {"id": "test_user_id"}
    response = client.get(
        "/api/v1/technical/AAPL/volume-profile",
        params={"timeframe": TimeFrame.MINUTE_1.value}
    )
    assert response.status_code == 200
