from typing import Dict, List, Optional, Set
import aiohttp
import asyncio
from datetime import datetime, timedelta
from app.core.config import get_settings
from app.core.redis import redis_client
import logging
from dataclasses import dataclass, field
from enum import Enum
from bs4 import BeautifulSoup
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import yfinance as yf
import re
from collections import defaultdict
from langchain.tools import YahooFinanceNewsTool
import feedparser
import json
import requests
from sec_api import QueryApi
from concurrent.futures import ThreadPoolExecutor

# Download required NLTK data
nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)

logger = logging.getLogger(__name__)
settings = get_settings()

class NewsSource(Enum):
    FINNHUB = "finnhub"
    FMP = "fmp"
    YAHOO = "yahoo"
    MARKETWATCH = "marketwatch"
    BENZINGA = "benzinga"
    SEC = "sec"
    REDDIT = "reddit"
    STOCKTWITS = "stocktwits"
    GOOGLE = "google"
    TWITTER = "twitter"
    OTC_MARKETS = "otc_markets"
    SEEKING_ALPHA = "seeking_alpha"

@dataclass
class NewsConfig:
    cache_times: Dict[str, int] = field(default_factory=lambda: {
        "news": 300,          # 5 minutes
        "topics": 3600,       # 1 hour
        "sentiment": 1800,    # 30 minutes
        "summary": 3600,      # 1 hour
        "sec_filings": 3600,  # 1 hour
        "social": 300,        # 5 minutes
    })
    max_articles: int = 200
    min_relevance_score: float = 0.5
    sentiment_threshold: float = 0.2
    penny_stock_threshold: float = 5.0  # Maximum price for penny stocks
    min_market_cap: float = 1000000     # Minimum market cap (1M)
    volume_spike_threshold: float = 3.0  # Volume spike multiplier

class NewsService:
    def __init__(self):
        self.config = NewsConfig()
        self.sia = SentimentIntensityAnalyzer()
        self.stop_words = set(stopwords.words('english'))
        self._known_tickers: Set[str] = set()
        self._penny_tickers: Set[str] = set()
        self._executor = ThreadPoolExecutor(max_workers=10)
        self.yahoo_news_tool = YahooFinanceNewsTool()
        self.sec_api = QueryApi(api_key=settings.SEC_API_KEY)
        self._update_known_tickers()

    async def _update_known_tickers(self):
        """Update the set of known stock tickers including penny stocks."""
        try:
            # Get tickers from Redis cache
            cached_tickers = await redis_client.get_market_data("known_tickers")
            cached_penny_tickers = await redis_client.get_market_data("penny_tickers")
            
            if cached_tickers and cached_penny_tickers:
                self._known_tickers = set(cached_tickers)
                self._penny_tickers = set(cached_penny_tickers)
                return

            tickers = set()
            penny_tickers = set()

            # Get OTC/Pink Sheet tickers
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://www.otcmarkets.com/research/stock-screener",
                    params={"page": 1, "pageSize": 500}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        for stock in data.get('stocks', []):
                            symbol = stock['symbol']
                            price = float(stock.get('price', 0))
                            if price <= self.config.penny_stock_threshold:
                                penny_tickers.add(symbol)
                            tickers.add(symbol)

            # Get additional penny stocks from FMP
            penny_stocks = await self._fmp_request("stock-screener", {
                "priceMoreThan": 0.01,
                "priceLowerThan": self.config.penny_stock_threshold,
                "volumeMoreThan": 50000,
                "limit": 1000
            })
            
            if penny_stocks:
                for stock in penny_stocks:
                    symbol = stock['symbol']
                    penny_tickers.add(symbol)
                    tickers.add(symbol)

            # Add regular stocks
            regular_stocks = await self._fmp_request("stock/list")
            if regular_stocks:
                tickers.update(s['symbol'] for s in regular_stocks)

            self._known_tickers = tickers
            self._penny_tickers = penny_tickers
            
            await redis_client.cache_market_data("known_tickers", list(tickers), 86400)
            await redis_client.cache_market_data("penny_tickers", list(penny_tickers), 86400)

        except Exception as e:
            logger.error(f"Error updating known tickers: {str(e)}")

    async def _get_sec_filings(self, symbol: str) -> List[Dict]:
        """Get recent SEC filings for a company."""
        try:
            query = {
                "query": {
                    "query_string": {
                        "query": f"ticker:{symbol} AND filedAt:[now-30d TO now]"
                    }
                },
                "from": 0,
                "size": 50,
                "sort": [{"filedAt": {"order": "desc"}}]
            }
            
            response = self.sec_api.get_filings(query)
            return response['filings']
        except Exception as e:
            logger.error(f"Error getting SEC filings: {str(e)}")
            return []

    async def _get_social_media_mentions(self, symbol: str) -> List[Dict]:
        """Get social media mentions for a symbol."""
        mentions = []
        
        # StockTwits
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        for message in data.get('messages', []):
                            mentions.append({
                                "source": "stocktwits",
                                "text": message['body'],
                                "timestamp": message['created_at'],
                                "sentiment": message.get('entities', {}).get('sentiment', {}).get('basic', 'neutral')
                            })
        except Exception as e:
            logger.error(f"Error getting StockTwits data: {str(e)}")

        # Reddit (wallstreetbets, pennystocks, etc.)
        subreddits = ['wallstreetbets', 'pennystocks', 'stocks']
        for subreddit in subreddits:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://www.reddit.com/r/{subreddit}/search.json",
                        params={"q": symbol, "t": "day", "limit": 100}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            for post in data.get('data', {}).get('children', []):
                                post_data = post['data']
                                mentions.append({
                                    "source": f"reddit_{subreddit}",
                                    "text": f"{post_data['title']} {post_data.get('selftext', '')}",
                                    "timestamp": datetime.fromtimestamp(post_data['created_utc']).isoformat(),
                                    "score": post_data['score'],
                                    "comments": post_data['num_comments']
                                })
            except Exception as e:
                logger.error(f"Error getting Reddit data: {str(e)}")

        return mentions

    def _is_penny_stock(self, symbol: str) -> bool:
        """Check if a stock is a penny stock."""
        return symbol in self._penny_tickers

    async def get_news(
        self,
        tickers: Optional[Set[str]] = None,
        topics: Optional[List[str]] = None,
        sources: Optional[List[NewsSource]] = None,
        min_sentiment: Optional[float] = None,
        include_filings: bool = True,
        include_social: bool = True,
        penny_stocks_only: bool = False
    ) -> List[Dict]:
        """
        Get news articles filtered by tickers and topics.
        
        Args:
            tickers: Set of stock tickers to filter by
            topics: List of topics to filter by
            sources: List of news sources to use
            min_sentiment: Minimum compound sentiment score (-1 to 1)
            include_filings: Whether to include SEC filings
            include_social: Whether to include social media mentions
            penny_stocks_only: Whether to only include penny stocks
        """
        try:
            sources = sources or list(NewsSource)
            
            # Filter for penny stocks if requested
            if penny_stocks_only and tickers:
                tickers = {t for t in tickers if self._is_penny_stock(t)}
            
            # Generate cache key
            cache_key = (
                f"news:{'-'.join(sorted(tickers or []))}:"
                f"{include_filings}:{include_social}:{penny_stocks_only}"
            )
            
            cached_news = await redis_client.get_market_data(cache_key)
            if cached_news:
                return cached_news

            all_articles = []
            
            # Gather news from all sources
            for source in sources:
                if source == NewsSource.YAHOO:
                    # Use LangChain's YahooFinanceNewsTool
                    for ticker in (tickers or ['']):
                        try:
                            news = self.yahoo_news_tool.run(ticker)
                            if isinstance(news, str):
                                news = json.loads(news)
                            all_articles.extend(news)
                        except Exception as e:
                            logger.error(f"Error getting Yahoo news: {str(e)}")

                elif source == NewsSource.SEC and include_filings:
                    for ticker in (tickers or []):
                        filings = await self._get_sec_filings(ticker)
                        for filing in filings:
                            all_articles.append({
                                "title": f"{filing['formType']} Filing",
                                "description": filing.get('description', ''),
                                "url": filing['linkToFilingDetails'],
                                "datetime": filing['filedAt'],
                                "source": "SEC",
                                "filing_type": filing['formType']
                            })

                elif source == NewsSource.STOCKTWITS and include_social:
                    for ticker in (tickers or []):
                        mentions = await self._get_social_media_mentions(ticker)
                        for mention in mentions:
                            all_articles.append({
                                "title": f"Social Media Mention - {mention['source']}",
                                "description": mention['text'],
                                "datetime": mention['timestamp'],
                                "source": mention['source'],
                                "social_metrics": {
                                    "score": mention.get('score'),
                                    "comments": mention.get('comments')
                                }
                            })

                # Add other sources (Finnhub, FMP, etc.) as before
                if source == NewsSource.FINNHUB:
                    for ticker in (tickers or ['']):  # Use empty string for general news
                        news = await self._finnhub_request(f"company-news?symbol={ticker}")
                        if news:
                            all_articles.extend(news)

                if source == NewsSource.FMP:
                    news = await self._fmp_request("stock_news")
                    if news:
                        all_articles.extend(news)

            # Process and filter articles
            processed_articles = []
            for article in all_articles:
                # Extract tickers and topics
                article_tickers = self._extract_tickers(
                    f"{article['title']} {article.get('description', '')}"
                )
                
                # Skip if penny_stocks_only and no penny stocks mentioned
                if penny_stocks_only and not any(
                    self._is_penny_stock(t) for t in article_tickers
                ):
                    continue
                
                article_topics = self._extract_topics(
                    f"{article['title']} {article.get('description', '')}"
                )
                
                # Calculate relevance score
                relevance_score = self._calculate_relevance_score(
                    article, tickers or set(), topics or []
                )
                
                if relevance_score >= self.config.min_relevance_score:
                    # Analyze sentiment
                    sentiment = self._analyze_sentiment(
                        f"{article['title']} {article.get('description', '')}"
                    )
                    
                    if min_sentiment is not None and sentiment['compound'] < min_sentiment:
                        continue
                    
                    processed_article = {
                        "id": article.get('id', hash(article['title'])),
                        "title": article['title'],
                        "description": article.get('description', ''),
                        "url": article.get('url'),
                        "datetime": article['datetime'],
                        "source": article.get('source', 'unknown'),
                        "tickers": list(article_tickers),
                        "topics": article_topics,
                        "sentiment": sentiment,
                        "relevance_score": relevance_score,
                        "is_penny_stock": any(
                            self._is_penny_stock(t) for t in article_tickers
                        ),
                        "filing_type": article.get('filing_type'),
                        "social_metrics": article.get('social_metrics')
                    }
                    processed_articles.append(processed_article)

            # Sort by relevance score and timestamp
            processed_articles.sort(
                key=lambda x: (x['relevance_score'], x['datetime']),
                reverse=True
            )

            # Cache the results
            await redis_client.cache_market_data(
                cache_key,
                processed_articles[:self.config.max_articles],
                self.config.cache_times["news"]
            )

            return processed_articles[:self.config.max_articles]

        except Exception as e:
            logger.error(f"Error getting news: {str(e)}")
            return []

    async def get_trending_topics(self) -> List[Dict]:
        """Get trending topics from recent news articles."""
        try:
            cache_key = "trending_topics"
            cached_topics = await redis_client.get_market_data(cache_key)
            if cached_topics:
                return cached_topics

            # Get recent news
            news = await self.get_news()
            
            # Aggregate topics
            topic_scores = defaultdict(float)
            for article in news:
                for topic, freq in article['topics']:
                    # Weight by article relevance and recency
                    weight = article['relevance_score']
                    pub_time = datetime.fromisoformat(article['datetime'].replace('Z', '+00:00'))
                    hours_old = (datetime.utcnow() - pub_time).total_seconds() / 3600
                    recency_weight = max(0, 1 - (hours_old / 24))
                    
                    topic_scores[topic] += freq * weight * recency_weight

            # Sort and format topics
            trending_topics = [
                {
                    "topic": topic,
                    "score": score,
                    "related_tickers": self._find_related_tickers(topic, news)
                }
                for topic, score in sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
            ][:20]  # Top 20 topics

            # Cache the results
            await redis_client.cache_market_data(
                cache_key,
                trending_topics,
                self.config.cache_times["topics"]
            )

            return trending_topics

        except Exception as e:
            logger.error(f"Error getting trending topics: {str(e)}")
            return []

    def _find_related_tickers(self, topic: str, articles: List[Dict]) -> List[str]:
        """Find tickers frequently mentioned with a topic."""
        ticker_scores = defaultdict(float)
        
        for article in articles:
            if any(t[0] == topic for t in article['topics']):
                for ticker in article['tickers']:
                    ticker_scores[ticker] += article['relevance_score']
        
        return [
            ticker for ticker, _ in 
            sorted(ticker_scores.items(), key=lambda x: x[1], reverse=True)
        ][:5]  # Top 5 related tickers

    async def _fmp_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make request to FMP API."""
        try:
            params = params or {}
            params["apikey"] = settings.FMP_API_KEY
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://financialmodelingprep.com/api/v3/{endpoint}", params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"FMP API request error: {str(e)}")
            return None

    async def _finnhub_request(self, endpoint: str) -> Optional[List[Dict]]:
        """Make request to Finnhub API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://finnhub.io/api/v1/{endpoint}?token={settings.FINNHUB_API_KEY}") as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Finnhub API request error: {str(e)}")
            return None

    def _extract_tickers(self, text: str) -> Set[str]:
        """Extract stock tickers from text."""
        # Common words that might be mistaken for tickers
        exclusions = {'CEO', 'CFO', 'CTO', 'THE', 'A', 'I', 'FOR', 'AT', 'BY', 'OF', 'ON', 'IN', 'TO'}
        
        # Find potential tickers (2-5 uppercase letters)
        words = set(word.strip('.,!?()[]{}') for word in text.split())
        potential_tickers = {
            word for word in words 
            if word.isupper() and 2 <= len(word) <= 5 
            and word not in exclusions
            and word in self._known_tickers
        }
        
        return potential_tickers

    def _extract_topics(self, text: str) -> List[str]:
        """Extract main topics from text using NLP."""
        # Tokenize and tag parts of speech
        tokens = word_tokenize(text.lower())
        tagged = nltk.pos_tag(tokens)
        
        # Extract noun phrases and named entities
        topics = []
        
        # Get noun phrases
        for i in range(len(tagged)-1):
            if tagged[i][1].startswith('JJ') and tagged[i+1][1].startswith('NN'):
                phrase = f"{tagged[i][0]} {tagged[i+1][0]}"
                if phrase not in self.stop_words:
                    topics.append(phrase)
            elif tagged[i][1].startswith('NN') and tagged[i+1][1].startswith('NN'):
                phrase = f"{tagged[i][0]} {tagged[i+1][0]}"
                if phrase not in self.stop_words:
                    topics.append(phrase)
        
        # Count frequencies and return top topics
        topic_freq = defaultdict(int)
        for topic in topics:
            topic_freq[topic] += 1
        
        return sorted(topic_freq.items(), key=lambda x: x[1], reverse=True)[:10]

    def _analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of text."""
        sentiment_scores = self.sia.polarity_scores(text)
        return {
            "positive": sentiment_scores["pos"],
            "negative": sentiment_scores["neg"],
            "neutral": sentiment_scores["neu"],
            "compound": sentiment_scores["compound"]
        }

    def _calculate_relevance_score(self, article: Dict, tickers: Set[str], topics: List[str]) -> float:
        """Calculate article relevance score based on tickers and topics."""
        score = 0.0
        text = f"{article['title']} {article.get('description', '')}"
        
        # Score based on ticker mentions
        if tickers:
            ticker_mentions = sum(1 for ticker in tickers if ticker in text.upper())
            score += 0.4 * min(ticker_mentions / len(tickers), 1.0)
        
        # Score based on topic matches
        if topics:
            topic_matches = sum(1 for topic, _ in topics if topic.lower() in text.lower())
            score += 0.4 * min(topic_matches / len(topics), 1.0)
        
        # Score based on recency
        pub_time = datetime.fromisoformat(article['datetime'].replace('Z', '+00:00'))
        hours_old = (datetime.utcnow() - pub_time).total_seconds() / 3600
        recency_score = max(0, 1 - (hours_old / 24))  # Decay over 24 hours
        score += 0.2 * recency_score
        
        return score

# Global news service instance
news_service = NewsService()
