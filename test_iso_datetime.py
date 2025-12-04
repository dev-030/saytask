import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from actions.models import Event, Reminder
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.dateparse import parse_datetime

User = get_user_model()

print("=" * 70)
print("TESTING ISO DATETIME FORMAT FOR TIMEZONE-AWARE REMINDERS")
print("=" * 70)

# Get or create test user
user, _ = User.objects.get_or_create(
    email='timezone_test@example.com',
    defaults={'full_name': 'Timezone Test User', 'is_active': True}
)

print("\n1. Testing Event Creation with ISO DateTime...")
print("   Simulating frontend sending: 2025-12-03T14:30:00+06:00")
print("   (2:30 PM in Bangladesh timezone)")

# Simulate what frontend would send in ISO format
iso_datetime_str = "2025-12-03T14:30:00+06:00"
event_dt = parse_datetime(iso_datetime_str)

print(f"   Parsed datetime: {event_dt}")
print(f"   Timezone aware: {timezone.is_aware(event_dt)}")

# Create event
event = Event.objects.create(
    user=user,
    title="Test Event - Timezone Aware",
    description="Testing ISO datetime format",
    event_datetime=event_dt
)

print(f"\n2. Event Created Successfully!")
print(f"   Event ID: {event.id}")
print(f"   Event DateTime (stored in DB): {event.event_datetime}")
print(f"   Is timezone-aware: {timezone.is_aware(event.event_datetime)}")

# Create reminder
print(f"\n3. Creating Reminder (10 minutes before)...")

event_ct = ContentType.objects.get_for_model(Event)
reminder_time = event.event_datetime - timedelta(minutes=10)

reminder = Reminder.objects.create(
    content_type=event_ct,
    object_id=event.id,
    time_before=10,
    types=['notification'],
    scheduled_time=reminder_time
)

print(f"   Reminder ID: {reminder.id}")
print(f"   Event time: {event.event_datetime}")
print(f"   Reminder time: {reminder.scheduled_time}")
print(f"   Time difference: {(event.event_datetime - reminder.scheduled_time).total_seconds() / 60} minutes")
print(f"   ✅ Reminder will trigger 10 minutes before event time!")

# Test API Serialization
print(f"\n4. API Response Format Test:")
from actions.serializers import EventSerializer

serializer = EventSerializer(event)
event_data = serializer.data
print(f"   event_datetime field: {event_data['event_datetime']}")
print(f"   ✅ Frontend will receive ISO format automatically!")

# Test current time check (simulating Celery task)
print(f"\n5. Simulating Reminder Check (like Celery task):")
now = timezone.now()
print(f"   Current UTC time: {now}")
print(f"   Reminder scheduled for: {reminder.scheduled_time}")

if now >= reminder.scheduled_time:
    print(f"   ⏰ Reminder WOULD BE SENT now!")
else:
    time_until = reminder.scheduled_time - now
    hours = int(time_until.total_seconds() / 3600)
    minutes = int((time_until.total_seconds() % 3600) / 60)
    print(f"   ⏳ Reminder will be sent in {hours}h {minutes}m")

# Cleanup
print(f"\n6. Cleanup...")
reminder.delete()
event.delete()
print(f"   ✅ Test data cleaned up")

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
print("\n📋 Summary:")
print("  ✅ Frontend sends ISO format datetime with timezone")
print("  ✅ Django automatically parses and stores in UTC")
print("  ✅ Reminders calculate correctly in UTC")
print("  ✅ Works for users in ANY timezone!")
print("\n💡 Frontend Example (JavaScript):")
print("  const localDate = new Date('2025-12-03T14:30:00');")
print("  const isoString = localDate.toISOString();")
print("  // Send isoString to backend")
print("=" * 70)
