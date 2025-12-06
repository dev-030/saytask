from celery import shared_task
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import Reminder, Event, Task
from authentication.models import UserProfile
from .fcm_service import send_push_notification
from .twilio_service import make_reminder_call
from datetime import timedelta




@shared_task(bind=True, max_retries=3)
def send_fcm_notification(self, user_id, title, body, data=None):

    try:
        profile = UserProfile.objects.select_related('user').get(user_id=user_id)
        
        if not profile.fcm_token:
            print(f"⚠️ User {user_id} has no FCM token")
            return {'status': 'no_token'}
        
        result = send_push_notification(
            fcm_token=profile.fcm_token,
            title=title,
            body=body,
            data=data
        )
        
        if result is None:
            profile.fcm_token = None
            profile.fcm_token_updated_at = None
            profile.save()
            return {'status': 'invalid_token'}
        
        return {'status': 'sent', 'message_id': result}
        
    except UserProfile.DoesNotExist:
        print(f"❌ UserProfile not found for user {user_id}")
        return {'status': 'user_not_found'}
    except Exception as e:
        print(f"❌ Error in send_fcm_notification: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_twilio_call_task(self, user_id, message):
    try:
        profile = UserProfile.objects.select_related('user').get(user_id=user_id)

        print('triggered 🔴', profile)
        
        phone = getattr(profile.user, 'phone_number', None)
        if not phone:
            print(f"⚠️ User {user_id} has no phone number")
            return {'status': 'no_phone'}
        
        call_sid = make_reminder_call(
            phone_number=phone,
            message=message
        )
        
        if call_sid:
            return {'status': 'called', 'call_sid': call_sid}
        else:
            return {'status': 'failed'}
        
    except UserProfile.DoesNotExist:
        print(f"❌ UserProfile not found for user {user_id}")
        return {'status': 'user_not_found'}
    except Exception as e:
        print(f"❌ Error in send_twilio_call_task: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def check_and_send_reminders():
    print('celery breat triggered 🔴')

    now = timezone.now()

    due_reminders = Reminder.objects.filter(
        sent=False,
        scheduled_time__lte=now
    ).select_related('content_type').prefetch_related('content_object')

    sent_count = 0
    failed_count = 0
    
    for reminder in due_reminders:

        try:
            obj = reminder.content_object
            if obj is None:
                print(f"⚠️ Reminder {reminder.id} has no content object")
                reminder.sent = True
                reminder.sent_at = now
                reminder.save()
                continue
            
            user = obj.user
            user_id = user.id
            
            obj_type = "Event" if isinstance(obj, Event) else "Task"
            obj_title = obj.title
            
            # Get event time based on object type
            if isinstance(obj, Event) and obj.event_datetime:
                event_time = obj.event_datetime
            elif hasattr(obj, 'scheduled_start') and obj.scheduled_start:
                event_time = obj.scheduled_start
            else:
                event_time = None
            
            if event_time:
                time_diff = event_time - now
                hours = int(time_diff.total_seconds() / 3600)
                minutes = int((time_diff.total_seconds() % 3600) / 60)
                
                if hours > 0:
                    time_str = f"in {hours} hour{'s' if hours > 1 else ''}"
                    if minutes > 0:
                        time_str += f" and {minutes} minute{'s' if minutes > 1 else ''}"
                elif minutes > 0:
                    time_str = f"in {minutes} minute{'s' if minutes > 1 else ''}"
                else:
                    time_str = "now"
            else:
                time_str = "soon"
            
            notification_title = f"{obj_type} Reminder"
            notification_body = f"{obj_title} {time_str}"           
            
            call_message = f"Hello! You have an upcoming {obj_type.lower()}: {obj_title} {time_str}."
            
            types = reminder.types if reminder.types else []

            if 'notification' in types or 'both' in types:
                send_fcm_notification.delay(
                    user_id=user_id,
                    title=notification_title,
                    body=notification_body,
                    data={
                        'type': obj_type.lower(),
                        'id': str(obj.id),
                        'title': obj_title
                    }
                )
            
            if 'call' in types or 'both' in types:
                send_twilio_call_task.delay(
                    user_id=user_id,
                    message=call_message
                )
            
            reminder.sent = True
            reminder.sent_at = now
            reminder.save()
            
            sent_count += 1
            print(f"✅ Sent reminder for {obj_type}: {obj_title}")
            
        except Exception as e:
            print(f"❌ Error processing reminder {reminder.id}: {e}")
            failed_count += 1
            continue
    
    if sent_count > 0 or failed_count > 0:
        print(f"📊 Reminders processed: {sent_count} sent, {failed_count} failed")
    
    return {
        'sent': sent_count,
        'failed': failed_count,
        'checked_at': now.isoformat()
    }
