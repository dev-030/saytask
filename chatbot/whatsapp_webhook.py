from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from datetime import datetime
import os
import logging

from authentication.models import UserAccount
from actions.models import Event, Task, Note, Reminder
from django.contrib.contenttypes.models import ContentType
from .ai_functions import classifier
from .timezone_utils import parse_iso8601_to_datetime
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def whatsapp_chatbot(message: str) -> dict:
    """
    WhatsApp-specific chatbot that provides conversational responses
    and validates required fields before creating entries.
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    import json
    
    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        openai_api_key=api_key
    )
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")
    
    system_prompt = f"""You are SayTask, a friendly AI assistant that helps users manage their tasks, events, and notes via WhatsApp.

Current date: {current_date}
Current time: {current_time}

Your job is to analyze the user's message and respond conversationally.

RESPONSE TYPES:

1. If user wants to create an EVENT (meeting, appointment, scheduled activity):
{{
  "type": "event",
  "response": "Conversational confirmation or request for missing info",
  "ready": true/false,
  "title": "Event title",
  "description": "Description",
  "location_address": "Location (empty string if not mentioned)",
  "event_datetime": "YYYY-MM-DDTHH:MM:SSZ (UTC format)",
  "needs_reminder_confirmation": true/false
}}

2. If user wants to create a TASK (todo, action item):
{{
  "type": "task",
  "response": "Conversational confirmation or request for missing info",
  "ready": true/false,
  "title": "Task title",
  "description": "Description",
  "start_time": "YYYY-MM-DDTHH:MM:SSZ",
  "end_time": "YYYY-MM-DDTHH:MM:SSZ",
  "tags": ["tag1", "tag2"],
  "needs_reminder_confirmation": true/false
}}

3. If user wants to create a NOTE:
{{
  "type": "note",
  "response": "Conversational confirmation",
  "ready": true,
  "title": "Note title",
  "content": "Note content"
}}

4. If user is just chatting or asking questions:
{{
  "type": "response",
  "response": "Your helpful response",
  "ready": true
}}

IMPORTANT RULES:
- Set "ready": true ONLY if all required information is provided
- Set "ready": false if date/time or other critical info is missing
- When ready=false, ask for the missing information in "response"
- For events: REQUIRED fields are title, event_datetime
- For tasks: REQUIRED fields are title, end_time (deadline)
- Convert times to UTC (assume user is in UTC+6/Asia/Dhaka timezone)
- Set "needs_reminder_confirmation": true if user hasn't mentioned reminders
- Be conversational and friendly
- Keep responses concise for WhatsApp

EXAMPLES:
User: "Meeting tomorrow at 3pm"
Response: {{"type": "event", "ready": false, "response": "I can set up a meeting for tomorrow at 3pm. What's the meeting about and where will it be?"}}

User: "Team meeting about Q4 review at office"
Response: {{"type": "event", "ready": true, "title": "Team meeting", "description": "Q4 review", "location_address": "office", "event_datetime": "...", "response": "Got it! Set up team meeting for Q4 review at the office tomorrow at 3pm. Would you like me to set a reminder?"}}

User: "Yes, remind me 30 minutes before"
Response: {{"type": "reminder_confirmation", "response": "Perfect! I'll remind you 30 minutes before the meeting.", "time_before": 30}}
"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=message)
    ]
    
    response = llm.invoke(messages)
    
    try:
        result = json.loads(response.content.strip())
        
        if isinstance(result, list):
            result = result[0] if result else {}
        
        if not isinstance(result, dict):
            raise ValueError("Invalid response format")
        
        return result
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"WhatsApp chatbot parsing error: {e}")
        return {
            "type": "response",
            "response": "I had trouble understanding that. Could you try rephrasing?",
            "ready": True
        }


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(APIView):
    """
    Webhook endpoint for Twilio WhatsApp messages.
    Receives messages, processes them with AI, and sends responses.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Handle incoming WhatsApp messages from Twilio"""
        
        # Extract Twilio webhook data
        from_number = request.POST.get('From', '').replace('whatsapp:', '')
        message_body = request.POST.get('Body', '').strip()
        to_number = request.POST.get('To', '')
        
        print(f"=== WHATSAPP WEBHOOK DEBUG ===")
        print(f"From: {from_number}")
        print(f"Message: {message_body}")
        print(f"To: {to_number}")
        logger.info(f"WhatsApp message from {from_number}: {message_body}")
        
        if not message_body:
            print("ERROR: No message body")
            return self._send_twilio_response("Please send a message!")
        
        # Validate message length
        if len(message_body) > 2000:
            print("ERROR: Message too long")
            return self._send_twilio_response(
                "Message is too long. Please keep it under 2000 characters."
            )
        
        # # Find user by phone number
        print(f"Looking up user by phone: {from_number}")
        user = self._get_user_by_phone(from_number)
        
        if not user:
            print(f"ERROR: No user found for phone {from_number}")
            return self._send_twilio_response(
                "You don't have a phone number added in the app or you aren't registered yet. "
                "Please register and add your phone number in the app first."
            )
        
        print(f"✓ User found: {user.email}")
        
        # Check if WhatsApp bot is enabled for this user
        try:
            if not user.profile.whatsapp_bot_enabled:
                print(f"WhatsApp bot disabled for user: {user.email}")
                return self._send_twilio_response(
                    "The WhatsApp assistant is currently disabled for your account. "
                    "Please enable it in your app settings to continue using this feature."
                )
        except Exception as e:
            # If profile doesn't exist or error occurs, allow access
            print(f"Warning: Could not check whatsapp_bot_enabled: {e}")
        
        # Process message with AI
        try:
            print("Processing with AI...")
            result = whatsapp_chatbot(message_body)
            print(f"AI Result: {result}")
            
            response_type = result.get('type', 'response')
            is_ready = result.get('ready', False)
            ai_response = result.get('response', 'I processed your request.')
            
            print(f"Type: {response_type}, Ready: {is_ready}")
            print(f"AI Response: {ai_response}")
            
            # If data is ready, create the database entry
            if is_ready and response_type in ['event', 'task', 'note']:
                print(f"Creating {response_type} in database...")
                self._create_structured_data(user, result)
                print(f"✓ {response_type.capitalize()} created")
            
            print(f"Sending response: {ai_response}")
            return self._send_twilio_response(ai_response)
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error processing WhatsApp message: {str(e)}")
            return self._send_twilio_response(
                "Sorry, I encountered an error processing your request. Please try again."
            )
    
    def _get_user_by_phone(self, phone_number):
        """Find user by phone number, trying multiple formats in both UserAccount and UserProfile"""
        from authentication.models import UserProfile
        
        if not phone_number:
            return None
        
        # Clean phone number (remove spaces, dashes, etc.)
        cleaned = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        print(f"Searching for phone: {phone_number} (cleaned: {cleaned})")
        
        # Try UserAccount.phone_number first (exact match)
        user = UserAccount.objects.filter(phone_number=phone_number).first()
        if user:
            print(f"Found in UserAccount (exact): {user.email}")
            return user
        
        # Try UserAccount.phone_number (cleaned)
        user = UserAccount.objects.filter(phone_number=cleaned).first()
        if user:
            print(f"Found in UserAccount (cleaned): {user.email}")
            return user
        
        # Try UserProfile.phone_number (exact match)
        profile = UserProfile.objects.filter(phone_number=phone_number).first()
        if profile:
            print(f"Found in UserProfile (exact): {profile.user.email}")
            return profile.user
        
        # Try UserProfile.phone_number (cleaned)
        profile = UserProfile.objects.filter(phone_number=cleaned).first()
        if profile:
            print(f"Found in UserProfile (cleaned): {profile.user.email}")
            return profile.user
        
        # Try without country code (last 10 digits) in UserAccount
        if len(cleaned) > 10:
            last_digits = cleaned[-10:]
            user = UserAccount.objects.filter(phone_number__endswith=last_digits).first()
            if user:
                print(f"Found in UserAccount (last digits): {user.email}")
                return user
            
            # Try in UserProfile too
            profile = UserProfile.objects.filter(phone_number__endswith=last_digits).first()
            if profile:
                print(f"Found in UserProfile (last digits): {profile.user.email}")
                return profile.user
        
        print("No user found with this phone number")
        return None
    
    def _create_structured_data(self, user, result):
        """Create Event, Task, or Note in database"""
        response_type = result.get('type')
        
        try:
            if response_type == 'event':
                event_datetime = None
                if result.get('event_datetime'):
                    event_datetime = parse_iso8601_to_datetime(result['event_datetime'])
                
                event = Event.objects.create(
                    user=user,
                    title=result.get('title', '')[:255],
                    description=result.get('description', ''),
                    location_address=result.get('location_address', ''),
                    event_datetime=event_datetime
                )
                
                # Create reminder if confirmed
                if event_datetime and result.get('time_before'):
                    self._create_reminder(event, result['time_before'], event_datetime)
                
                logger.info(f"Created event: {event.title} for user {user.email}")
            
            elif response_type == 'task':
                start_time = None
                end_time = None
                
                if result.get('start_time'):
                    start_time = parse_iso8601_to_datetime(result['start_time'])
                if result.get('end_time'):
                    end_time = parse_iso8601_to_datetime(result['end_time'])
                
                task = Task.objects.create(
                    user=user,
                    title=result.get('title', '')[:255],
                    description=result.get('description', ''),
                    start_time=start_time,
                    end_time=end_time,
                    tags=result.get('tags', []),
                    completed=False
                )
                
                # Create reminder if confirmed
                if end_time and result.get('time_before'):
                    self._create_reminder(task, result['time_before'], end_time)
                
                logger.info(f"Created task: {task.title} for user {user.email}")
            
            elif response_type == 'note':
                note = Note.objects.create(
                    user=user,
                    title=result.get('title', '')[:255],
                    original=result.get('content', ''),
                    summarized='',
                    points=[]
                )
                
                logger.info(f"Created note: {note.title} for user {user.email}")
        
        except Exception as e:
            logger.error(f"Error creating structured data: {str(e)}")
            raise
    
    def _create_reminder(self, obj, time_before, scheduled_time):
        """Create a reminder for an event or task"""
        from datetime import timedelta
        
        content_type = ContentType.objects.get_for_model(obj)
        reminder_time = scheduled_time - timedelta(minutes=time_before)
        
        if reminder_time > timezone.now():
            Reminder.objects.create(
                content_type=content_type,
                object_id=obj.id,
                time_before=time_before,
                types=['notification'],
                scheduled_time=reminder_time,
                sent=False
            )
            logger.info(f"Created reminder {time_before} minutes before")
    
    def _send_twilio_response(self, message):
        """Send response back via Twilio WhatsApp"""
        print(f">>> Generating TwiML response: {message}")
        twiml_response = MessagingResponse()
        twiml_response.message(message)
        
        twiml_str = str(twiml_response)
        print(f">>> TwiML XML: {twiml_str}")
        
        return HttpResponse(
            twiml_str,
            content_type='text/xml',
            status=status.HTTP_200_OK
        )

