from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import datetime
from .ai_functions import chatbot, classifier
from .note_processor import summarize_note
from .models import ChatMessage 
from .serializers import ChatMessageSerializer
from actions.models import Event, Task, Note
from .document_summarizer import summarize_document, summarize_text
import tempfile
import os





class ChatBotView(APIView):

    def post(self, request):

        user_message = request.data.get("message", "").strip()
        if not user_message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate message length (prevent extremely long inputs)
        if len(user_message) > 2000:
            return Response({"error": "Message too long (max 2000 characters)"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        history_msgs = ChatMessage.objects.filter(user=user).order_by('-created_at')[:20]
        history = []
        for msg in reversed(history_msgs):
            history.append({
                'role': msg.role,
                'timestamp': msg.created_at.isoformat(),
                'message': msg.content
            })

        ChatMessage.objects.create(
            user=user,
            role='user',
            content=user_message
        )

        try:
            result = chatbot(history, user_message)
            
            # Validate and extract response data with defaults
            response_type = result.get('response_type', 'response')
            content = result.get('content', '').strip()
            
            # Validate content is not empty
            if not content:
                content = "I understood your request but couldn't generate a proper response."
            
            # Validate response_type is valid
            valid_types = ['response', 'event', 'task', 'note']
            if response_type not in valid_types:
                response_type = 'response'

            # Store all metadata including new fields
            metadata = {
                'date': result.get('date'),
                'time': result.get('time'),
                'title': result.get('title'),
                'description': result.get('description'),
                'location_address': result.get('location_address'),
                'event_datetime': result.get('event_datetime'),
                'start_time': result.get('start_time'),
                'end_time': result.get('end_time'),
                'tags': result.get('tags', []),
                'reminders': result.get('reminders', []),
                'note_content': result.get('note_content')
            }
            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            # item_id will be injected after creation below
            chat_msg_data = dict(
                user=user,
                role='assistant',
                content=content,
                response_type=response_type,
                metadata=metadata
            )

            # Try to create structured data, but don't fail the whole request if it fails
            created_item_id = None
            try:
                created_item_id = self._create_structured_data(user, result)
            except Exception as e:
                # Log the error but don't crash - chat message is already saved
                print(f"⚠️ Failed to create structured data: {str(e)}")

            # Inject the created item id into metadata before saving chat message
            if created_item_id:
                chat_msg_data['metadata']['item_id'] = created_item_id

            chat_msg = ChatMessage.objects.create(**chat_msg_data)

            # Return backward-compatible response with additional rich fields
            response_data = {
                'message': content,
                'response_type': response_type,
                'message_id': str(chat_msg.id)
            }

            # Include the created item id so the frontend can use edit/delete APIs
            if created_item_id:
                response_data['item_id'] = created_item_id

            # Add backward-compatible simple fields
            if result.get('date'):
                response_data['date'] = result['date']
            if result.get('time'):
                response_data['time'] = result['time']

            # Add rich fields for enhanced frontend (optional)
            if result.get('title'):
                response_data['title'] = result['title']
            if result.get('description'):
                response_data['description'] = result['description']
            if result.get('location_address'):
                response_data['location'] = result['location_address']
            if result.get('event_datetime'):
                response_data['event_datetime'] = result['event_datetime']
            if result.get('start_time'):
                response_data['start_time'] = result['start_time']
            if result.get('end_time'):
                response_data['end_time'] = result['end_time']
            if result.get('tags'):
                response_data['tags'] = result['tags']
            if result.get('reminders'):
                response_data['reminders'] = result['reminders']

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"⚠️ Chatbot processing error: {str(e)}")
            return Response({
                'error': 'Chatbot processing failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

        

    def _create_structured_data(self, user, result):
        """Extract and save structured data from enhanced chatbot response"""
        from datetime import datetime, timedelta
        from .timezone_utils import parse_iso8601_to_datetime
        from actions.models import Reminder
        from django.contrib.contenttypes.models import ContentType
        
        response_type = result.get('response_type')
        
        if response_type == 'event':
            # Try ISO-8601 format first (new format)
            event_datetime = None
            if result.get('event_datetime'):
                event_datetime = parse_iso8601_to_datetime(result['event_datetime'])
            
            # Fallback to old date/time format if ISO-8601 not available
            if not event_datetime:
                parsed_date = self._parse_date_field(result.get('date'))
                parsed_time = self._parse_time_field(result.get('time'))
                
                if parsed_date and parsed_time:
                    event_datetime = datetime.combine(parsed_date, parsed_time)
                    event_datetime = timezone.make_aware(event_datetime)
                elif parsed_date:
                    event_datetime = datetime.combine(parsed_date, datetime.min.time())
                    event_datetime = timezone.make_aware(event_datetime)
            
            # Create event with all available data
            event = Event.objects.create(
                user=user,
                title=result.get('title', result.get('content', ''))[:255],
                description=result.get('description', result.get('content', '')),
                location_address=result.get('location_address', ''),
                event_datetime=event_datetime
            )

            # Create reminders if present
            if event_datetime and result.get('reminders'):
                self._create_reminders(event, result['reminders'], event_datetime)

            return str(event.id)
        
        elif response_type == 'task':
            # Try ISO-8601 format first
            start_time = None
            end_time = None
            
            if result.get('start_time'):
                start_time = parse_iso8601_to_datetime(result['start_time'])
            if result.get('end_time'):
                end_time = parse_iso8601_to_datetime(result['end_time'])
            
            # Fallback to old date/time format
            if not start_time:
                parsed_date = self._parse_date_field(result.get('date'))
                parsed_time = self._parse_time_field(result.get('time'))
                
                if parsed_date and parsed_time:
                    start_time = datetime.combine(parsed_date, parsed_time)
                    start_time = timezone.make_aware(start_time)
                elif parsed_date:
                    start_time = datetime.combine(parsed_date, datetime.min.time())
                    start_time = timezone.make_aware(start_time)
                elif parsed_time:
                    now_utc = timezone.now()
                    today_date = now_utc.date()
                    start_time = datetime.combine(today_date, parsed_time)
                    start_time = timezone.make_aware(start_time)
                    
                    if start_time <= now_utc:
                        tomorrow_date = today_date + timedelta(days=1)
                        start_time = datetime.combine(tomorrow_date, parsed_time)
                        start_time = timezone.make_aware(start_time)
            
            # Create task with all available data
            task = Task.objects.create(
                user=user,
                title=result.get('title', result.get('content', ''))[:255],
                description=result.get('description', result.get('content', '')),
                start_time=start_time,
                end_time=end_time,
                tags=result.get('tags', []),
                completed=False
            )

            # Create reminders if present and we have a start_time
            if start_time and result.get('reminders'):
                self._create_reminders(task, result['reminders'], start_time)

            return str(task.id)
        
        elif response_type == 'note':
            note = Note.objects.create(
                user=user,
                title=result.get('title', '')[:255],
                original=result.get('note_content', result.get('content', '')),
                summarized='',
                points=[]
            )

            return str(note.id)

    def _create_reminders(self, obj, reminders_data, scheduled_time):
        """Create reminder objects for an event or task"""
        from datetime import timedelta
        from actions.models import Reminder
        from django.contrib.contenttypes.models import ContentType
        
        content_type = ContentType.objects.get_for_model(obj)
        
        for reminder_data in reminders_data:
            time_before = reminder_data.get('time_before', 30)  # minutes
            reminder_types = reminder_data.get('types', ['notification'])
            
            # Calculate when to send the reminder
            reminder_time = scheduled_time - timedelta(minutes=time_before)
            
            # Only create if reminder time is in the future
            if reminder_time > timezone.now():
                Reminder.objects.create(
                    content_type=content_type,
                    object_id=obj.id,
                    time_before=time_before,
                    types=reminder_types,
                    scheduled_time=reminder_time,
                    sent=False
                )

    
    def _parse_date_field(self, date_str):
        """Parse and validate date string - supports multiple formats"""
        if not date_str or not isinstance(date_str, str):
            return None
        
        from datetime import datetime
        
        # Try multiple date formats
        date_formats = [
            '%Y-%m-%d',      # 2025-12-04
            '%Y/%m/%d',      # 2025/12/04
            '%d-%m-%Y',      # 04-12-2025
            '%d/%m/%Y',      # 04/12/2025
            '%m-%d-%Y',      # 12-04-2025 (US format)
            '%m/%d/%Y',      # 12/04/2025 (US format)
        ]
        
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str.strip(), fmt).date()
                return date_obj
            except ValueError:
                continue
        
        # If none of the formats work, return None
        return None
    
    def _parse_time_field(self, time_str):
        """Parse and validate time string - supports multiple formats"""
        if not time_str or not isinstance(time_str, str):
            return None
        
        from datetime import datetime
        
        # Try multiple time formats
        time_formats = [
            '%H:%M',         # 19:00 (24-hour)
            '%H:%M:%S',      # 19:00:00 (24-hour with seconds)
            '%I:%M %p',      # 07:00 PM (12-hour)
            '%I:%M%p',       # 07:00PM (12-hour no space)
            '%I %p',         # 7 PM (hour only)
        ]
        
        for fmt in time_formats:
            try:
                time_obj = datetime.strptime(time_str.strip(), fmt).time()
                return time_obj
            except ValueError:
                continue
        
        # If none of the formats work, return None
        return None




class ClassifyMessageView(APIView):

    def post(self, request):
        message = request.data.get("message", "").strip()
        if not message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = classifier([], message)
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'error': 'Classification failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ChatHistoryView(APIView):

    def get(self, request):
        messages = ChatMessage.objects.filter(user=request.user).order_by('created_at')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response({
            'messages': serializer.data,
            'total_count': messages.count()
        }, status=status.HTTP_200_OK)




class SummarizeNoteView(APIView):
    
    def post(self, request):
        raw_note = request.data.get("note", "").strip()
        max_length = request.data.get("max_length", "200")
        
        if not raw_note:
            return Response({
                "error": "Note content is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Use summarize_text with appropriate max_length
            result = summarize_text(raw_note, max_length)
            
            return Response({
                "summary": result["summary"],
                "original_note": raw_note,
                "original_length": result["original_length"],
                "summary_length": result["summary_length"]
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": "Failed to summarize note",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class DocumentSummarizerView(APIView):

    def post(self, request):

        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            max_length = int(request.data.get('max_length', 500))
            custom_prompt = request.data.get('custom_prompt', None)
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                    for chunk in uploaded_file.chunks():
                        tmp_file.write(chunk)
                    tmp_file_path = tmp_file.name
                
                result = summarize_document(tmp_file_path, max_length, custom_prompt)

                os.unlink(tmp_file_path)
                
                return Response({
                    "success": True,
                    "summary": result["summary"],
                    "file_name": result["file_name"],
                    "file_size": result["file_size"]
                }, status=status.HTTP_200_OK)
                
            except Exception as e:

                if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                
                return Response({
                    "error": "Failed to summarize document",
                    "details": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif 'text' in request.data:
            text = request.data.get('text', '').strip()
            max_length = int(request.data.get('max_length', 500))
            custom_prompt = request.data.get('custom_prompt', None)
            
            if not text:
                return Response({
                    "error": "Text content is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                result = summarize_text(text, max_length, custom_prompt)
                
                return Response({
                    "success": True,
                    "summary": result["summary"],
                    "original_length": result["original_length"],
                    "summary_length": result["summary_length"]
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    "error": "Failed to summarize text",
                    "details": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        else:
            return Response({
                "error": "Either 'file' or 'text' parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)