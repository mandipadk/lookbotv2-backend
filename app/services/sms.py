from typing import Optional
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self):
        self.client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        self.from_number = settings.TWILIO_FROM_NUMBER

    async def send_sms(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> bool:
        """Send an SMS message using Twilio."""
        try:
            # Clean phone number
            to_number = self._clean_phone_number(to_number)
            
            # Validate phone number format
            if not self._validate_phone_number(to_number):
                logger.error(f"Invalid phone number format: {to_number}")
                return False
            
            # Create message parameters
            message_params = {
                "to": to_number,
                "from_": self.from_number,
                "body": message
            }
            
            # Add media URL if provided
            if media_url:
                message_params["media_url"] = [media_url]
            
            # Send message
            message = self.client.messages.create(**message_params)
            
            # Log success
            logger.info(
                f"SMS sent successfully. SID: {message.sid}, "
                f"To: {to_number}, Status: {message.status}"
            )
            
            return True
            
        except TwilioRestException as e:
            logger.error(
                f"Twilio error sending SMS to {to_number}: "
                f"Code {e.code}, Message: {e.msg}"
            )
            return False
            
        except Exception as e:
            logger.error(f"Error sending SMS to {to_number}: {str(e)}")
            return False

    def _clean_phone_number(self, phone_number: str) -> str:
        """Clean phone number to E.164 format."""
        # Remove any non-digit characters
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        # Add country code if missing
        if len(cleaned) == 10:  # US number without country code
            cleaned = f"+1{cleaned}"
        elif not cleaned.startswith('+'):
            cleaned = f"+{cleaned}"
            
        return cleaned

    def _validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format."""
        # Basic E.164 format validation
        if not phone_number.startswith('+'):
            return False
            
        # Should have between 10 and 15 digits
        digits = ''.join(filter(str.isdigit, phone_number))
        if not (10 <= len(digits) <= 15):
            return False
            
        return True

# Global SMS service instance
sms_service = SMSService()
