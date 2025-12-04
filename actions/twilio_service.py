from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from django.conf import settings


def get_twilio_client():
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    
    if not account_sid or not auth_token:
        print("⚠️ Twilio credentials not configured")
        return None
    
    return Client(account_sid, auth_token)


def create_reminder_twiml(message):
    response = VoiceResponse()
    
    response.say(
        message,
        voice='Polly.Joanna',  
        language='en-US'
    )
    
    response.say(
        "Please check the Taskly app for more details. Thank you!",
        voice='Polly.Joanna',
        language='en-US'
    )
    
    return str(response)


def make_reminder_call(phone_number, message):

    if not phone_number:
        print("⚠️ No phone number provided")
        return None
    
    client = get_twilio_client()
    if not client:
        return None
    
    from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)
    if not from_number:
        print("⚠️ Twilio phone number not configured")
        return None
    
    try:
        twiml = create_reminder_twiml(message)
        
        call = client.calls.create(
            to=phone_number,
            from_=from_number,
            twiml=twiml,
            status_callback=None,  
            status_callback_event=['completed', 'failed']
        )
        
        print(f"✅ Twilio call initiated: {call.sid}")
        return call.sid
        
    except Exception as e:
        print(f"❌ Error making Twilio call: {e}")
        return None


def send_sms_reminder(phone_number, message):

    if not phone_number:
        print("⚠️ No phone number provided")
        return None
    
    client = get_twilio_client()
    if not client:
        return None
    
    from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)
    if not from_number:
        print("⚠️ Twilio phone number not configured")
        return None
    
    try:
        message_obj = client.messages.create(
            to=phone_number,
            from_=from_number,
            body=message
        )
        
        print(f"✅ SMS sent: {message_obj.sid}")
        return message_obj.sid
        
    except Exception as e:
        print(f"❌ Error sending SMS: {e}")
        return None
