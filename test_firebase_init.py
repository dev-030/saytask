import os
import django
import sys

# Set up Django environment
sys.path.append('/Users/jamil/Desktop/saytask')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
import firebase_admin
from firebase_admin import credentials, messaging

def test():
    try:
        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
        print(f"Checking credentials at: {cred_path}")
        if not os.path.exists(cred_path):
            print("File does not exist!")
            return
            
        cred = credentials.Certificate(cred_path)
        
        # Check if already initialized
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully.")
        else:
            print("Firebase already initialized.")
            
        # Try a dummy message send (will fail with invalid token but check if auth works)
        message = messaging.Message(
            notification=messaging.Notification(title='test', body='test'),
            token='fcm_token_placeholder'
        )
        try:
            # messaging.send with dry_run=True still requires valid auth/JWT
            print("Attempting messaging.send(dry_run=True)...")
            messaging.send(message, dry_run=True)
            print("Auth check: Success (Unexpected for a placeholder token but means JWT signed correctly)")
        except messaging.UnregisteredError:
            print("Auth check: Success (Got UnregisteredError as expected, meaning JWT signature was valid)")
        except Exception as e:
            print(f"Auth check: Failed with error: {type(e).__name__}: {e}")

    except Exception as e:
        print(f"General error: {type(e).__name__}: {e}")

if __name__ == '__main__':
    test()
