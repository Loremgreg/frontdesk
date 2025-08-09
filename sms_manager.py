import os
from typing import Optional

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

class SMSManager:
    def __init__(self):
        """Initialize the SMS manager with Twilio credentials from environment variables."""
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        if not all([self.account_sid, self.auth_token, self.from_phone_number]):
            raise ValueError(
                "Missing required Twilio environment variables. "
                "Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER."
            )
            
        self.client = Client(self.account_sid, self.auth_token)

    def send_confirmation_sms(self, to_phone_number: str, appointment_details: str, language: str = "de") -> bool:
        """
        Send a confirmation SMS to the specified phone number.
        
        Args:
            to_phone_number: The recipient's phone number in E.164 format (e.g., +491746260679)
            appointment_details: The appointment details to include in the message
            language: The language for the SMS message (default: "de" for German)
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # Message templates by language
        message_templates = {
            "de": f"Bestätigung des Termins: {appointment_details}",
            "fr": f"Confirmation de rendez-vous: {appointment_details}",
            "en": f"Appointment confirmation: {appointment_details}"
        }
        
        message_body = message_templates.get(language, message_templates["de"])
        
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=self.from_phone_number,
                to=to_phone_number
            )
            print(f"SMS sent successfully. SID: {message.sid}")
            return True
        except TwilioRestException as e:
            print(f"Error sending SMS: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error sending SMS: {e}")
            return False