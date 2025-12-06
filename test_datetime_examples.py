#!/usr/bin/env python
"""
Test script to demonstrate Event and Task creation with ISO 8601 UTC format.
This script shows example JSON payloads for manual API testing.
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def create_sample_event():
    """
    Create a sample event with ISO 8601 UTC datetime
    """
    # Example 1: Event 2 hours from now
    now = datetime.now(ZoneInfo("UTC"))
    event_time = now + timedelta(hours=2)
    
    event_data = {
        "title": "Doctor Appointment",
        "description": "Annual checkup",
        "location_address": "123 Main Street",
        "event_datetime": event_time.isoformat(),  # ISO 8601 format
        "reminders": [
            {
                "time_before": 10,
                "types": ["notification"]
            },
            {
                "time_before": 30,
                "types": ["notification", "call"]
            }
        ]
    }
    
    print("=" * 60)
    print("SAMPLE EVENT JSON")
    print("=" * 60)
    print(json.dumps(event_data, indent=2))
    print()
    print(f"Event Time (UTC): {event_time}")
    print(f"Reminder 1 will trigger at: {event_time - timedelta(minutes=10)}")
    print(f"Reminder 2 will trigger at: {event_time - timedelta(minutes=30)}")
    print()
    
    return event_data


def create_sample_task():
    """
    Create a sample task with ISO 8601 UTC datetime
    """
    # Example: Task starting tomorrow at 9 AM UTC
    now = datetime.now(ZoneInfo("UTC"))
    start_time = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    end_time = start_time + timedelta(hours=2)
    
    task_data = {
        "title": "Complete Project Report",
        "description": "Finish and submit Q4 report",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "tags": ["work", "priority"],
        "reminders": [
            {
                "time_before": 60,
                "types": ["notification"]
            }
        ]
    }
    
    print("=" * 60)
    print("SAMPLE TASK JSON")
    print("=" * 60)
    print(json.dumps(task_data, indent=2))
    print()
    print(f"Task Start (UTC): {start_time}")
    print(f"Task End (UTC): {end_time}")
    print(f"Reminder will trigger at: {start_time - timedelta(minutes=60)}")
    print()
    
    return task_data


def demonstrate_timezone_conversion():
    """
    Show how to convert between local time and UTC
    """
    print("=" * 60)
    print("TIMEZONE CONVERSION EXAMPLES")
    print("=" * 60)
    
    # Example: User in Bangladesh (UTC+6) wants event at 3 PM local time
    local_tz = ZoneInfo("Asia/Dhaka")
    local_time = datetime(2025, 12, 6, 15, 0, 0, tzinfo=local_tz)
    utc_time = local_time.astimezone(ZoneInfo("UTC"))
    
    print(f"User's Local Time (Dhaka): {local_time}")
    print(f"Converted to UTC: {utc_time}")
    print(f"ISO 8601 String for API: {utc_time.isoformat()}")
    print()
    
    # Example: API returns UTC, convert to user's local time
    api_response_utc = "2025-12-06T09:00:00+00:00"
    utc_datetime = datetime.fromisoformat(api_response_utc)
    local_datetime = utc_datetime.astimezone(local_tz)
    
    print(f"API Response (UTC): {api_response_utc}")
    print(f"Displayed to User (Dhaka): {local_datetime}")
    print()


def generate_curl_commands():
    """
    Generate curl commands for testing
    """
    print("=" * 60)
    print("CURL COMMANDS FOR TESTING")
    print("=" * 60)
    
    now = datetime.now(ZoneInfo("UTC"))
    event_time = now + timedelta(hours=2)
    
    event_json = json.dumps({
        "title": "Test Event",
        "event_datetime": event_time.isoformat(),
        "reminders": [{"time_before": 10, "types": ["notification"]}]
    })
    
    print("# Create Event:")
    print(f"curl -X POST http://localhost:8000/api/actions/events/ \\")
    print(f"  -H 'Authorization: Bearer YOUR_TOKEN' \\")
    print(f"  -H 'Content-Type: application/json' \\")
    print(f"  -d '{event_json}'")
    print()
    
    task_time = now + timedelta(days=1)
    task_json = json.dumps({
        "title": "Test Task",
        "start_time": task_time.isoformat(),
        "reminders": [{"time_before": 30, "types": ["notification"]}]
    })
    
    print("# Create Task:")
    print(f"curl -X POST http://localhost:8000/api/actions/tasks/ \\")
    print(f"  -H 'Authorization: Bearer YOUR_TOKEN' \\")
    print(f"  -H 'Content-Type: application/json' \\")
    print(f"  -d '{task_json}'")
    print()


if __name__ == "__main__":
    print("\n")
    print("*" * 60)
    print("ISO 8601 UTC DateTime Format - Test Examples")
    print("*" * 60)
    print("\n")
    
    create_sample_event()
    create_sample_task()
    demonstrate_timezone_conversion()
    generate_curl_commands()
    
    print("=" * 60)
    print("IMPORTANT NOTES")
    print("=" * 60)
    print("1. Always send datetime in UTC to the API")
    print("2. Use ISO 8601 format: YYYY-MM-DDTHH:MM:SS+00:00 or YYYY-MM-DDTHH:MM:SSZ")
    print("3. Convert user's local time to UTC before sending")
    print("4. Convert API response (UTC) to user's local time for display")
    print("5. Django will automatically parse ISO 8601 strings")
    print("=" * 60)
