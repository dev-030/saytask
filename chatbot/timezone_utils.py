"""
Timezone utility functions for handling ISO-8601 UTC datetime conversions.
All internal storage uses UTC, with helpers for local timezone display.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional


def get_current_datetime_utc() -> str:
    """Get current datetime in ISO-8601 UTC format"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_to_local(utc_datetime_str: str, local_tz: str = None) -> str:
    """
    Convert UTC datetime string to local timezone.
    
    Args:
        utc_datetime_str: ISO-8601 UTC datetime string (e.g., "2025-12-03T05:00:00Z")
        local_tz: Local timezone name (e.g., "Asia/Dhaka"). If None, uses system timezone.
        
    Returns:
        Formatted local datetime string
    """
    try:
        # Parse UTC datetime
        if utc_datetime_str.endswith('Z'):
            utc_datetime_str = utc_datetime_str[:-1] + '+00:00'
        utc_dt = datetime.fromisoformat(utc_datetime_str)
        
        # Convert to local timezone
        if local_tz:
            local_timezone = ZoneInfo(local_tz)
        else:
            local_timezone = datetime.now().astimezone().tzinfo
        
        local_dt = utc_dt.astimezone(local_timezone)
        return local_dt.strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        return utc_datetime_str


def local_to_utc(date_str: str, time_str: str = None, local_tz: str = None) -> str:
    """
    Convert local date/time to UTC ISO-8601 format.
    
    Args:
        date_str: Date string (e.g., "2025-12-03")
        time_str: Time string (e.g., "15:00", "3pm")
        local_tz: Local timezone name. If None, uses system timezone.
        
    Returns:
        ISO-8601 UTC datetime string (e.g., "2025-12-03T05:00:00Z")
    """
    try:
        # Get local timezone
        if local_tz:
            local_timezone = ZoneInfo(local_tz)
        else:
            local_timezone = datetime.now().astimezone().tzinfo
        
        # Parse date
        if date_str:
            local_dt = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            local_dt = datetime.now()
        
        # Add time if provided
        if time_str:
            time_parts = datetime.strptime(time_str, "%H:%M")
            local_dt = local_dt.replace(hour=time_parts.hour, minute=time_parts.minute, second=0)
        else:
            local_dt = local_dt.replace(hour=0, minute=0, second=0)
        
        # Make timezone aware and convert to UTC
        local_dt = local_dt.replace(tzinfo=local_timezone)
        utc_dt = local_dt.astimezone(timezone.utc)
        
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        # Fallback: return current time in UTC
        return get_current_datetime_utc()


def parse_iso8601_to_datetime(iso_string: str) -> Optional[datetime]:
    """
    Parse ISO-8601 string to timezone-aware datetime object.
    
    Args:
        iso_string: ISO-8601 format string (e.g., "2025-12-03T05:00:00Z")
        
    Returns:
        Timezone-aware datetime object or None if parsing fails
    """
    try:
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1] + '+00:00'
        return datetime.fromisoformat(iso_string)
    except (ValueError, AttributeError):
        return None


def format_response_for_display(result: dict, local_tz: str = None) -> dict:
    """
    Convert UTC times in response to local timezone for display.
    
    Args:
        result: Chatbot response dict
        local_tz: Local timezone name (e.g., "Asia/Dhaka")
        
    Returns:
        Same response with additional _local fields for datetime
    """
    display_result = result.copy()
    
    if result.get("response_type") == "event" and result.get("event_datetime"):
        display_result["event_datetime_local"] = utc_to_local(result["event_datetime"], local_tz)
    
    elif result.get("response_type") == "task":
        if result.get("start_time"):
            display_result["start_time_local"] = utc_to_local(result["start_time"], local_tz)
        if result.get("end_time"):
            display_result["end_time_local"] = utc_to_local(result["end_time"], local_tz)
    
    return display_result
