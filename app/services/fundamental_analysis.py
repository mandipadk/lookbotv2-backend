import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from scipy.stats import norm

from app.services.market_data import market_data_service
from app.models.fundamental import (
    IndustryMetrics,
    PeerComparison,
    ValuationModel,
    RiskAssessment,
    GrowthAnalysis,
    DividendAnalysis
)

logger = logging.getLogger(__name__)

class FundamentalAnalysisService:
    """Additional fundamental analysis methods."""
    
    async def _get_industry_metrics(
        self,
        sector: str,
        industry: str
    ) -> IndustryMetrics:
        """Get industry metrics and analysis."""
        try:
            metrics = await self.market_data.get_industry_metrics(industry)
            
            return IndustryMetrics(
                industry=industry,
                average_pe=float(metrics['avg_pe']),
                average_pb=float(metrics['avg_pb']),
                average_ps=float(metrics['avg_ps']),
                average_dividend_yield=float(metrics['avg_dividend_yield']),
                average_net_margin=float(metrics['avg_net_margin']),
                average_roe=float(metrics['avg_roe']),
                revenue_growth=float(metrics['revenue_growth']),
                earnings_growth=float(metrics['earnings_growth']),
                market_size=float(metrics['market_size']),
                competition_level=float(metrics['competition_level']),
                barriers_to_entry=float(metrics['barriers_to_entry']),
                regulatory_risk=float(metrics['regulatory_risk'])
            )
            
        except Exception as e:
            logger.error(f"Error getting industry metrics: {str(e)}")
            raise

    async def _get_peer_comparison(
        self,
        symbol: str,
        sector: str,
        industry: str
    ) -> List[PeerComparison]:
        """Get peer comparison data."""
        try:
            peers = await self.market_data.get_peers(
                symbol,
                sector,
                industry,
                limit=self.PEER_COUNT
            )
            
            comparisons = []
            for peer in peers:
                comparison = PeerComparison(
                    company=peer['symbol'],
                    market_cap=float(peer['market_cap']),
                    revenue=float(peer['revenue']),
                    net_income=float(peer['net_income']),
                    pe_ratio=float(peer['pe_ratio']),
                    pb_ratio=float(peer['pb_ratio']),
                    ps_ratio=float(peer['ps_ratio']),
                    dividend_yield=float(peer['dividend_yield']),
                    roe=float(peer['roe']),
                    net_margin=float(peer['net_margin']),
                    debt_to_equity=float(peer['debt_to_equity']),
                    revenue_growth=float(peer['revenue_growth']),
                    earnings_growth=float(peer['earnings_growth'])
                )
                comparisons.append(comparison)
            
            return comparisons
            
        except Exception as e:
            logger.error(f"Error getting peer comparison: {str(e)}")
            raise

    async def _calculate_valuation(
        self,
        symbol: str,
        financials: List[FinancialStatement],
        peers: List[PeerComparison],
        industry: IndustryMetrics
    ) -> ValuationModel:
        """Calculate company valuation using multiple methods."""
        try:
            # Calculate WACC
            wacc = await self._calculate_wacc(symbol, financials[-1])
            
            # Project future cash flows
            fcf_projections = self._project_cash_flows(
                financials,
                industry
            )
            
            # Calculate terminal value
            terminal_growth = min(
                industry.revenue_growth,
                0.04  # Cap at risk-free rate
            )
            terminal_value = (
                fcf_projections[-1] * (1 + terminal_growth) /
                (wacc - terminal_growth)
            )
            
            # Calculate enterprise and equity value
            present_values = [
                fcf / (1 + wacc) ** (i + 1)
                for i, fcf in enumerate(fcf_projections)
            ]
            terminal_present_value = (
                terminal_value /
                (1 + wacc) ** len(fcf_projections)
            )
            
            enterprise_value = (
                sum(present_values) + terminal_present_value
            )
            equity_value = (
                enterprise_value +
                financials[-1].cash -
                financials[-1].debt
            )
            
            # Calculate fair value per share
            fair_value = (
                equity_value / financials[-1].shares_outstanding
            )
            
            # Calculate comparable metrics
            peer_metrics = {
                'pe': np.mean([p.pe_ratio for p in peers]),
                'pb': np.mean([p.pb_ratio for p in peers]),
                'ps': np.mean([p.ps_ratio for p in peers])
            }
            
            implied_values = {
                'pe': (
                    peer_metrics['pe'] * financials[-1].eps
                ),
                'pb': (
                    peer_metrics['pb'] *
                    (financials[-1].total_equity /
                     financials[-1].shares_outstanding)
                ),
                'ps': (
                    peer_metrics['ps'] *
                    (financials[-1].revenue /
                     financials[-1].shares_outstanding)
                )
            }
            
            # Calculate other valuation metrics
            ev_to_ebitda = (
                enterprise_value /
                (financials[-1].operating_income +
                 financials[-1].capex)  # Approximate EBITDA
            )
            
            ev_to_sales = enterprise_value / financials[-1].revenue
            
            # Calculate Graham number
            graham = np.sqrt(
                22.5 * financials[-1].eps *
                (financials[-1].total_equity /
                 financials[-1].shares_outstanding)
            )
            
            # Calculate margin of safety
            current_price = await self.market_data.get_last_price(symbol)
            margin_of_safety = (fair_value - current_price) / fair_value
            
            return ValuationModel(
                wacc=float(wacc),
                terminal_growth_rate=float(terminal_growth),
                projected_fcf=[float(f) for f in fcf_projections],
                terminal_value=float(terminal_value),
                enterprise_value=float(enterprise_value),
                equity_value=float(equity_value),
                fair_value_per_share=float(fair_value),
                peer_average_pe=float(peer_metrics['pe']),
                peer_average_pb=float(peer_metrics['pb']),
                peer_average_ps=float(peer_metrics['ps']),
                implied_value_pe=float(implied_values['pe']),
                implied_value_pb=float(implied_values['pb']),
                implied_value_ps=float(implied_values['ps']),
                ev_to_ebitda=float(ev_to_ebitda),
                ev_to_sales=float(ev_to_sales),
                graham_number=float(graham),
                margin_of_safety=float(margin_of_safety)
            )
            
        except Exception as e:
            logger.error(f"Error calculating valuation: {str(e)}")
            raise

    async def _assess_risks(
        self,
        symbol: str,
        financials: List[FinancialStatement],
        industry: IndustryMetrics
    ) -> RiskAssessment:
        """Assess company risks."""
        try:
            latest = financials[-1]
            
            # Calculate financial risks
            credit_risk = self._calculate_credit_risk(latest)
            liquidity_risk = self._calculate_liquidity_risk(latest)
            solvency_risk = self._calculate_solvency_risk(latest)
            
            # Get market risks
            market_risks = await self.market_data.get_market_risks(symbol)
            
            # Calculate business risks
            business_risk = self._calculate_business_risk(
                financials,
                industry
            )
            
            return RiskAssessment(
                credit_risk=float(credit_risk),
                liquidity_risk=float(liquidity_risk),
                solvency_risk=float(solvency_risk),
                beta=float(market_risks['beta']),
                volatility=float(market_risks['volatility']),
                var_95=float(market_risks['var_95']),
                business_risk=float(business_risk),
                industry_risk=float(industry.regulatory_risk),
                geographic_risk=float(market_risks['geographic_risk']),
                regulatory_risk=float(industry.regulatory_risk),
                litigation_risk=float(market_risks['litigation_risk']),
                esg_risk=float(market_risks['esg_risk'])
            )
            
        except Exception as e:
            logger.error(f"Error assessing risks: {str(e)}")
            raise

    async def _analyze_growth(
        self,
        symbol: str,
        financials: List[FinancialStatement],
        industry: IndustryMetrics
    ) -> GrowthAnalysis:
        """Analyze company growth."""
        try:
            # Calculate historical growth rates
            historical = self._calculate_historical_growth(financials)
            
            # Project future growth
            projected = self._project_growth_rates(
                financials,
                industry
            )
            
            # Get growth drivers
            drivers = await self.market_data.get_growth_drivers(
                symbol,
                industry.industry
            )
            
            return GrowthAnalysis(
                historical_revenue_growth=historical['revenue'],
                historical_earnings_growth=historical['earnings'],
                historical_fcf_growth=historical['fcf'],
                projected_revenue_growth=projected['revenue'],
                projected_earnings_growth=projected['earnings'],
                projected_fcf_growth=projected['fcf'],
                market_growth=float(industry.revenue_growth),
                market_share_growth=float(drivers['market_share']),
                pricing_power=float(drivers['pricing_power']),
                margin_expansion=float(drivers['margin_expansion']),
                competitive_advantage=float(drivers['competitive_advantage']),
                market_opportunity=float(drivers['market_opportunity']),
                execution_capability=float(drivers['execution'])
            )
            
        except Exception as e:
            logger.error(f"Error analyzing growth: {str(e)}")
            raise

    async def _analyze_dividends(
        self,
        symbol: str,
        financials: List[FinancialStatement]
    ) -> DividendAnalysis:
        """Analyze dividend payments and sustainability."""
        try:
            latest = financials[-1]
            
            # Get dividend history
            history = await self.market_data.get_dividend_history(
                symbol,
                years=10
            )
            
            # Calculate metrics
            current = history[-1]['dividend']
            yield_val = current / await self.market_data.get_last_price(symbol)
            payout = current * latest.shares_outstanding / latest.net_income
            coverage = 1 / payout if payout > 0 else 0
            
            # Calculate growth rates
            cagr_5 = self._calculate_dividend_cagr(history, 5)
            cagr_10 = self._calculate_dividend_cagr(history, 10)
            
            # Project future dividends
            projections = self._project_dividends(
                history,
                latest,
                cagr_5
            )
            
            # Calculate sustainability score
            sustainability = self._calculate_dividend_sustainability(
                latest,
                payout,
                coverage,
                cagr_5
            )
            
            return DividendAnalysis(
                current_dividend=float(current),
                dividend_yield=float(yield_val),
                payout_ratio=float(payout),
                dividend_coverage=float(coverage),
                years_of_growth=len(history),
                cagr_5_year=float(cagr_5),
                cagr_10_year=float(cagr_10),
                sustainability_score=float(sustainability),
                projected_dividends=[float(d) for d in projections]
            )
            
        except Exception as e:
            logger.error(f"Error analyzing dividends: {str(e)}")
            raise

    async def _generate_rating(
        self,
        symbol: str,
        valuation: ValuationModel,
        risk: RiskAssessment,
        growth: GrowthAnalysis
    ) -> Tuple[str, float, float]:
        """Generate investment rating and target price."""
        try:
            # Weight different valuation methods
            target_price = np.average([
                valuation.fair_value_per_share,
                valuation.implied_value_pe,
                valuation.implied_value_pb,
                valuation.graham_number
            ], weights=[0.4, 0.2, 0.2, 0.2])
            
            # Calculate upside potential
            current_price = await self.market_data.get_last_price(symbol)
            upside = (target_price - current_price) / current_price
            
            # Generate rating based on upside and risk
            if upside > 0.3 and risk.credit_risk < 0.3:
                rating = "Strong Buy"
            elif upside > 0.15 and risk.credit_risk < 0.4:
                rating = "Buy"
            elif upside < -0.15 or risk.credit_risk > 0.7:
                rating = "Sell"
            elif upside < -0.3 or risk.credit_risk > 0.8:
                rating = "Strong Sell"
            else:
                rating = "Hold"
            
            return rating, target_price, upside
            
        except Exception as e:
            logger.error(f"Error generating rating: {str(e)}")
            raise

    def _identify_key_points(
        self,
        ratios: FinancialRatios,
        valuation: ValuationModel,
        risk: RiskAssessment,
        growth: GrowthAnalysis,
        industry: IndustryMetrics
    ) -> Tuple[List[str], List[str]]:
        """Identify key strengths and risks."""
        try:
            strengths = []
            risks = []
            
            # Check profitability
            if ratios.net_margin > industry.average_net_margin:
                strengths.append(
                    "Above-average profit margins"
                )
            elif ratios.net_margin < industry.average_net_margin * 0.8:
                risks.append(
                    "Below-average profit margins"
                )
            
            # Check growth
            if growth.projected_earnings_growth[-1] > industry.earnings_growth:
                strengths.append(
                    "Strong earnings growth potential"
                )
            elif growth.projected_earnings_growth[-1] < 0:
                risks.append(
                    "Declining earnings forecast"
                )
            
            # Check valuation
            if valuation.margin_of_safety > 0.3:
                strengths.append(
                    "Attractive valuation with significant upside"
                )
            elif valuation.margin_of_safety < -0.2:
                risks.append(
                    "Potentially overvalued"
                )
            
            # Check financial health
            if risk.credit_risk > 0.7:
                risks.append(
                    "High credit risk"
                )
            elif risk.credit_risk < 0.3:
                strengths.append(
                    "Strong financial health"
                )
            
            # Check competitive position
            if growth.competitive_advantage > 0.7:
                strengths.append(
                    "Strong competitive advantage"
                )
            elif growth.competitive_advantage < 0.3:
                risks.append(
                    "Weak competitive position"
                )
            
            return strengths, risks
            
        except Exception as e:
            logger.error(f"Error identifying key points: {str(e)}")
            return [], []

    def _get_risk_level(self, risk: RiskAssessment) -> str:
        """Determine overall risk level."""
        try:
            # Calculate weighted risk score
            risk_score = np.average([
                risk.credit_risk,
                risk.liquidity_risk,
                risk.solvency_risk,
                risk.business_risk,
                risk.industry_risk,
                risk.regulatory_risk
            ], weights=[0.25, 0.15, 0.15, 0.20, 0.15, 0.10])
            
            if risk_score < 0.3:
                return "Low"
            elif risk_score < 0.6:
                return "Medium"
            else:
                return "High"
            
        except Exception as e:
            logger.error(f"Error getting risk level: {str(e)}")
            return "Medium"

# Global fundamental analysis service instance
fundamental_service = FundamentalService()
fundamental_analysis_service = FundamentalAnalysisService()
