from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Event, Task, Note
from .serializers import EventSerializer, TaskSerializer, NoteSerializer
from subscription.utils import check_usage_limit, increment_usage
from actions.utils import check_duplicate_note




class NoteListView(APIView):
    
    def get(self, request):
        notes = Note.objects.filter(user=request.user)
        serializer = NoteSerializer(notes, many=True)
        return Response({'notes': serializer.data})

    def post(self, request):
        from actions.utils import check_duplicate_note
        from subscription.utils import check_usage_limit, increment_usage
        
        # Check usage limits
        can_create, error_msg = check_usage_limit(request.user, 'note')
        if not can_create:
            return Response({'error': error_msg}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = NoteSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for duplicates
        is_duplicate, dup_msg = check_duplicate_note(
            request.user,
            serializer.validated_data.get('original'),
            None
        )
        if is_duplicate:
            return Response({'error': dup_msg}, status=status.HTTP_409_CONFLICT)
        
        serializer.save()
        increment_usage(request.user, 'note')
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NoteDetailView(APIView):

    def get_object(self, pk, user):
        try:
            return Note.objects.get(pk=pk, user=user)
        except Note.DoesNotExist:
            return None

    def get(self, request, pk):
        note = self.get_object(pk, request.user)
        if not note:
            return Response({"error": "Note not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = NoteSerializer(note)
        return Response(serializer.data)

    def put(self, request, pk):
        from subscription.utils import check_usage_limit, increment_usage
        
        note = self.get_object(pk, request.user)
        if not note:
            return Response({"error": "Note not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check edit limits
        can_edit, error_msg = check_usage_limit(request.user, 'edit')
        if not can_edit:
            return Response({'error': error_msg}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = NoteSerializer(note, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            increment_usage(request.user, 'edit')
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        note = self.get_object(pk, request.user)
        if not note:
            return Response({"error": "Note not found"}, status=status.HTTP_404_NOT_FOUND)
        
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)





class EventListView(APIView):    

    def get(self, request):
        events = Event.objects.filter(user=request.user)
        serializer = EventSerializer(events, many=True)
        return Response({'events': serializer.data})

    def post(self, request):
        from actions.utils import check_duplicate_event
        from subscription.utils import check_usage_limit, increment_usage
        
        # Check usage limits
        can_create, error_msg = check_usage_limit(request.user, 'event')
        if not can_create:
            return Response({'error': error_msg}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = EventSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for duplicates
        is_duplicate, dup_msg = check_duplicate_event(
            request.user,
            serializer.validated_data.get('title'),
            serializer.validated_data.get('event_datetime')
        )
        if is_duplicate:
            return Response({'error': dup_msg}, status=status.HTTP_409_CONFLICT)
        
        serializer.save()
        increment_usage(request.user, 'event')
        return Response(serializer.data, status=status.HTTP_201_CREATED)




class EventDetailView(APIView):    

    def get_object(self, pk, user):
        try:
            return Event.objects.get(pk=pk, user=user)
        except Event.DoesNotExist:
            return None

    def get(self, request, pk):
        event = self.get_object(pk, request.user)
        if not event:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = EventSerializer(event)
        return Response(serializer.data)

    def put(self, request, pk):
        from subscription.utils import check_usage_limit, increment_usage
        
        event = self.get_object(pk, request.user)
        if not event:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check edit limits
        can_edit, error_msg = check_usage_limit(request.user, 'edit')
        if not can_edit:
            return Response({'error': error_msg}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = EventSerializer(event, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            increment_usage(request.user, 'edit')
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        event = self.get_object(pk, request.user)
        if not event:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
        
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)





class TaskListView(APIView):    

    def get(self, request):
        tasks = Task.objects.filter(user=request.user)
        serializer = TaskSerializer(tasks, many=True)
        return Response({'tasks': serializer.data})

    def post(self, request):
        from actions.utils import check_duplicate_task
        from subscription.utils import check_usage_limit, increment_usage
        
        # Check usage limits
        can_create, error_msg = check_usage_limit(request.user, 'task')
        if not can_create:
            return Response({'error': error_msg}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = TaskSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for duplicates
        is_duplicate, dup_msg = check_duplicate_task(
            request.user,
            serializer.validated_data.get('title'),
            serializer.validated_data.get('start_time')
        )
        if is_duplicate:
            return Response({'error': dup_msg}, status=status.HTTP_409_CONFLICT)
        
        serializer.save()
        increment_usage(request.user, 'task')
        return Response(serializer.data, status=status.HTTP_201_CREATED)




class TaskDetailView(APIView):
    
    def get_object(self, pk, user):
        try:
            return Task.objects.get(pk=pk, user=user)
        except Task.DoesNotExist:
            return None

    def get(self, request, pk):
        task = self.get_object(pk, request.user)
        if not task:
            return Response({"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TaskSerializer(task)
        return Response(serializer.data)

    def put(self, request, pk):
        from subscription.utils import check_usage_limit, increment_usage
        
        task = self.get_object(pk, request.user)
        if not task:
            return Response({"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check edit limits
        can_edit, error_msg = check_usage_limit(request.user, 'edit')
        if not can_edit:
            return Response({'error': error_msg}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = TaskSerializer(task, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            increment_usage(request.user, 'edit')
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        task = self.get_object(pk, request.user)
        if not task:
            return Response({"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND)
        
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MakeCallView(APIView):
    """
    Temporary view for testing In-App VoIP calls manually (via FCM).
    No authentication required for testing purposes.
    """
    permission_classes = []

    def post(self, request):
        from actions.fcm_service import send_push_notification
        import json
        import uuid
        
        token = request.data.get('token')
        message = request.data.get('message', 'This is a test call from SayTask AI.')
        
        if not token:
            return Response({
                'error': 'token is required',
                'message': 'Please provide an FCM device token'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"📞 Initiating manual FCM VoIP call to token: {token[:20]}...")
        
        # Construct VOIP payload
        call_uuid = str(uuid.uuid4())
        voip_payload = {
            "type": "voip_call",
            "uuid": call_uuid,
            "caller_name": "SayTask AI (Test)",
            "handle": "SayTask",
            "app_name": "SayTask",
            "has_video": "false",
            "duration": "30000",
            "extra": json.dumps({
                "message_to_speak": message
            })
        }
        
        # Trigger notification synchronously for immediate feedback
        result = send_push_notification(
            fcm_token=token,
            title=None,
            body=None,
            data=voip_payload
        )
        
        if result and result.get('success'):
            return Response({
                'status': 'success',
                'call_uuid': call_uuid,
                'message_id': result.get('message_id'),
                'message': 'FCM VoIP notification sent successfully'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'error': result.get('error') if result else 'Failed to send VoIP notification',
                'message': '❌ Firebase rejected the VoIP notification'
            }, status=status.HTTP_400_BAD_REQUEST)


class TestFCMView(APIView):
    """
    Test endpoint to verify Firebase FCM communication.
    Use this to confirm backend → Firebase is working.
    """
    permission_classes = []

    def post(self, request):
        
        # Get FCM token from request data since user is not authenticated
        fcm_token = request.data.get('token')
        
        if not fcm_token:
            return Response({
                'error': 'token is required',
                'message': 'Please provide an FCM device token in the request body'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"\n{'='*60}")
        print(f"🧪 TESTING FCM NOTIFICATION")
        print(f"   Token: {fcm_token[:20]}...")
        print(f"{'='*60}\n")
        
        # Send test notification synchronously to get immediate feedback
        from actions.fcm_service import send_push_notification
        
        result = send_push_notification(
            fcm_token=fcm_token,
            title="🧪 Test Notification",
            body="If you see this, Firebase communication is working!",
            data={
                'type': 'test',
                'timestamp': str(timezone.now())
            }
        )
        
        if result and result.get('success'):
            return Response({
                'status': 'success',
                'message': 'Test notification sent to Firebase',
                'firebase_response': {
                    'message_id': result['message_id'],
                    'timestamp': timezone.now().isoformat(),
                },
                'verification': '✅ SUCCESS! Firebase accepted the message. If the app hasn\'t received it, check the Flutter app setup.'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'error',
                'message': 'Firebase rejected the request',
                'error_details': result.get('error'),
                'error_type': result.get('error_type'),
                'troubleshooting': 'Check Firebase credentials or if the device token is still valid.'
            }, status=status.HTTP_400_BAD_REQUEST)


class HealthCheckView(APIView):
    """
    Simple health check endpoint - no authentication required
    """
    permission_classes = []
    
    def get(self, request):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class SendNotificationView(APIView):
    """
    Direct FCM notification endpoint - send notification to any FCM token
    No authentication required for testing purposes
    """
    permission_classes = []
    
    def post(self, request):
        from actions.fcm_service import send_push_notification
        
        token = request.data.get('token')
        title = request.data.get('title')
        body = request.data.get('body')
        
        # Validate required fields
        if not token:
            return Response({
                'error': 'token is required',
                'message': 'Please provide an FCM device token'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not title:
            return Response({
                'error': 'title is required',
                'message': 'Please provide a notification title'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not body:
            return Response({
                'error': 'body is required',
                'message': 'Please provide a notification body'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Send notification via FCM
            result = send_push_notification(
                fcm_token=token,
                title=title,
                body=body,
                data=request.data.get('data', {})
            )
            
            if result and result.get('success'):
                return Response({
                    'success': True,
                    'message_id': result.get('message_id'),
                    'details': {
                        'token': token[:20] + '...',
                        'title': title,
                        'body': body
                    },
                    'message': '✅ Notification sent successfully to Firebase'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': result.get('error') if result else 'Failed to send notification',
                    'message': '❌ Firebase rejected the notification (invalid token or Firebase not initialized)'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': f'❌ Error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
