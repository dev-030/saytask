import os
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings


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
        print("⚠️ No FCM token provided")
        return None
    
    try:
        initialize_firebase()
        
        if not _firebase_initialized:
            print("❌ Firebase not initialized")
            return None
        
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    click_action='FLUTTER_NOTIFICATION_CLICK'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1
                    )
                )
            )
        )
        
        response = messaging.send(message)
        print(f"✅ FCM notification sent: {response}")
        return response
        
    except messaging.UnregisteredError:
        print("❌ FCM token is invalid or unregistered")
        return None
    except Exception as e:
        print(f"❌ Error sending FCM notification: {e}")
        return None


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
