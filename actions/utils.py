from .models import Event, Task, Note







def check_duplicate_event(user, title, event_datetime):
    
    if not title or not title.strip():
        return False, None
    
    if not event_datetime:
        return False, None 
    
    query_filter = {
        'user': user,
        'title__iexact': title.strip(),
        'event_datetime': event_datetime
    }
    
    exists = Event.objects.filter(**query_filter).exists()
    
    if exists:
        try:
            # Format datetime for user-friendly message
            from django.utils import timezone
            if timezone.is_aware(event_datetime):
                dt_str = event_datetime.strftime('%Y-%m-%d at %H:%M UTC')
            else:
                dt_str = event_datetime.strftime('%Y-%m-%d at %H:%M')
            return True, f"Duplicate event: '{title}' already exists on {dt_str}"
        except:
            return True, f"Duplicate event: '{title}' already exists"
    
    return False, None





def check_duplicate_task(user, title, start_time):

    if not title or not title.strip():
        return False, None
    
    query_filter = {
        'user': user,
        'title__iexact': title.strip()
    }
    
    if start_time is not None:
        query_filter['start_time'] = start_time
    
    exists = Task.objects.filter(**query_filter).exists()
    
    if exists:
        try:
            if start_time:
                time_str = f" starting at {start_time.strftime('%Y-%m-%d %H:%M')}"
            else:
                time_str = ""
            return True, f"Duplicate task: '{title}'{time_str} already exists"
        except:
            return True, f"Duplicate task: '{title}' already exists"
    
    return False, None





def check_duplicate_note(user, original, date):
    
    if not original or not original.strip():
        return False, None
    
    try:
        exists = Note.objects.filter(
            user=user,
            original__iexact=original.strip()
        ).exists()
        
        if exists:
            return True, f"Duplicate note with this content already exists"
        
        return False, None
    except Exception as e:
        print(f"Error in duplicate note check: {e}")
        return False, None
