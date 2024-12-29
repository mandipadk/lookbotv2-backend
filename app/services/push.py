from typing import List, Dict, Optional, Any
import logging
import json
from firebase_admin import messaging, credentials, initialize_app
from google.cloud.exceptions import NotFound

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class PushService:
    def __init__(self):
        # Initialize Firebase Admin SDK
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        initialize_app(cred)

    async def send_push(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        badge: Optional[int] = None,
        sound: Optional[str] = None,
        priority: str = "high",
        ttl: int = 86400  # 24 hours
    ) -> Dict[str, List[str]]:
        """Send push notification using Firebase Cloud Messaging."""
        try:
            # Validate input
            if not tokens:
                logger.error("No tokens provided for push notification")
                return {"success": [], "failure": []}
            
            # Create notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url
            )
            
            # Create Android config
            android_config = messaging.AndroidConfig(
                priority=priority,
                notification=messaging.AndroidNotification(
                    icon='stock_icon',
                    color='#2196F3',
                    sound='default' if sound else None,
                    notification_priority='PRIORITY_HIGH',
                    default_sound=bool(sound),
                    default_vibrate_timings=True,
                    visibility='PUBLIC'
                )
            )
            
            # Create APNS config
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        badge=badge,
                        sound=sound if sound else 'default',
                        content_available=True,
                        mutable_content=True,
                        category='STOCK_ALERT'
                    )
                )
            )
            
            # Create message
            message = messaging.MulticastMessage(
                notification=notification,
                data=data,
                android=android_config,
                apns=apns_config,
                tokens=tokens,
            )
            
            # Send message
            response = messaging.send_multicast(message)
            
            # Process results
            success_tokens = []
            failure_tokens = []
            
            for idx, result in enumerate(response.responses):
                if result.success:
                    success_tokens.append(tokens[idx])
                else:
                    failure_tokens.append(tokens[idx])
                    logger.error(
                        f"Error sending to token {tokens[idx]}: {result.exception}"
                    )
            
            # Log results
            logger.info(
                f"Push notification sent. Success: {len(success_tokens)}, "
                f"Failure: {len(failure_tokens)}"
            )
            
            return {
                "success": success_tokens,
                "failure": failure_tokens
            }
            
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return {
                "success": [],
                "failure": tokens
            }

    async def subscribe_to_topic(
        self,
        tokens: List[str],
        topic: str
    ) -> Dict[str, List[str]]:
        """Subscribe tokens to a topic."""
        try:
            # Clean topic name
            topic = self._clean_topic_name(topic)
            
            # Subscribe tokens
            response = messaging.subscribe_to_topic(tokens, topic)
            
            # Process results
            success_tokens = []
            failure_tokens = []
            
            for idx, result in enumerate(response.results):
                if result.success:
                    success_tokens.append(tokens[idx])
                else:
                    failure_tokens.append(tokens[idx])
                    logger.error(
                        f"Error subscribing token {tokens[idx]} to topic {topic}"
                    )
            
            return {
                "success": success_tokens,
                "failure": failure_tokens
            }
            
        except Exception as e:
            logger.error(f"Error subscribing to topic: {str(e)}")
            return {
                "success": [],
                "failure": tokens
            }

    async def unsubscribe_from_topic(
        self,
        tokens: List[str],
        topic: str
    ) -> Dict[str, List[str]]:
        """Unsubscribe tokens from a topic."""
        try:
            # Clean topic name
            topic = self._clean_topic_name(topic)
            
            # Unsubscribe tokens
            response = messaging.unsubscribe_from_topic(tokens, topic)
            
            # Process results
            success_tokens = []
            failure_tokens = []
            
            for idx, result in enumerate(response.results):
                if result.success:
                    success_tokens.append(tokens[idx])
                else:
                    failure_tokens.append(tokens[idx])
                    logger.error(
                        f"Error unsubscribing token {tokens[idx]} from topic {topic}"
                    )
            
            return {
                "success": success_tokens,
                "failure": failure_tokens
            }
            
        except Exception as e:
            logger.error(f"Error unsubscribing from topic: {str(e)}")
            return {
                "success": [],
                "failure": tokens
            }

    async def send_topic_message(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        priority: str = "high"
    ) -> bool:
        """Send message to a topic."""
        try:
            # Clean topic name
            topic = self._clean_topic_name(topic)
            
            # Create message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url
                ),
                data=data,
                topic=topic
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"Successfully sent topic message: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending topic message: {str(e)}")
            return False

    def _clean_topic_name(self, topic: str) -> str:
        """Clean topic name to match FCM requirements."""
        # Remove special characters and spaces
        cleaned = ''.join(
            c for c in topic.lower()
            if c.isalnum() or c in ['-', '_']
        )
        
        # Ensure it starts with a letter or number
        if not cleaned[0].isalnum():
            cleaned = f"t{cleaned}"
            
        return cleaned

# Global push notification service instance
push_service = PushService()
