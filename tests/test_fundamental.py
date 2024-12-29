import pytest
from datetime import timedelta
from datetime import datetime
import datetime as dt
import numpy as np
from unittest.mock import Mock, patch

from app.services.fundamental import fundamental_service
from app.services.market_data import market_data_service
from app.models.fundamental import (
    FinancialRatios,
    FinancialStatement,
    IndustryMetrics,
    PeerComparison,
    ValuationModel,
    RiskAssessment,
    GrowthAnalysis,
    DividendAnalysis,
    FundamentalAnalysis
)

@pytest.fixture
def mock_market_data():
    with patch('app.services.market_data.market_data_service') as mock:
        # Mock historical data
        mock.get_historical_data.return_value = [
            {
                'timestamp': (datetime.now(dt.UTC) - timedelta(days=i)).isoformat(),
                'open': 100.0 * (1.01 ** i),
                'high': 101.0 * (1.01 ** i),
                'low': 99.0 * (1.01 ** i),
                'close': 100.0 * (1.01 ** i),
                'volume': 1000000
            }
            for i in range(252)  # One year of data
        ]
        
        # Mock real-time quote
        mock.get_real_time_quote.return_value = {
            'symbol': 'AAPL',
            'price': 150.0,
            'change': 1.5,
            'percent_change': 1.0,
            'volume': 1000000,
            'timestamp': datetime.now(dt.UTC).isoformat()
        }
        
        yield mock

@pytest.fixture
def mock_fundamental():
    with patch('app.services.fundamental.fundamental_service') as mock:
        # Mock financial ratios
        mock.get_financial_ratios.return_value = FinancialRatios(
            symbol='AAPL',
            timestamp=datetime.now(dt.UTC),
            pe_ratio=25.0,
            pb_ratio=5.0,
            ps_ratio=10.0,
            peg_ratio=1.5,
            ev_ebitda=15.0,
            current_ratio=2.0,
            quick_ratio=1.5,
            debt_equity=0.5,
            gross_margin=0.4,
            operating_margin=0.3,
            net_margin=0.2,
            roe=0.25,
            roa=0.15,
            roic=0.20,
            cash_ratio=1.0,
            debt_to_equity=0.5,
            debt_to_assets=0.3,
            interest_coverage=10.0,
            asset_turnover=0.8,
            inventory_turnover=12.0,
            receivables_turnover=8.0,
            dividend_yield=0.015,
            revenue_growth=0.15,
            earnings_growth=0.20,
            dividend_growth=0.10
        )
        
        # Mock industry metrics
        mock.get_industry_metrics.return_value = IndustryMetrics(
            sector='Technology',
            industry='Software',
            market_size=1000000000000,
            growth_rate=0.15,
            avg_margin=0.25,
            average_pe=25.0,
            average_pb=5.0,
            average_ps=10.0,
            average_dividend_yield=0.02,
            average_net_margin=0.20,
            average_roe=0.25,
            revenue_growth=0.15,
            earnings_growth=0.20,
            competition_level=0.7,
            barriers_to_entry=0.8,
            regulatory_risk=0.3
        )
        
        # Mock peer comparison
        mock.get_peer_comparison.return_value = PeerComparison(
            symbol='AAPL',
            company='Apple Inc.',
            peers=['MSFT', 'GOOGL', 'META', 'AMZN'],
            market_cap=2e12,
            revenue=365.8e9,
            net_income=94.3e9,
            pe_ratio=25.0,
            pb_ratio=5.0,
            ps_ratio=10.0,
            dividend_yield=0.015,
            roe=0.25,
            net_margin=0.20,
            debt_to_equity=0.5,
            revenue_growth=0.15,
            earnings_growth=0.20,
            metrics={
                'market_cap': [2e12, 1.8e12, 1.5e12, 1.2e12, 1e12],
                'pe_ratio': [25.0, 24.0, 23.0, 22.0, 21.0],
                'revenue_growth': [0.15, 0.14, 0.13, 0.12, 0.11],
                'net_margin': [0.25, 0.24, 0.23, 0.22, 0.21]
            },
            rank={
                'market_cap': 1,
                'pe_ratio': 2,
                'revenue_growth': 1,
                'net_margin': 1
            }
        )

        # Mock valuation model
        mock.get_valuation_model.return_value = ValuationModel(
            symbol='AAPL',
            timestamp=datetime.now(dt.UTC),
            fair_value=150.0,
            upside_potential=0.15,
            confidence_level=0.8,
            methods=['DCF', 'Multiples'],
            assumptions={
                'growth_rate': 0.15,
                'discount_rate': 0.10,
                'terminal_multiple': 15
            },
            wacc=0.10,
            terminal_growth_rate=0.03,
            projected_fcf=[1000000000, 1150000000, 1322500000, 1520875000, 1749006250],
            terminal_value=35000000000,
            enterprise_value=40000000000,
            equity_value=38000000000,
            fair_value_per_share=150.0,
            peer_average_pe=25.0,
            peer_average_pb=5.0,
            peer_average_ps=10.0,
            implied_value_pe=160.0,
            implied_value_pb=145.0,
            implied_value_ps=155.0,
            ev_to_ebitda=15.0,
            ev_to_sales=5.0,
            graham_number=140.0,
            margin_of_safety=0.2
        )

        # Mock risk assessment
        mock.get_risk_assessment.return_value = RiskAssessment(
            symbol='AAPL',
            timestamp=datetime.now(dt.UTC),
            beta=1.2,
            volatility=0.25,
            var_95=0.02,
            sharpe_ratio=1.5,
            risk_factors=['Market Risk', 'Industry Risk'],
            risk_scores={
                'market': 0.7,
                'credit': 0.3,
                'operational': 0.2
            }
        )

        # Mock growth analysis
        mock.get_growth_analysis.return_value = GrowthAnalysis(
            symbol='AAPL',
            timestamp=datetime.now(dt.UTC),
            revenue_growth=0.15,
            earnings_growth=0.20,
            growth_stability=0.8,
            growth_quality=0.85,
            growth_drivers=['Product Innovation', 'Market Expansion'],
            growth_risks=['Competition', 'Regulation']
        )

        # Mock dividend analysis
        mock.get_dividend_analysis.return_value = DividendAnalysis(
            symbol='AAPL',
            timestamp=datetime.now(dt.UTC),
            dividend_yield=0.015,
            payout_ratio=0.28,
            dividend_growth_rate=0.10,
            dividend_safety=0.9,
            years_of_growth=10,
            dividend_history=[0.82, 0.88, 0.94, 1.0],
            next_dividend_date=datetime.now(dt.UTC) + timedelta(days=30),
            dividend_frequency='Quarterly'
        )
        
        yield mock

@pytest.mark.asyncio
async def test_financial_ratios(mock_market_data, mock_fundamental):
    """Test financial ratio calculations."""
    symbol = "AAPL"
    
    ratios = await fundamental_service.get_financial_ratios(symbol)
    
    assert isinstance(ratios, FinancialRatios)
    assert ratios.symbol == symbol
    assert ratios.pe_ratio > 0
    assert ratios.pb_ratio > 0
    assert ratios.current_ratio > 0
    assert ratios.debt_equity >= 0

@pytest.mark.asyncio
async def test_industry_analysis(mock_market_data, mock_fundamental):
    """Test industry analysis."""
    symbol = "AAPL"
    
    metrics = await fundamental_service.get_industry_metrics(symbol)
    
    assert isinstance(metrics, IndustryMetrics)
    assert metrics.sector == "Technology"
    assert metrics.market_size > 0
    assert 0 <= metrics.competition_level <= 1
    assert 0 <= metrics.regulatory_risk <= 1

@pytest.mark.asyncio
async def test_peer_comparison(mock_market_data, mock_fundamental):
    """Test peer comparison."""
    symbol = "AAPL"
    
    comparison = await fundamental_service.get_peer_comparison(symbol)
    
    assert isinstance(comparison, PeerComparison)
    assert comparison.symbol == symbol
    assert len(comparison.peers) > 0
    assert all(metric in comparison.metrics for metric in ['market_cap', 'pe_ratio'])
    assert all(metric in comparison.rank for metric in ['market_cap', 'pe_ratio'])

@pytest.mark.asyncio
async def test_valuation(mock_market_data, mock_fundamental):
    """Test valuation models."""
    symbol = "AAPL"
    
    valuation = await fundamental_service.get_valuation_model(symbol)
    
    assert isinstance(valuation, ValuationModel)
    assert valuation.symbol == symbol
    assert valuation.fair_value > 0
    assert valuation.upside_potential is not None

@pytest.mark.asyncio
async def test_risk_assessment(mock_market_data, mock_fundamental):
    """Test risk assessment."""
    symbol = "AAPL"
    
    risk = await fundamental_service.get_risk_assessment(symbol)
    
    assert isinstance(risk, RiskAssessment)
    assert risk.symbol == symbol
    assert 0 <= risk.beta <= 5
    assert 0 <= risk.volatility <= 1

@pytest.mark.asyncio
async def test_growth_analysis(mock_market_data, mock_fundamental):
    """Test growth analysis."""
    symbol = "AAPL"
    
    growth = await fundamental_service.get_growth_analysis(symbol)
    
    assert isinstance(growth, GrowthAnalysis)
    assert growth.symbol == symbol
    assert growth.revenue_growth is not None
    assert growth.earnings_growth is not None

@pytest.mark.asyncio
async def test_dividend_analysis(mock_market_data, mock_fundamental):
    """Test dividend analysis."""
    symbol = "AAPL"
    
    dividend = await fundamental_service.get_dividend_analysis(symbol)
    
    assert isinstance(dividend, DividendAnalysis)
    assert dividend.symbol == symbol
    assert dividend.dividend_yield >= 0
    assert dividend.payout_ratio >= 0
