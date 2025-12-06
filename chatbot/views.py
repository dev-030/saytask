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
            date = result.get('date')
            time = result.get('time')
            
            # Validate content is not empty
            if not content:
                content = "I understood your request but couldn't generate a proper response."
            
            # Validate response_type is valid
            valid_types = ['response', 'event', 'task', 'note']
            if response_type not in valid_types:
                response_type = 'response'

            chat_msg = ChatMessage.objects.create(
                user=user,
                role='assistant',
                content=content,
                response_type=response_type,
                metadata={
                    'date': date,
                    'time': time
                } if (date or time) else {}
            )

            # Try to create structured data, but don't fail the whole request if it fails
            try:
                self._create_structured_data(user, response_type, content, date, time)
            except Exception as e:
                # Log the error but don't crash - chat message is already saved
                print(f"⚠️ Failed to create structured data: {str(e)}")

            return Response({
                'message': content,
                'response_type': response_type,
                'date': date,
                'time': time,
                'message_id': str(chat_msg.id)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Chatbot processing failed',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    def _create_structured_data(self, user, response_type, content, date, time):
        """Extract and save structured data from chatbot response"""
        
        # Skip if content is empty
        if not content or not content.strip():
            return
        
        if response_type == 'event':
            # Parse and validate the date and time fields
            parsed_date = self._parse_date_field(date)
            parsed_time = self._parse_time_field(time)
            
            # Combine into a single datetime in UTC
            event_datetime = None
            if parsed_date and parsed_time:
                # Both date and time provided
                from datetime import datetime
                event_datetime = datetime.combine(parsed_date, parsed_time)
                event_datetime = timezone.make_aware(event_datetime)
            elif parsed_date:
                # Only date provided, use midnight
                from datetime import datetime, time as dt_time
                event_datetime = datetime.combine(parsed_date, dt_time(0, 0))
                event_datetime = timezone.make_aware(event_datetime)
            elif parsed_time:
                # Only time provided - use today's date in UTC
                from datetime import datetime, date as dt_date
                now_utc = timezone.now()
                today_date = now_utc.date()
                
                # Combine with today's date
                event_datetime = datetime.combine(today_date, parsed_time)
                event_datetime = timezone.make_aware(event_datetime)
                
                # If the time has already passed today, assume tomorrow
                if event_datetime <= now_utc:
                    from datetime import timedelta
                    tomorrow_date = today_date + timedelta(days=1)
                    event_datetime = datetime.combine(tomorrow_date, parsed_time)
                    event_datetime = timezone.make_aware(event_datetime)
            
            Event.objects.create(
                user=user,
                title=content[:255],
                description=content,
                event_datetime=event_datetime
            )
        
        elif response_type == 'task':
            # Parse date/time with error handling
            parsed_date = self._parse_date_field(date)
            parsed_time = self._parse_time_field(time)
            
            start_time = None
            if parsed_date and parsed_time:
                # Both date and time are valid
                from datetime import datetime
                start_time = datetime.combine(parsed_date, parsed_time)
                start_time = timezone.make_aware(start_time)
            elif parsed_date:
                # Only date is valid
                from datetime import datetime, time as dt_time
                start_time = datetime.combine(parsed_date, dt_time(0, 0))
                start_time = timezone.make_aware(start_time)
            elif parsed_time:
                # Only time provided - use today's date in UTC
                from datetime import datetime, date as dt_date
                now_utc = timezone.now()
                today_date = now_utc.date()
                
                # Combine with today's date
                start_time = datetime.combine(today_date, parsed_time)
                start_time = timezone.make_aware(start_time)
                
                # If the time has already passed today, assume tomorrow
                if start_time <= now_utc:
                    from datetime import timedelta
                    tomorrow_date = today_date + timedelta(days=1)
                    start_time = datetime.combine(tomorrow_date, parsed_time)
                    start_time = timezone.make_aware(start_time)
            
            Task.objects.create(
                user=user,
                title=content[:255],
                description=content,
                start_time=start_time,
                completed=False
            )
        
        elif response_type == 'note':
            Note.objects.create(
                user=user,
                title='',
                original=content,
                summarized='',
                points=[]
            )

    def _combine_datetime(self, date_str, time_str):
        """Combine date and time strings into an aware datetime"""
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            combined = datetime.combine(date_obj.date(), time_obj)
            return timezone.make_aware(combined)
        except:
            return None
    
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
        
        if not raw_note:
            return Response({
                "error": "Note content is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = summarize_note(raw_note)
            
            return Response({
                "summary": result["summary"],
                "points": result["points"],
                "original_note": raw_note
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": "Failed to summarize note",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)