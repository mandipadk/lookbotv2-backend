from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from jinja2 import Environment, PackageLoader, select_autoescape
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import get_settings
from app.models.notification import (
    NotificationType,
    NotificationPriority,
    NotificationStatus,
    DBNotification
)
from app.core.redis import redis_client

settings = get_settings()
logger = logging.getLogger(__name__)

# Set up Jinja2 environment for email templates
jinja_env = Environment(
    loader=PackageLoader('app', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

class NotificationService:
    def __init__(self):
        self.settings = settings
        self._delivery_handlers = {
            NotificationType.EMAIL: self._send_email,
            NotificationType.WEBHOOK: self._send_webhook,
            NotificationType.SMS: self._send_sms,
            NotificationType.PUSH: self._send_push
        }

    async def send_notification(
        self,
        db: Session,
        user_id: UUID,
        type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.MEDIUM
    ) -> DBNotification:
        """Send a notification to a user."""
        try:
            # Create notification record
            notification = DBNotification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                data=data,
                priority=priority,
                status=NotificationStatus.PENDING
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)

            # Get user preferences
            user_prefs = await self._get_user_notification_preferences(user_id)
            if not user_prefs.get(type.value, {}).get('enabled', True):
                notification.status = NotificationStatus.SKIPPED
                notification.error = "Notification type disabled by user"
                db.commit()
                return notification

            # Send notification
            handler = self._delivery_handlers.get(type)
            if handler:
                success = await handler(
                    user_id=user_id,
                    title=title,
                    message=message,
                    data=data,
                    notification_id=notification.id
                )
                
                notification.status = (
                    NotificationStatus.DELIVERED if success
                    else NotificationStatus.FAILED
                )
                
                if not success:
                    notification.error = "Delivery failed"
                
                db.commit()
            else:
                notification.status = NotificationStatus.FAILED
                notification.error = f"No handler for notification type: {type}"
                db.commit()

            return notification

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            if notification:
                notification.status = NotificationStatus.FAILED
                notification.error = str(e)
                db.commit()
            return notification

    async def get_notifications(
        self,
        db: Session,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        status: Optional[NotificationStatus] = None
    ) -> List[DBNotification]:
        """Get notifications for a user."""
        query = db.query(DBNotification).filter(
            DBNotification.user_id == user_id
        )
        
        if status:
            query = query.filter(DBNotification.status == status)
        
        return query.order_by(
            DBNotification.created_at.desc()
        ).offset(skip).limit(limit).all()

    async def mark_as_read(
        self,
        db: Session,
        notification_id: UUID,
        user_id: UUID
    ) -> bool:
        """Mark a notification as read."""
        notification = db.query(DBNotification).filter(
            DBNotification.id == notification_id,
            DBNotification.user_id == user_id
        ).first()
        
        if not notification:
            return False
        
        notification.read = True
        notification.read_at = datetime.utcnow()
        db.commit()
        return True

    async def _get_user_notification_preferences(self, user_id: UUID) -> dict:
        """Get user's notification preferences from cache or database."""
        cache_key = f"notification_prefs:{user_id}"
        
        # Try to get from cache
        prefs = await redis_client.get_json(cache_key)
        if prefs:
            return prefs
        
        # Get from database
        # TODO: Implement user preferences in database
        default_prefs = {
            "email": {"enabled": True},
            "webhook": {"enabled": True},
            "sms": {"enabled": True},
            "push": {"enabled": True}
        }
        
        # Cache preferences
        await redis_client.set_json(cache_key, default_prefs, 3600)  # 1 hour
        
        return default_prefs

    async def _send_email(
        self,
        user_id: UUID,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        notification_id: Optional[UUID] = None
    ) -> bool:
        """Send an email notification."""
        try:
            # Get user's email
            user_email = "user@example.com"  # TODO: Get from user profile
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = title
            msg['From'] = settings.SMTP_FROM_EMAIL
            msg['To'] = user_email
            
            # Render email template
            template = jinja_env.get_template('email/alert.html')
            html_content = template.render(
                title=title,
                message=message,
                data=data
            )
            
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            async with aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                use_tls=True
            ) as smtp:
                await smtp.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD
                )
                await smtp.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False

    async def _send_webhook(
        self,
        user_id: UUID,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        notification_id: Optional[UUID] = None
    ) -> bool:
        """Send a webhook notification."""
        try:
            # Get user's webhook URL
            webhook_url = "https://example.com/webhook"  # TODO: Get from user profile
            
            # Prepare payload
            payload = {
                "id": str(notification_id) if notification_id else None,
                "title": title,
                "message": message,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send webhook
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=10.0
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Error sending webhook: {str(e)}")
            return False

    async def _send_sms(
        self,
        user_id: UUID,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        notification_id: Optional[UUID] = None
    ) -> bool:
        """Send an SMS notification."""
        try:
            # Get user's phone number from profile
            user_profile = await self._get_user_profile(user_id)
            if not user_profile or not user_profile.phone_number:
                logger.error(f"No phone number found for user {user_id}")
                return False

            # Format message
            sms_message = f"{title}\n\n{message}"
            if data:
                # Add relevant data points, keeping message concise
                if 'price' in data:
                    sms_message += f"\nPrice: ${data['price']}"
                if 'change_percent' in data:
                    sms_message += f"\nChange: {data['change_percent']}%"
                if 'volume' in data:
                    sms_message += f"\nVolume: {data['volume']}"

            # Send SMS using Twilio
            return await sms_service.send_sms(
                to_number=user_profile.phone_number,
                message=sms_message
            )
            
        except Exception as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return False

    async def _send_push(
        self,
        user_id: UUID,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        notification_id: Optional[UUID] = None
    ) -> bool:
        """Send a push notification."""
        try:
            # Get user's push tokens from profile
            user_profile = await self._get_user_profile(user_id)
            if not user_profile or not user_profile.push_tokens:
                logger.error(f"No push tokens found for user {user_id}")
                return False

            # Prepare notification data
            push_data = {
                "notification_id": str(notification_id) if notification_id else None,
                "type": "stock_alert",
                "timestamp": datetime.utcnow().isoformat()
            }
            if data:
                push_data.update(data)

            # Send push notification
            result = await push_service.send_push(
                tokens=user_profile.push_tokens,
                title=title,
                body=message,
                data=push_data,
                badge=await self._get_unread_count(user_id),
                sound="alert_sound.wav",
                priority="high"
            )

            # Return True if at least one token succeeded
            return len(result["success"]) > 0
            
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return False

    async def _get_user_profile(self, user_id: UUID) -> Optional[dict]:
        """Get user profile with notification preferences."""
        try:
            # Try to get from cache
            cache_key = f"user_profile:{user_id}"
            profile = await redis_client.get_json(cache_key)
            if profile:
                return profile

            # Get from database
            profile = await self._fetch_user_profile_from_db(user_id)
            if profile:
                # Cache for 1 hour
                await redis_client.set_json(cache_key, profile, 3600)
            return profile

        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return None

    async def _fetch_user_profile_from_db(self, user_id: UUID) -> Optional[dict]:
        """Fetch user profile from database."""
        try:
            # Get user profile from Supabase
            response = await supabase_client.table('user_profiles').select(
                'phone_number',
                'push_tokens',
                'email',
                'notification_preferences'
            ).eq('user_id', str(user_id)).single().execute()

            if response.data:
                return response.data
            return None

        except Exception as e:
            logger.error(f"Error fetching user profile from DB: {str(e)}")
            return None

    async def _get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        try:
            # Try to get from cache
            cache_key = f"unread_count:{user_id}"
            count = await redis_client.get(cache_key)
            if count is not None:
                return int(count)

            # Get from database
            response = await supabase_client.table('notifications').select(
                'id',
                count='exact'
            ).eq('user_id', str(user_id)).eq('read', False).execute()

            count = response.count or 0
            
            # Cache for 5 minutes
            await redis_client.set(cache_key, str(count), 300)
            
            return count

        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0

# Global notification service instance
notification_service = NotificationService()
