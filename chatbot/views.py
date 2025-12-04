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
            response_type = result.get('response_type', 'response')
            content = result.get('content', '')
            date = result.get('date')
            time = result.get('time')

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

            self._create_structured_data(user, response_type, content, date, time)

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
        
        if response_type == 'event':
            # Parse and validate the time field
            parsed_time = self._parse_time_field(time)
            
            Event.objects.create(
                user=user,
                title=content[:255],
                description=content,
                date=date,
                time=parsed_time
            )
        
        elif response_type == 'task':
            start_time = None
            if date and time:
                start_time = self._combine_datetime(date, time)
            elif date:
                from datetime import datetime
                start_time = datetime.strptime(date, '%Y-%m-%d')
            
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
    
    def _parse_time_field(self, time_str):
        """Parse and validate time string to HH:MM format"""
        if not time_str:
            return None
        
        try:
            # Try to parse as HH:MM format
            from datetime import datetime
            time_obj = datetime.strptime(time_str, '%H:%M').time()
            return time_obj
        except ValueError:
            # If it's not a valid time format (e.g., "morning", "afternoon"), return None
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