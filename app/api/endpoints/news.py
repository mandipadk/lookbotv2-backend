from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.news import news_service, NewsSource
from app.api.dependencies.auth import get_current_user
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/articles")
async def get_news_articles(
    tickers: Optional[Set[str]] = Query(None, description="Stock tickers to filter by"),
    topics: Optional[List[str]] = Query(None, description="Topics to filter by"),
    sources: Optional[List[NewsSource]] = Query(None, description="News sources to use"),
    min_sentiment: Optional[float] = Query(
        None,
        description="Minimum sentiment score (-1 to 1)",
        ge=-1,
        le=1
    ),
    include_filings: bool = Query(
        True,
        description="Include SEC filings"
    ),
    include_social: bool = Query(
        True,
        description="Include social media mentions"
    ),
    penny_stocks_only: bool = Query(
        False,
        description="Only include penny stocks"
    ),
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get news articles filtered by tickers and topics.
    
    - **tickers**: Optional set of stock tickers (e.g., ["AAPL", "MSFT"])
    - **topics**: Optional list of topics (e.g., ["artificial intelligence", "earnings"])
    - **sources**: Optional list of news sources
    - **min_sentiment**: Optional minimum sentiment score (-1 to 1)
    - **include_filings**: Whether to include SEC filings
    - **include_social**: Whether to include social media mentions
    - **penny_stocks_only**: Whether to only include penny stocks
    
    Returns a list of articles with:
    - title
    - description
    - url
    - datetime
    - source
    - extracted tickers
    - relevant topics
    - sentiment analysis
    - relevance score
    - is_penny_stock flag
    - filing_type (if SEC filing)
    - social_metrics (if social media mention)
    """
    articles = await news_service.get_news(
        tickers=tickers,
        topics=topics,
        sources=sources,
        min_sentiment=min_sentiment,
        include_filings=include_filings,
        include_social=include_social,
        penny_stocks_only=penny_stocks_only
    )
    
    if not articles:
        raise HTTPException(
            status_code=404,
            detail="No articles found matching the criteria"
        )
    
    return articles

@router.get("/trending")
async def get_trending_topics(
    penny_stocks_only: bool = Query(
        False,
        description="Only include penny stock topics"
    ),
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get trending topics from recent news articles.
    
    - **penny_stocks_only**: Whether to only include penny stock topics
    
    Returns a list of topics with:
    - topic name
    - trend score
    - related tickers
    - penny stock indicators
    """
    topics = await news_service.get_trending_topics(penny_stocks_only=penny_stocks_only)
    
    if not topics:
        raise HTTPException(
            status_code=404,
            detail="No trending topics found"
        )
    
    return topics

@router.get("/filings/{symbol}")
async def get_sec_filings(
    symbol: str,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get recent SEC filings for a company.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    
    Returns a list of SEC filings with:
    - filing type
    - description
    - filing date
    - link to filing
    """
    filings = await news_service._get_sec_filings(symbol.upper())
    
    if not filings:
        raise HTTPException(
            status_code=404,
            detail=f"No SEC filings found for symbol: {symbol}"
        )
    
    return filings

@router.get("/social/{symbol}")
async def get_social_mentions(
    symbol: str,
    current_user: dict = Depends(get_current_user)
) -> List[Dict]:
    """
    Get social media mentions for a symbol.
    
    - **symbol**: Stock symbol (e.g., AAPL)
    
    Returns a list of social media mentions with:
    - source (reddit, stocktwits, etc.)
    - text content
    - timestamp
    - sentiment
    - social metrics (score, comments, etc.)
    """
    mentions = await news_service._get_social_media_mentions(symbol.upper())
    
    if not mentions:
        raise HTTPException(
            status_code=404,
            detail=f"No social media mentions found for symbol: {symbol}"
        )
    
    return mentions
