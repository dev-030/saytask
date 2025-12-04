"""
FCM (Firebase Cloud Messaging) Service
Handles push notifications to Flutter mobile app
"""
from firebase_admin import messaging
import logging

logger = logging.getLogger(__name__)


class FCMService:
    """Service for sending Firebase Cloud Messaging notifications"""
    
    @staticmethod
    def send_notification(fcm_token, title, body, data=None):
        """
        Send FCM push notification to a device
        
        Args:
            fcm_token (str): FCM device token
            title (str): Notification title
            body (str): Notification body text
            data (dict, optional): Additional data payload
            
        Returns:
            dict: Response with success status and message_id or error
        """
        if not fcm_token:
            logger.warning("FCM token is empty, cannot send notification")
            return {'success': False, 'error': 'No FCM token provided'}
        
        # Build the message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    channel_id='reminders'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default'
                    )
                )
            )
        )
        
        try:
            response = messaging.send(message)
            logger.info(f"Successfully sent FCM notification. Message ID: {response}")
            return {'success': True, 'message_id': response}
        except messaging.UnregisteredError:
            logger.error(f"FCM token is invalid or unregistered: {fcm_token}")
            return {'success': False, 'error': 'Invalid or unregistered token'}
        except Exception as e:
            logger.error(f"Failed to send FCM notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def send_batch_notifications(tokens_and_messages):
        """
        Send multiple notifications in a batch
        
        Args:
            tokens_and_messages (list): List of dicts with 'token', 'title', 'body', 'data'
            
        Returns:
            dict: Batch response with success count and failures
        """
        messages = []
        for item in tokens_and_messages:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=item['title'],
                    body=item['body'],
                ),
                data=item.get('data', {}),
                token=item['token'],
            )
            messages.append(message)
        
        try:
            response = messaging.send_all(messages)
            logger.info(f"Batch send completed. Success: {response.success_count}, Failures: {response.failure_count}")
            return {
                'success': True,
                'success_count': response.success_count,
                'failure_count': response.failure_count,
                'responses': response.responses
            }
        except Exception as e:
            logger.error(f"Failed to send batch notifications: {str(e)}")
            return {'success': False, 'error': str(e)}
