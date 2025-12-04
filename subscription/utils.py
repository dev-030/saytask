from django.utils import timezone
from datetime import timedelta
from .models import UsageTracking





def get_period_bounds(period_type):

    now = timezone.now()
    
    if period_type == 'minute': 
        start = now.replace(second=0, microsecond=0)
        end = start + timedelta(minutes=1)
        
    elif period_type == 'hour':
        start = now.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        
    elif period_type == 'day':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
    elif period_type == 'week':
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=7)
        
    elif period_type == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    
    return start, end



def check_usage_limit(user, item_type):
    try:
        subscription = user.subscriptions
        plan = subscription.plan
        features = plan.features or {}
        
        limit_config = features.get(item_type, {})
        limit = limit_config.get('limit') 
        period = limit_config.get('period', 'week')
        
    except Exception as e:
        return False, f"Unable to verify subscription: {str(e)}"
    
    if limit is None:
        return True, None
    
    period_start, period_end = get_period_bounds(period)
    
    tracker, created = UsageTracking.objects.get_or_create(
        user=user,
        item_type=item_type,
        period_type=period,
        period_start=period_start,
        defaults={'period_end': period_end, 'count': 0}
    )
    
    if tracker.count >= limit:
        period_label = {
            'minute': 'minute',
            'hour': 'hour',
            'day': 'day',
            'week': 'week',
            'month': 'month'
        }.get(period, period)
        
        return False, f"Limit of {limit} {item_type}s per {period_label} reached"
    
    return True, None




def increment_usage(user, item_type):

    try:
        subscription = user.subscriptions
        plan = subscription.plan
        features = plan.features or {}
        
        limit_config = features.get(item_type, {})
        period = limit_config.get('period', 'week')
        
        period_start, period_end = get_period_bounds(period)
        
        tracker, created = UsageTracking.objects.get_or_create(
            user=user,
            item_type=item_type,
            period_type=period,
            period_start=period_start,
            defaults={'period_end': period_end, 'count': 0}
        )
        
        tracker.count += 1
        tracker.save()
        
    except Exception as e:
        print(f"⚠️ Failed to increment usage for {user}: {e}")
        pass




def get_usage_info(user, item_type):

    try:
        subscription = user.subscriptions
        plan = subscription.plan
        features = plan.features or {}
        
        limit_config = features.get(item_type, {})
        limit = limit_config.get('limit')
        period = limit_config.get('period', 'week')
        
        period_start, period_end = get_period_bounds(period)
        
        try:
            tracker = UsageTracking.objects.get(
                user=user,
                item_type=item_type,
                period_type=period,
                period_start=period_start
            )
            used = tracker.count
        except UsageTracking.DoesNotExist:
            used = 0
        
        if limit is None:
            remaining = None  
        else:
            remaining = max(0, limit - used)
        
        return {
            'used': used,
            'limit': limit,
            'remaining': remaining,
            'period': period
        }
        
    except Exception:
        return {
            'used': 0,
            'limit': 0,
            'remaining': 0,
            'period': 'week'
        }
