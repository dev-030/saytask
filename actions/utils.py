from .models import Event, Task, Note







def check_duplicate_event(user, title, date, time):

    if not title or not title.strip():
        return False, None
    
    if not date:
        return False, None 
    
    query_filter = {
        'user': user,
        'title__iexact': title.strip(),
        'date': date
    }
    
    if time is not None:
        query_filter['time'] = time
    
    exists = Event.objects.filter(**query_filter).exists()
    
    if exists:
        try:
            time_str = f" at {time.strftime('%H:%M')}" if time else ""
            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
            return True, f"Duplicate event: '{title}' already exists on {date_str}{time_str}"
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
