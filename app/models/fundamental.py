from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

class FinancialRatios(BaseModel):
    """Financial ratios for a company."""
    # Profitability Ratios
    gross_margin: float
    operating_margin: float
    net_margin: float
    roe: float  # Return on Equity
    roa: float  # Return on Assets
    roic: float  # Return on Invested Capital
    
    # Liquidity Ratios
    current_ratio: float
    quick_ratio: float
    cash_ratio: float
    
    # Solvency Ratios
    debt_to_equity: float
    debt_to_assets: float
    interest_coverage: float
    
    # Efficiency Ratios
    asset_turnover: float
    inventory_turnover: float
    receivables_turnover: float
    
    # Market Ratios
    pe_ratio: float
    pb_ratio: float  # Price to Book
    ps_ratio: float  # Price to Sales
    peg_ratio: float  # Price/Earnings to Growth
    dividend_yield: float
    
    # Growth Metrics
    revenue_growth: float
    earnings_growth: float
    dividend_growth: float

class FinancialStatement(BaseModel):
    """Financial statement data."""
    date: datetime
    revenue: float
    gross_profit: float
    operating_income: float
    net_income: float
    eps: float
    total_assets: float
    total_liabilities: float
    total_equity: float
    cash: float
    debt: float
    
    # Cash Flow Items
    operating_cash_flow: float
    investing_cash_flow: float
    financing_cash_flow: float
    free_cash_flow: float
    
    # Balance Sheet Items
    current_assets: float
    current_liabilities: float
    inventory: float
    accounts_receivable: float
    accounts_payable: float
    
    # Additional Metrics
    capex: float
    dividends_paid: float
    shares_outstanding: float

class IndustryMetrics(BaseModel):
    """Industry-wide metrics."""
    industry: str
    average_pe: float
    average_pb: float
    average_ps: float
    average_dividend_yield: float
    average_net_margin: float
    average_roe: float
    revenue_growth: float
    earnings_growth: float
    market_size: float
    competition_level: float  # 0-1 scale
    barriers_to_entry: float  # 0-1 scale
    regulatory_risk: float  # 0-1 scale

class PeerComparison(BaseModel):
    """Peer comparison data."""
    company: str
    market_cap: float
    revenue: float
    net_income: float
    pe_ratio: float
    pb_ratio: float
    ps_ratio: float
    dividend_yield: float
    roe: float
    net_margin: float
    debt_to_equity: float
    revenue_growth: float
    earnings_growth: float

class ValuationModel(BaseModel):
    """Company valuation analysis."""
    # DCF Model
    wacc: float  # Weighted Average Cost of Capital
    terminal_growth_rate: float
    projected_fcf: List[float]  # Future Free Cash Flows
    terminal_value: float
    enterprise_value: float
    equity_value: float
    fair_value_per_share: float
    
    # Comparable Company Analysis
    peer_average_pe: float
    peer_average_pb: float
    peer_average_ps: float
    implied_value_pe: float
    implied_value_pb: float
    implied_value_ps: float
    
    # Other Valuation Metrics
    ev_to_ebitda: float
    ev_to_sales: float
    graham_number: float
    margin_of_safety: float

class RiskAssessment(BaseModel):
    """Company risk assessment."""
    # Financial Risk
    credit_risk: float  # 0-1 scale
    liquidity_risk: float
    solvency_risk: float
    
    # Market Risk
    beta: float
    volatility: float
    var_95: float  # Value at Risk (95% confidence)
    
    # Business Risk
    business_risk: float
    industry_risk: float
    geographic_risk: float
    
    # Other Risks
    regulatory_risk: float
    litigation_risk: float
    esg_risk: float  # Environmental, Social, Governance

class GrowthAnalysis(BaseModel):
    """Company growth analysis."""
    # Historical Growth
    historical_revenue_growth: List[float]
    historical_earnings_growth: List[float]
    historical_fcf_growth: List[float]
    
    # Projected Growth
    projected_revenue_growth: List[float]
    projected_earnings_growth: List[float]
    projected_fcf_growth: List[float]
    
    # Growth Drivers
    market_growth: float
    market_share_growth: float
    pricing_power: float
    margin_expansion: float
    
    # Growth Sustainability
    competitive_advantage: float  # 0-1 scale
    market_opportunity: float
    execution_capability: float

class DividendAnalysis(BaseModel):
    """Dividend analysis."""
    current_dividend: float
    dividend_yield: float
    payout_ratio: float
    dividend_coverage: float
    years_of_growth: int
    cagr_5_year: float  # 5-year Compound Annual Growth Rate
    cagr_10_year: float
    sustainability_score: float  # 0-1 scale
    projected_dividends: List[float]

class FundamentalAnalysis(BaseModel):
    """Complete fundamental analysis for a company."""
    symbol: str
    timestamp: datetime
    
    # Company Overview
    market_cap: float
    enterprise_value: float
    sector: str
    industry: str
    
    # Analysis Components
    ratios: FinancialRatios
    financials: List[FinancialStatement]
    industry_metrics: IndustryMetrics
    peer_comparison: List[PeerComparison]
    valuation: ValuationModel
    risk: RiskAssessment
    growth: GrowthAnalysis
    dividends: Optional[DividendAnalysis]
    
    # Analysis Summary
    investment_rating: str  # "Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"
    target_price: float
    upside_potential: float
    risk_level: str  # "Low", "Medium", "High"
    key_strengths: List[str]
    key_risks: List[str]
    
    class Config:
        from_attributes = True
