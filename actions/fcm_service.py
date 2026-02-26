import os
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import logging
from datetime import datetime


logger = logging.getLogger(__name__)
_firebase_initialized = False


def initialize_firebase():
    global _firebase_initialized
    
    if not _firebase_initialized:
        try:
            if not firebase_admin._apps:
                cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
                
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    _firebase_initialized = True
                    print("✅ Firebase Admin SDK initialized")
                else:
                    print("⚠️ Firebase credentials file not found")
        except Exception as e:
            print(f"❌ Error initializing Firebase: {e}")


def send_push_notification(fcm_token, title, body, data=None):

    if not fcm_token:
        logger.warning("⚠️ No FCM token provided")
        print("⚠️ No FCM token provided")
        return None
    
    try:
        initialize_firebase()
        
        if not _firebase_initialized:
            logger.error("❌ Firebase not initialized")
            print("❌ Firebase not initialized")
            return {'success': False, 'error': 'Firebase not initialized', 'error_type': 'init_failed'}
        
        # Log the attempt
        logger.info(f"🚀 ATTEMPTING FCM SEND at {datetime.now()}")
        logger.info(f"   Token: {fcm_token[:20]}...")
        logger.info(f"   Title: {title}")
        logger.info(f"   Body: {body}")
        logger.info(f"   Data: {data}")
        print(f"\n{'='*60}")
        print(f"🚀 SENDING TO FIREBASE FCM SERVER")
        print(f"   Time: {datetime.now()}")
        print(f"   Token: {fcm_token[:20]}...")
        print(f"   Title: {title}")
        print(f"   Body: {body}")
        print(f"{'='*60}\n")
        
        # Construct message
        message_args = {
            'data': data or {},
            'token': fcm_token,
            'android': messaging.AndroidConfig(
                priority='high',
                ttl=0,  # Immediate delivery
            ),
            'apns': messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        content_available=True,  # Wake up app for background processing
                        sound='default' if title else None
                    )
                ),
                headers={
                    'apns-priority': '10',
                    'apns-push-type': 'background' if not title else 'alert'
                }
            )
        }

        # Only add notification block if title/body exists
        if title or body:
            message_args['notification'] = messaging.Notification(
                title=title,
                body=body
            )
            # Add click action for notifications
            message_args['android'].notification = messaging.AndroidNotification(
                sound='default',
                click_action='FLUTTER_NOTIFICATION_CLICK'
            )
        
        message = messaging.Message(**message_args)
        
        # THIS IS THE ACTUAL API CALL TO FIREBASE SERVERS
        response = messaging.send(message)
        
        # If we get here, Firebase accepted the message
        logger.info(f"✅ FIREBASE RESPONSE RECEIVED: {response}")
        logger.info(f"   Message ID: {response}")
        logger.info(f"   This confirms backend → Firebase communication successful!")
        print(f"\n{'='*60}")
        print(f"✅ SUCCESS! FIREBASE SERVER RESPONDED")
        print(f"   Message ID: {response}")
        print(f"   Time: {datetime.now()}")
        print(f"   This proves: Backend → Firebase = WORKING ✓")
        print(f"   If app doesn't receive: Check Flutter app FCM setup")
        print(f"{'='*60}\n")
        
        return {'success': True, 'message_id': response}
        
    except messaging.UnregisteredError as e:
        logger.error(f"❌ FCM token is invalid or unregistered: {e}")
        print(f"\n{'='*60}")
        print(f"❌ FIREBASE REJECTED: Invalid/Unregistered Token")
        print(f"   This means: Backend → Firebase = WORKING ✓")
        print(f"   But: Token is invalid (device uninstalled app?)")
        print(f"{'='*60}\n")
        return {'success': False, 'error': str(e), 'error_type': 'unregistered'}
    except Exception as e:
        logger.error(f"❌ Error sending FCM notification: {type(e).__name__}: {e}")
        print(f"\n{'='*60}")
        print(f"❌ ERROR COMMUNICATING WITH FIREBASE")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error: {e}")
        print(f"   Check: Firebase credentials, network, etc.")
        print(f"{'='*60}\n")
        return {'success': False, 'error': str(e), 'error_type': 'generic'}


def send_push_notification_multicast(fcm_tokens, title, body, data=None):

    if not fcm_tokens or len(fcm_tokens) == 0:
        print("⚠️ No FCM tokens provided")
        return None
    
    try:
        initialize_firebase()
        
        if not _firebase_initialized:
            print("❌ Firebase not initialized")
            return None
        
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            tokens=fcm_tokens
        )
        
        response = messaging.send_multicast(message)
        print(f"✅ Sent {response.success_count} notifications, {response.failure_count} failed")
        return response
        
    except Exception as e:
        print(f"❌ Error sending multicast FCM notification: {e}")
        return None
