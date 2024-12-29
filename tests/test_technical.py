import pytest
import datetime as dt
from datetime import timedelta, timezone, datetime
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from app.services.technical import technical_service
from app.services.order_flow import order_flow_service
from app.services.dark_pool import dark_pool_service
from app.services.options_flow import options_flow_service
from app.services.market_data import market_data_service
from app.models.technical import (
    TimeFrame,
    VolumeProfile,
    OrderFlowTrade,
    OrderFlowImbalance,
    OrderFlowAnalysis,
    LiquidityAnalysis,
    DarkPoolAnalysis,
    OptionsFlowAnalysis,
    PatternSignal,
    TrendAnalysis,
    Signal
)

@pytest.fixture
def mock_market_data():
    with patch('app.services.market_data.market_data_service') as mock:
        # Mock historical data
        mock.get_historical_data.return_value = [
            {
                'timestamp': (datetime.now(dt.UTC) - timedelta(minutes=i)).isoformat(),
                'open': 100.0 + i,
                'high': 101.0 + i,
                'low': 99.0 + i,
                'close': 100.0 + i,
                'volume': 1000000
            }
            for i in range(100)
        ]
        
        # Mock trades data
        mock.get_trades.return_value = pd.DataFrame({
            'timestamp': [(datetime.now(dt.UTC) - timedelta(minutes=i)) for i in range(100)],
            'price': [100.0 + i for i in range(100)],
            'volume': [1000 for _ in range(100)],
            'side': ['buy' if i % 2 == 0 else 'sell' for i in range(100)],
            'is_aggressive': [True if i % 2 == 0 else False for i in range(100)]
        })
        
        # Mock order flow analysis
        mock.get_order_flow_analysis.return_value = OrderFlowAnalysis(
            symbol="AAPL",
            timeframe=TimeFrame.MINUTE_1,
            start_time=datetime.now(dt.UTC) - timedelta(hours=1),
            end_time=datetime.now(dt.UTC),
            trades=[
                OrderFlowTrade(
                    timestamp=datetime.now(dt.UTC) - timedelta(minutes=i),
                    price=100.0,
                    volume=1000,
                    side='buy' if i % 2 == 0 else 'sell',
                    is_aggressive=True if i % 2 == 0 else False,
                    is_block_trade=False,
                    metadata={}
                )
                for i in range(10)
            ],
            imbalances=[
                OrderFlowImbalance(
                    timestamp=datetime.now(dt.UTC) - timedelta(minutes=i*5),
                    start_time=datetime.now(dt.UTC) - timedelta(minutes=i*5),
                    end_time=datetime.now(dt.UTC) - timedelta(minutes=i*5-5),
                    price_level=100.0 + i,
                    buy_volume=5000,
                    sell_volume=4000,
                    net_volume=1000,
                    trade_count=50,
                    avg_trade_size=100,
                    max_trade_size=1000,
                    aggressive_buy_volume=3000,
                    aggressive_sell_volume=2000,
                    imbalance_ratio=0.2
                )
                for i in range(5)
            ],
            cumulative_volume_delta=1000,
            buy_volume_ratio=0.6,
            sell_volume_ratio=0.4,
            large_trade_threshold=10000,
            block_trade_count=5,
            aggressive_buy_ratio=0.7,
            aggressive_sell_ratio=0.3,
            smart_money_indicator=0.65,
            gamma_exposure=1000000,
            vanna_exposure=500000,
            charm_exposure=100000
        )

        # Mock dark pool analysis
        mock.get_dark_pool_analysis.return_value = DarkPoolAnalysis(
            symbol="AAPL",
            timestamp=datetime.now(dt.UTC),
            timeframe=TimeFrame.MINUTE_1,
            total_volume=1000000,
            total_trades=100,
            avg_trade_size=10000,
            block_trade_count=5,
            block_volume_ratio=0.4,
            recent_trades=[],
            venues=[
                {
                    "name": "Venue1",
                    "volume": 500000,
                    "trade_count": 50,
                    "avg_trade_size": 10000,
                    "block_trades": 3
                },
                {
                    "name": "Venue2",
                    "volume": 500000,
                    "trade_count": 50,
                    "avg_trade_size": 10000,
                    "block_trades": 2
                }
            ],
            price_levels=[],
            significant_levels=[],
            volume_distribution={},
            smart_money_indicator=0.65,
            gamma_exposure=1000000,
            vanna_exposure=500000,
            charm_exposure=100000
        )

        # Mock options flow analysis
        mock.get_options_flow_analysis.return_value = OptionsFlowAnalysis(
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
            smart_money_indicator=0.65,
            gamma_exposure=1000000,
            vanna_exposure=500000,
            charm_exposure=100000
        )
        
        yield mock

@pytest.fixture
def mock_order_flow():
    with patch('app.services.order_flow.order_flow_service') as mock:
        mock.get_order_flow_analysis.return_value = OrderFlowAnalysis(
            symbol="AAPL",
            timeframe=TimeFrame.MINUTE_1,
            start_time=datetime.now(dt.UTC) - timedelta(hours=1),
            end_time=datetime.now(dt.UTC),
            trades=[
                OrderFlowTrade(
                    timestamp=datetime.now(dt.UTC) - timedelta(minutes=i),
                    price=100.0,
                    volume=1000,
                    side='buy' if i % 2 == 0 else 'sell',
                    is_aggressive=True if i % 2 == 0 else False,
                    is_block_trade=False,
                    metadata={}
                )
                for i in range(10)
            ],
            imbalances=[
                OrderFlowImbalance(
                    timestamp=datetime.now(dt.UTC) - timedelta(minutes=i*5),
                    start_time=datetime.now(dt.UTC) - timedelta(minutes=i*5),
                    end_time=datetime.now(dt.UTC) - timedelta(minutes=i*5-5),
                    price_level=100.0 + i,
                    buy_volume=5000,
                    sell_volume=4000,
                    net_volume=1000,
                    trade_count=50,
                    avg_trade_size=100,
                    max_trade_size=1000,
                    aggressive_buy_volume=3000,
                    aggressive_sell_volume=2000,
                    imbalance_ratio=0.2
                )
                for i in range(5)
            ]
        )
        yield mock

@pytest.fixture
def mock_dark_pool():
    with patch('app.services.dark_pool.dark_pool_service') as mock:
        mock.get_dark_pool_analysis.return_value = DarkPoolAnalysis(
            symbol="AAPL",
            timestamp=datetime.now(dt.UTC),
            timeframe=TimeFrame.MINUTE_1,
            total_volume=1000000,
            total_trades=100,
            avg_trade_size=10000,
            block_trade_count=5,
            block_volume_ratio=0.4,
            recent_trades=[],
            venues=[
                {
                    "name": "Venue1",
                    "volume": 500000,
                    "trade_count": 50,
                    "avg_trade_size": 10000,
                    "block_trades": 3
                },
                {
                    "name": "Venue2",
                    "volume": 500000,
                    "trade_count": 50,
                    "avg_trade_size": 10000,
                    "block_trades": 2
                }
            ],
            price_levels=[],
            significant_levels=[],
            volume_distribution={},
            smart_money_indicator=0.65,
            gamma_exposure=1000000,
            vanna_exposure=500000,
            charm_exposure=100000
        )
        yield mock

@pytest.fixture
def mock_options_flow():
    with patch('app.services.options_flow.options_flow_service') as mock:
        mock.get_options_flow_analysis.return_value = OptionsFlowAnalysis(
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
            greeks_exposure={}
        )
        yield mock

@pytest.mark.asyncio
async def test_volume_profile_analysis(mock_market_data):
    """Test volume profile analysis."""
    symbol = "AAPL"
    timeframe = TimeFrame.MINUTE_1
    
    analysis = await technical_service.get_volume_profile(
        symbol=symbol,
        timeframe=timeframe
    )
    
    assert isinstance(analysis, VolumeProfile)
    assert analysis.symbol == symbol
    assert len(analysis.price_levels) > 0
    assert analysis.volume_at_price is not None
    assert analysis.value_area_high > analysis.value_area_low
    assert analysis.point_of_control is not None

@pytest.mark.asyncio
async def test_order_flow_analysis(mock_market_data, mock_order_flow):
    """Test order flow analysis."""
    symbol = "AAPL"
    timeframe = TimeFrame.MINUTE_1
    
    analysis = await order_flow_service.get_order_flow_analysis(
        symbol=symbol,
        timeframe=timeframe,
        start_time=datetime.now(dt.UTC) - timedelta(hours=1),
        end_time=datetime.now(dt.UTC)
    )
    
    assert isinstance(analysis, OrderFlowAnalysis)
    assert analysis.symbol == symbol
    assert len(analysis.trades) > 0
    assert len(analysis.imbalances) > 0

@pytest.mark.asyncio
async def test_dark_pool_analysis(mock_market_data, mock_dark_pool):
    """Test dark pool analysis."""
    symbol = "AAPL"
    timeframe = TimeFrame.MINUTE_1
    
    analysis = await dark_pool_service.get_dark_pool_analysis(
        symbol=symbol,
        timeframe=timeframe,
        lookback_minutes=60
    )
    
    assert isinstance(analysis, DarkPoolAnalysis)
    assert analysis.symbol == symbol
    assert analysis.total_volume > 0
    assert analysis.block_volume_ratio >= 0
    assert analysis.block_volume_ratio <= 1

@pytest.mark.asyncio
async def test_options_flow_analysis(mock_market_data, mock_options_flow):
    """Test options flow analysis."""
    symbol = "AAPL"
    
    analysis = await options_flow_service.get_options_flow_analysis(
        symbol=symbol,
        lookback_minutes=60
    )
    
    assert isinstance(analysis, OptionsFlowAnalysis)
    assert analysis.symbol == symbol
    assert analysis.total_volume > 0
    assert analysis.put_call_ratio >= 0
    assert 0 <= analysis.implied_volatility_rank <= 100
    assert 0 <= analysis.implied_volatility_percentile <= 100

@pytest.mark.asyncio
async def test_technical_indicators(mock_market_data):
    """Test technical indicators calculation."""
    symbol = "AAPL"
    timeframe = TimeFrame.MINUTE_1
    
    indicators = await technical_service.get_technical_indicators(
        symbol=symbol,
        timeframe=timeframe
    )
    
    assert "moving_averages" in indicators
    assert "momentum_indicators" in indicators
    assert "volatility_indicators" in indicators
    assert "volume_indicators" in indicators

@pytest.mark.asyncio
async def test_trend_analysis(mock_market_data):
    """Test trend analysis."""
    symbol = "AAPL"
    timeframe = TimeFrame.MINUTE_1
    
    analysis = await technical_service.analyze_trend(
        symbol=symbol,
        timeframe=timeframe
    )
    
    assert isinstance(analysis, TrendAnalysis)
    assert analysis.symbol == symbol
    assert analysis.direction is not None
    assert analysis.strength is not None
    assert len(analysis.support_levels) > 0
    assert len(analysis.resistance_levels) > 0

@pytest.mark.asyncio
async def test_signal_generation(mock_market_data):
    """Test trading signal generation."""
    symbol = "AAPL"
    timeframe = TimeFrame.MINUTE_1
    
    signals = await technical_service.generate_signals(
        symbol=symbol,
        timeframe=timeframe
    )
    
    assert isinstance(signals, list)
    for signal in signals:
        assert isinstance(signal, dict)
        assert "type" in signal
        assert "confidence" in signal
        assert 0 <= signal["confidence"] <= 1
