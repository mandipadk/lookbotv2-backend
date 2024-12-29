from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime
from typing import Dict, List

from app.models.fundamental import (
    FundamentalAnalysis,
    FinancialRatios,
    FinancialStatement,
    IndustryMetrics,
    PeerComparison,
    ValuationModel,
    RiskAssessment,
    GrowthAnalysis,
    DividendAnalysis
)
from app.services.fundamental import fundamental_service
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/fundamental", tags=["Fundamental Analysis"])

@router.get("/{symbol}/analysis", response_model=FundamentalAnalysis)
async def get_fundamental_analysis(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get complete fundamental analysis for a company."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting fundamental analysis: {str(e)}"
        )

@router.get("/{symbol}/ratios", response_model=FinancialRatios)
async def get_financial_ratios(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get financial ratios for a company."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return analysis.ratios
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting financial ratios: {str(e)}"
        )

@router.get("/{symbol}/financials", response_model=List[FinancialStatement])
async def get_financial_statements(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get historical financial statements."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return sorted(
            analysis.financials,
            key=lambda x: x.date,
            reverse=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting financial statements: {str(e)}"
        )

@router.get("/{symbol}/industry", response_model=IndustryMetrics)
async def get_industry_metrics(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get industry metrics and analysis."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return analysis.industry_metrics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting industry metrics: {str(e)}"
        )

@router.get("/{symbol}/peers", response_model=List[PeerComparison])
async def get_peer_comparison(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get peer comparison data."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return sorted(
            analysis.peer_comparison,
            key=lambda x: x.market_cap,
            reverse=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting peer comparison: {str(e)}"
        )

@router.get("/{symbol}/valuation", response_model=ValuationModel)
async def get_valuation(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get company valuation analysis."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return analysis.valuation
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting valuation: {str(e)}"
        )

@router.get("/{symbol}/risk", response_model=RiskAssessment)
async def get_risk_assessment(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get company risk assessment."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return analysis.risk
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting risk assessment: {str(e)}"
        )

@router.get("/{symbol}/growth", response_model=GrowthAnalysis)
async def get_growth_analysis(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get company growth analysis."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        return analysis.growth
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting growth analysis: {str(e)}"
        )

@router.get("/{symbol}/dividends", response_model=DividendAnalysis)
async def get_dividend_analysis(
    symbol: str,
    current_user=Depends(get_current_user)
):
    """Get dividend analysis if applicable."""
    try:
        analysis = await fundamental_service.get_fundamental_analysis(
            symbol=symbol
        )
        
        if not analysis.dividends:
            raise HTTPException(
                status_code=404,
                detail="No dividend data available for this company"
            )
        
        return analysis.dividends
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting dividend analysis: {str(e)}"
        )
