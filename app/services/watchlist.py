from typing import List, Optional, Set
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta
import logging

from app.models.watchlist import (
    Alert, AlertCreate, AlertType, AlertCondition, AlertPriority,
    WatchlistItem, WatchlistItemCreate,
    Watchlist, WatchlistCreate, WatchlistType,
    DBAlert, DBWatchlistItem, DBWatchlist
)
from app.services.market_data import market_data_service
from app.services.news import news_service
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class WatchlistService:
    def __init__(self):
        self._alert_handlers = {
            AlertType.PRICE: self._check_price_alert,
            AlertType.VOLUME: self._check_volume_alert,
            AlertType.NEWS: self._check_news_alert,
            AlertType.TECHNICAL: self._check_technical_alert,
            AlertType.FILING: self._check_filing_alert,
            AlertType.SOCIAL: self._check_social_alert,
            AlertType.CUSTOM: self._check_custom_alert
        }

    async def create_watchlist(
        self,
        db: Session,
        user_id: UUID,
        watchlist: WatchlistCreate
    ) -> Watchlist:
        """Create a new watchlist."""
        db_watchlist = DBWatchlist(
            **watchlist.dict(),
            user_id=user_id
        )
        db.add(db_watchlist)
        db.commit()
        db.refresh(db_watchlist)
        return Watchlist.from_orm(db_watchlist)

    async def get_watchlist(
        self,
        db: Session,
        watchlist_id: UUID,
        user_id: UUID
    ) -> Optional[Watchlist]:
        """Get a watchlist by ID."""
        db_watchlist = db.query(DBWatchlist).filter(
            DBWatchlist.id == watchlist_id,
            DBWatchlist.user_id == user_id
        ).first()
        
        if not db_watchlist:
            return None
            
        return Watchlist.from_orm(db_watchlist)

    async def get_watchlists(
        self,
        db: Session,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Watchlist]:
        """Get all watchlists for a user."""
        db_watchlists = db.query(DBWatchlist).filter(
            DBWatchlist.user_id == user_id
        ).offset(skip).limit(limit).all()
        
        return [Watchlist.from_orm(w) for w in db_watchlists]

    async def update_watchlist(
        self,
        db: Session,
        watchlist_id: UUID,
        user_id: UUID,
        updates: dict
    ) -> Optional[Watchlist]:
        """Update a watchlist."""
        db_watchlist = db.query(DBWatchlist).filter(
            DBWatchlist.id == watchlist_id,
            DBWatchlist.user_id == user_id
        ).first()
        
        if not db_watchlist:
            return None
            
        for key, value in updates.items():
            setattr(db_watchlist, key, value)
        
        db_watchlist.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_watchlist)
        return Watchlist.from_orm(db_watchlist)

    async def delete_watchlist(
        self,
        db: Session,
        watchlist_id: UUID,
        user_id: UUID
    ) -> bool:
        """Delete a watchlist."""
        db_watchlist = db.query(DBWatchlist).filter(
            DBWatchlist.id == watchlist_id,
            DBWatchlist.user_id == user_id
        ).first()
        
        if not db_watchlist:
            return False
            
        db.delete(db_watchlist)
        db.commit()
        return True

    async def add_watchlist_item(
        self,
        db: Session,
        watchlist_id: UUID,
        user_id: UUID,
        item: WatchlistItemCreate
    ) -> Optional[WatchlistItem]:
        """Add an item to a watchlist."""
        # Verify watchlist exists and belongs to user
        db_watchlist = db.query(DBWatchlist).filter(
            DBWatchlist.id == watchlist_id,
            DBWatchlist.user_id == user_id
        ).first()
        
        if not db_watchlist:
            return None

        # Validate symbol exists
        if not await market_data_service.validate_symbol(item.symbol):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid symbol: {item.symbol}"
            )

        # Create watchlist item
        db_item = DBWatchlistItem(
            **item.dict(),
            watchlist_id=watchlist_id
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return WatchlistItem.from_orm(db_item)

    async def remove_watchlist_item(
        self,
        db: Session,
        watchlist_id: UUID,
        user_id: UUID,
        item_id: UUID
    ) -> bool:
        """Remove an item from a watchlist."""
        # Verify watchlist exists and belongs to user
        db_watchlist = db.query(DBWatchlist).filter(
            DBWatchlist.id == watchlist_id,
            DBWatchlist.user_id == user_id
        ).first()
        
        if not db_watchlist:
            return False

        # Delete item
        result = db.query(DBWatchlistItem).filter(
            DBWatchlistItem.id == item_id,
            DBWatchlistItem.watchlist_id == watchlist_id
        ).delete()
        
        db.commit()
        return result > 0

    async def add_alert(
        self,
        db: Session,
        watchlist_id: UUID,
        user_id: UUID,
        alert: AlertCreate
    ) -> Optional[Alert]:
        """Add an alert to a watchlist."""
        # Verify watchlist exists and belongs to user
        db_watchlist = db.query(DBWatchlist).filter(
            DBWatchlist.id == watchlist_id,
            DBWatchlist.user_id == user_id
        ).first()
        
        if not db_watchlist:
            return None

        # Create alert
        db_alert = DBAlert(
            **alert.dict(),
            watchlist_id=watchlist_id
        )
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        return Alert.from_orm(db_alert)

    async def remove_alert(
        self,
        db: Session,
        watchlist_id: UUID,
        user_id: UUID,
        alert_id: UUID
    ) -> bool:
        """Remove an alert from a watchlist."""
        # Verify watchlist exists and belongs to user
        db_watchlist = db.query(DBWatchlist).filter(
            DBWatchlist.id == watchlist_id,
            DBWatchlist.user_id == user_id
        ).first()
        
        if not db_watchlist:
            return False

        # Delete alert
        result = db.query(DBAlert).filter(
            DBAlert.id == alert_id,
            DBAlert.watchlist_id == watchlist_id
        ).delete()
        
        db.commit()
        return result > 0

    async def check_alerts(self, db: Session) -> List[dict]:
        """Check all active alerts and return triggered ones."""
        triggered_alerts = []
        
        # Get all active alerts
        active_alerts = db.query(DBAlert).filter(
            DBAlert.enabled == True
        ).all()
        
        for alert in active_alerts:
            # Skip if in cooldown
            if alert.last_triggered and datetime.utcnow() - alert.last_triggered < timedelta(minutes=alert.cooldown_minutes):
                continue
                
            # Check alert condition
            handler = self._alert_handlers.get(alert.type)
            if handler and await handler(alert):
                # Update alert
                alert.last_triggered = datetime.utcnow()
                alert.trigger_count += 1
                db.commit()
                
                triggered_alerts.append({
                    "alert": Alert.from_orm(alert),
                    "watchlist": Watchlist.from_orm(alert.watchlist),
                    "triggered_at": datetime.utcnow()
                })
        
        return triggered_alerts

    async def _check_price_alert(self, alert: DBAlert) -> bool:
        """Check if a price alert is triggered."""
        try:
            # Get current price
            symbol = alert.watchlist.items[0].symbol if alert.watchlist.items else None
            if not symbol:
                return False
                
            price = await market_data_service.get_current_price(symbol)
            if not price:
                return False
            
            alert_value = float(alert.value)
            
            if alert.condition == AlertCondition.ABOVE:
                return price > alert_value
            elif alert.condition == AlertCondition.BELOW:
                return price < alert_value
            elif alert.condition == AlertCondition.PERCENT_CHANGE:
                prev_price = await market_data_service.get_previous_close(symbol)
                if not prev_price:
                    return False
                change = (price - prev_price) / prev_price * 100
                return abs(change) >= alert_value
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking price alert: {str(e)}")
            return False

    async def _check_volume_alert(self, alert: DBAlert) -> bool:
        """Check if a volume alert is triggered."""
        try:
            symbol = alert.watchlist.items[0].symbol if alert.watchlist.items else None
            if not symbol:
                return False
                
            volume = await market_data_service.get_current_volume(symbol)
            if not volume:
                return False
            
            alert_value = float(alert.value)
            
            if alert.condition == AlertCondition.VOLUME_SPIKE:
                avg_volume = await market_data_service.get_average_volume(symbol)
                if not avg_volume:
                    return False
                return volume >= (avg_volume * alert_value)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking volume alert: {str(e)}")
            return False

    async def _check_news_alert(self, alert: DBAlert) -> bool:
        """Check if a news alert is triggered."""
        try:
            symbol = alert.watchlist.items[0].symbol if alert.watchlist.items else None
            if not symbol:
                return False
            
            # Get recent news
            news = await news_service.get_news(
                tickers={symbol},
                min_sentiment=float(alert.value) if alert.condition == AlertCondition.SENTIMENT else None
            )
            
            if not news:
                return False
            
            # Check if any news articles match the condition
            for article in news:
                if alert.condition == AlertCondition.SENTIMENT:
                    if article["sentiment"]["compound"] >= float(alert.value):
                        return True
                elif alert.condition == AlertCondition.TOPIC:
                    if any(topic == alert.value for topic, _ in article["topics"]):
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking news alert: {str(e)}")
            return False

    async def _check_filing_alert(self, alert: DBAlert) -> bool:
        """Check if a filing alert is triggered."""
        try:
            symbol = alert.watchlist.items[0].symbol if alert.watchlist.items else None
            if not symbol:
                return False
            
            # Get recent filings
            filings = await news_service._get_sec_filings(symbol)
            
            if not filings:
                return False
            
            # Check if any filings match the condition
            if alert.condition == AlertCondition.FILING_TYPE:
                return any(
                    filing["formType"] == alert.value
                    for filing in filings
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking filing alert: {str(e)}")
            return False

    async def _check_social_alert(self, alert: DBAlert) -> bool:
        """Check if a social media alert is triggered."""
        try:
            symbol = alert.watchlist.items[0].symbol if alert.watchlist.items else None
            if not symbol:
                return False
            
            # Get social media mentions
            mentions = await news_service._get_social_media_mentions(symbol)
            
            if not mentions:
                return False
            
            # Check if social volume exceeds threshold
            if alert.condition == AlertCondition.SOCIAL_VOLUME:
                return len(mentions) >= float(alert.value)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking social alert: {str(e)}")
            return False

    async def _check_technical_alert(self, alert: DBAlert) -> bool:
        """Check if a technical indicator alert is triggered."""
        try:
            symbol = alert.watchlist.items[0].symbol if alert.watchlist.items else None
            if not symbol:
                return False
            
            # Get technical indicators
            indicators = await market_data_service.get_technical_indicators(symbol)
            
            if not indicators:
                return False
            
            # Parse indicator and value from alert value (e.g., "RSI:70")
            indicator, threshold = alert.value.split(":")
            threshold = float(threshold)
            
            if indicator not in indicators:
                return False
            
            value = indicators[indicator]
            
            if alert.condition == AlertCondition.ABOVE:
                return value > threshold
            elif alert.condition == AlertCondition.BELOW:
                return value < threshold
            elif alert.condition == AlertCondition.CROSSES_ABOVE:
                prev_value = await market_data_service.get_previous_indicator(symbol, indicator)
                return prev_value < threshold and value >= threshold
            elif alert.condition == AlertCondition.CROSSES_BELOW:
                prev_value = await market_data_service.get_previous_indicator(symbol, indicator)
                return prev_value > threshold and value <= threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking technical alert: {str(e)}")
            return False

    async def _check_custom_alert(self, alert: DBAlert) -> bool:
        """Check if a custom alert is triggered."""
        # Implement custom alert logic here
        return False

# Global watchlist service instance
watchlist_service = WatchlistService()
