import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from scipy.stats import norm

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
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class FundamentalService:
    def __init__(self):
        self.market_data = market_data_service
        self.CACHE_TTL = 3600  # 1 hour
        self.PEER_COUNT = 5
        self.HISTORICAL_YEARS = 5
        self.PROJECTION_YEARS = 5
        self.RISK_FREE_RATE = 0.04  # 4% treasury yield

    async def get_fundamental_analysis(
        self,
        symbol: str
    ) -> FundamentalAnalysis:
        """Get complete fundamental analysis for a company."""
        try:
            # Try to get from cache
            cache_key = f"fundamental:{symbol}"
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                return FundamentalAnalysis(**cached_data)

            # Get company overview
            overview = await self.market_data.get_company_overview(symbol)
            
            # Get financial statements
            financials = await self._get_financial_statements(symbol)
            
            # Calculate financial ratios
            ratios = await self._calculate_ratios(financials)
            
            # Get industry metrics
            industry = await self._get_industry_metrics(
                overview['sector'],
                overview['industry']
            )
            
            # Get peer comparison
            peers = await self._get_peer_comparison(
                symbol,
                overview['sector'],
                overview['industry']
            )
            
            # Calculate valuation
            valuation = await self._calculate_valuation(
                symbol,
                financials,
                peers,
                industry
            )
            
            # Assess risks
            risk = await self._assess_risks(
                symbol,
                financials,
                industry
            )
            
            # Analyze growth
            growth = await self._analyze_growth(
                symbol,
                financials,
                industry
            )
            
            # Analyze dividends if applicable
            dividends = None
            if overview.get('dividend_yield'):
                dividends = await self._analyze_dividends(
                    symbol,
                    financials
                )
            
            # Generate investment rating and summary
            rating, target, upside = self._generate_rating(
                symbol,
                valuation,
                risk,
                growth
            )
            
            strengths, risks = self._identify_key_points(
                ratios,
                valuation,
                risk,
                growth,
                industry
            )
            
            # Create analysis
            analysis = FundamentalAnalysis(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                market_cap=float(overview['market_cap']),
                enterprise_value=float(valuation.enterprise_value),
                sector=overview['sector'],
                industry=overview['industry'],
                ratios=ratios,
                financials=financials,
                industry_metrics=industry,
                peer_comparison=peers,
                valuation=valuation,
                risk=risk,
                growth=growth,
                dividends=dividends,
                investment_rating=rating,
                target_price=float(target),
                upside_potential=float(upside),
                risk_level=self._get_risk_level(risk),
                key_strengths=strengths,
                key_risks=risks
            )
            
            # Cache for 1 hour
            await redis_client.set_json(
                cache_key,
                analysis.dict(),
                self.CACHE_TTL
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                f"Error analyzing fundamentals for {symbol}: {str(e)}"
            )
            raise

    async def _get_financial_statements(
        self,
        symbol: str
    ) -> List[FinancialStatement]:
        """Get historical financial statements."""
        try:
            statements = []
            
            # Get last N years of financial data
            financials = await self.market_data.get_financial_statements(
                symbol,
                years=self.HISTORICAL_YEARS
            )
            
            for data in financials:
                statement = FinancialStatement(
                    date=data['date'],
                    revenue=float(data['revenue']),
                    gross_profit=float(data['gross_profit']),
                    operating_income=float(data['operating_income']),
                    net_income=float(data['net_income']),
                    eps=float(data['eps']),
                    total_assets=float(data['total_assets']),
                    total_liabilities=float(data['total_liabilities']),
                    total_equity=float(data['total_equity']),
                    cash=float(data['cash']),
                    debt=float(data['debt']),
                    operating_cash_flow=float(data['operating_cash_flow']),
                    investing_cash_flow=float(data['investing_cash_flow']),
                    financing_cash_flow=float(data['financing_cash_flow']),
                    free_cash_flow=float(data['free_cash_flow']),
                    current_assets=float(data['current_assets']),
                    current_liabilities=float(data['current_liabilities']),
                    inventory=float(data['inventory']),
                    accounts_receivable=float(data['accounts_receivable']),
                    accounts_payable=float(data['accounts_payable']),
                    capex=float(data['capex']),
                    dividends_paid=float(data.get('dividends_paid', 0)),
                    shares_outstanding=float(data['shares_outstanding'])
                )
                statements.append(statement)
            
            return sorted(statements, key=lambda x: x.date)
            
        except Exception as e:
            logger.error(f"Error getting financial statements: {str(e)}")
            raise

    async def _calculate_ratios(
        self,
        financials: List[FinancialStatement]
    ) -> FinancialRatios:
        """Calculate financial ratios from statements."""
        try:
            # Use latest financial statement
            latest = financials[-1]
            
            # Calculate profitability ratios
            gross_margin = (
                latest.gross_profit / latest.revenue
                if latest.revenue > 0 else 0
            )
            operating_margin = (
                latest.operating_income / latest.revenue
                if latest.revenue > 0 else 0
            )
            net_margin = (
                latest.net_income / latest.revenue
                if latest.revenue > 0 else 0
            )
            roe = (
                latest.net_income / latest.total_equity
                if latest.total_equity > 0 else 0
            )
            roa = (
                latest.net_income / latest.total_assets
                if latest.total_assets > 0 else 0
            )
            invested_capital = (
                latest.total_equity + latest.debt - latest.cash
            )
            roic = (
                latest.operating_income * (1 - 0.21) / invested_capital
                if invested_capital > 0 else 0
            )
            
            # Calculate liquidity ratios
            current_ratio = (
                latest.current_assets / latest.current_liabilities
                if latest.current_liabilities > 0 else 0
            )
            quick_ratio = (
                (latest.current_assets - latest.inventory) /
                latest.current_liabilities
                if latest.current_liabilities > 0 else 0
            )
            cash_ratio = (
                latest.cash / latest.current_liabilities
                if latest.current_liabilities > 0 else 0
            )
            
            # Calculate solvency ratios
            debt_to_equity = (
                latest.debt / latest.total_equity
                if latest.total_equity > 0 else 0
            )
            debt_to_assets = (
                latest.debt / latest.total_assets
                if latest.total_assets > 0 else 0
            )
            interest_coverage = (
                latest.operating_income /
                abs(latest.financing_cash_flow)
                if abs(latest.financing_cash_flow) > 0 else 0
            )
            
            # Calculate efficiency ratios
            asset_turnover = (
                latest.revenue / latest.total_assets
                if latest.total_assets > 0 else 0
            )
            inventory_turnover = (
                latest.revenue / latest.inventory
                if latest.inventory > 0 else 0
            )
            receivables_turnover = (
                latest.revenue / latest.accounts_receivable
                if latest.accounts_receivable > 0 else 0
            )
            
            # Get market ratios from market data
            market_ratios = await self.market_data.get_market_ratios(
                latest.symbol
            )
            
            # Calculate growth metrics
            if len(financials) > 1:
                prev = financials[-2]
                revenue_growth = (
                    (latest.revenue - prev.revenue) / prev.revenue
                    if prev.revenue > 0 else 0
                )
                earnings_growth = (
                    (latest.net_income - prev.net_income) / abs(prev.net_income)
                    if prev.net_income != 0 else 0
                )
                dividend_growth = (
                    (latest.dividends_paid - prev.dividends_paid) /
                    prev.dividends_paid
                    if prev.dividends_paid > 0 else 0
                )
            else:
                revenue_growth = 0
                earnings_growth = 0
                dividend_growth = 0
            
            return FinancialRatios(
                gross_margin=float(gross_margin),
                operating_margin=float(operating_margin),
                net_margin=float(net_margin),
                roe=float(roe),
                roa=float(roa),
                roic=float(roic),
                current_ratio=float(current_ratio),
                quick_ratio=float(quick_ratio),
                cash_ratio=float(cash_ratio),
                debt_to_equity=float(debt_to_equity),
                debt_to_assets=float(debt_to_assets),
                interest_coverage=float(interest_coverage),
                asset_turnover=float(asset_turnover),
                inventory_turnover=float(inventory_turnover),
                receivables_turnover=float(receivables_turnover),
                pe_ratio=float(market_ratios['pe']),
                pb_ratio=float(market_ratios['pb']),
                ps_ratio=float(market_ratios['ps']),
                peg_ratio=float(market_ratios['peg']),
                dividend_yield=float(market_ratios['dividend_yield']),
                revenue_growth=float(revenue_growth),
                earnings_growth=float(earnings_growth),
                dividend_growth=float(dividend_growth)
            )
            
        except Exception as e:
            logger.error(f"Error calculating ratios: {str(e)}")
            raise

# Create singleton instance
fundamental_service = FundamentalService()
