import os
import json
from typing import List, Dict, Any
from datetime import datetime, timezone
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from django.conf import settings


def chatbot(convo_history: List[Dict], query: str) -> Dict[str, Any]:

    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        openai_api_key=api_key
    )
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")
    
    system_prompt = f"""You are a friendly and helpful personal assistant that helps users manage their day.
    Your responses should be warm, conversational, and encouraging.

    Current date: {current_date}
    Current time: {current_time}

    Classify the user's request and respond with structured JSON:

    For EVENTS (appointments, meetings, scheduled activities):
    {{
    "type": "event",
    "content": "Warm conversational confirmation (e.g., 'Great! I've scheduled your meeting...')",
    "title": "Short title of the event",
    "description": "Detailed description",
    "location_address": "Address or location (if mentioned, otherwise empty string)",
    "event_datetime": "YYYY-MM-DDTHH:MM:SSZ (UTC format)",
    "reminders": [
        {{"time_before": 30, "types": ["notification"]}}
    ]
    }}

    For TASKS (action items, todos):
    {{
    "type": "task",
    "content": "Warm conversational confirmation",
    "title": "Short title of the task",
    "description": "Detailed description of what needs to be done",
    "start_time": "YYYY-MM-DDTHH:MM:SSZ (when to start, UTC format)",
    "end_time": "YYYY-MM-DDTHH:MM:SSZ (deadline, UTC format)",
    "tags": ["tag1", "tag2"],
    "reminders": [
        {{"time_before": 60, "types": ["notification"]}}
    ]
    }}

    For NOTES (information to remember):
    {{
    "type": "note",
    "title": "Short title of the note",
    "content": "The information to save"
    }}

    For GENERAL RESPONSE (questions, greetings, etc.):
    {{
    "type": "response",
    "content": "Your helpful response"
    }}

    IMPORTANT RULES:
    - All datetime must be in ISO-8601 UTC format (e.g., "2025-12-03T19:00:00Z")
    - Convert mentioned times to UTC (assume user is in UTC+6/Asia/Dhaka timezone)
    - Always include both simple fields (date, time) AND rich fields (event_datetime, etc.) for compatibility
    - time_before in reminders is in minutes
    - Include appropriate reminders based on urgency
    - Extract tags from context for tasks
    - Always include location_address for events (empty string if not mentioned)
    """
    
    messages = [SystemMessage(content=system_prompt)]
    
    # Add conversation history
    for msg in convo_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["message"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["message"]))
    
    # Add current query
    messages.append(HumanMessage(content=query))
    
    # Get response
    response = llm.invoke(messages)
    
    # Parse JSON response
    try:
        result = json.loads(response.content.strip())
        
        # Handle if result is a list (take first item)
        if isinstance(result, list):
            result = result[0] if result else {}
        
        # Ensure result is a dict
        if not isinstance(result, dict):
            raise ValueError("Invalid response format")
        
        response_type = result.get("type", "response")
        
        # Add rich fields based on type
        if response_type == "event":
            return {
                "response_type": "event",
                "content": result.get("content", ""),  # ← ADDED THIS
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "location_address": result.get("location_address", ""),
                "event_datetime": result.get("event_datetime", ""),
                "reminders": result.get("reminders", [{"time_before": 30, "types": ["notification"]}])
            }
        
        elif response_type == "task":
            return {
                "response_type": "task",
                "content": result.get("content", ""),
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "start_time": result.get("start_time", ""),
                "end_time": result.get("end_time", ""),
                "tags": result.get("tags", []),
                "reminders": result.get("reminders", [{"time_before": 60, "types": ["notification"]}])
            }
        
        elif response_type == "note":
            return {
                "response_type": "note",
                "title": result.get("title", ""),
                "note_content": result.get("note_content", result.get("content", ""))
            }
        
        else:  # response
            return {
                "response_type": "response",
                "content": result.get("content", response.content)
            }
        
    except (json.JSONDecodeError, ValueError, KeyError):
        # Fallback if JSON parsing fails
        return {
            "response_type": "response",
            "content": response.content
        }




def classifier(convo_history: List[Dict], query: str) -> Dict[str, Any]:
    """
    Enhanced classifier that identifies the type of user query and extracts structured data.
    
    Args:
        convo_history: List of conversation messages with 'role', 'timestamp', 'message'
        query: User's current query
        
    Returns:
        For events: {response_type, title, description, location_address, event_datetime, reminders}
        For tasks: {response_type, title, description, start_time, end_time, tags, reminders}
        For notes: {response_type, title, content}
        For response: {response_type}
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.3,
        openai_api_key=api_key
    )
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M")
    
    system_prompt = f"""You are a classification system that categorizes user queries and extracts structured data.

Current date: {current_date}
Current time: {current_time}

Classify and extract data based on the type:

For EVENTS (appointments, meetings, scheduled activities):
{{
  "type": "event",
  "title": "Short title of the event",
  "description": "Detailed description",
  "location_address": "Address or location (empty string if not mentioned)",
  "event_datetime": "YYYY-MM-DDTHH:MM:SSZ (UTC format)",
  "reminders": [
    {{"time_before": 30, "types": ["notification"]}}
  ]
}}

For TASKS (action items, todos):
{{
  "type": "task",
  "title": "Short title of the task",
  "description": "Detailed description of what needs to be done",
  "start_time": "YYYY-MM-DDTHH:MM:SSZ (UTC format)",
  "end_time": "YYYY-MM-DDTHH:MM:SSZ (deadline, UTC format)",
  "tags": ["tag1", "tag2"],
  "reminders": [
    {{"time_before": 60, "types": ["notification"]}}
  ]
}}

For NOTES (information to remember):
{{
  "type": "note",
  "title": "Short title of the note",
  "content": "The information to save"
}}

For GENERAL/RESPONSE (questions, greetings):
{{
  "type": "response"
}}

IMPORTANT:
- All datetime must be in ISO-8601 UTC format (e.g., "2025-12-03T19:00:00Z")
- Convert times to UTC (assume user is in UTC+6/Asia/Dhaka timezone)
- time_before in reminders is in minutes
- Extract relevant tags for tasks
- Do NOT include conversational content - only classification data"""
    
    messages = [SystemMessage(content=system_prompt)]
    
    for msg in convo_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["message"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["message"]))
    
    messages.append(HumanMessage(content=query))
    
    response = llm.invoke(messages)
    
    try:
        result = json.loads(response.content.strip())
        
        if isinstance(result, list):
            result = result[0] if result else {}
        
        if not isinstance(result, dict):
            raise ValueError("Invalid response format")
        
        response_type = result.get("type", "response")
        
        if response_type == "event":
            return {
                "response_type": "event",
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "location_address": result.get("location_address", ""),
                "event_datetime": result.get("event_datetime", ""),
                "reminders": result.get("reminders", [{"time_before": 30, "types": ["notification"]}])
            }
        
        elif response_type == "task":
            return {
                "response_type": "task",
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "start_time": result.get("start_time", ""),
                "end_time": result.get("end_time", ""),
                "tags": result.get("tags", []),
                "reminders": result.get("reminders", [{"time_before": 60, "types": ["notification"]}])
            }
        
        elif response_type == "note":
            return {
                "response_type": "note",
                "title": result.get("title", ""),
                "content": result.get("content", "")
            }
        
        else:  # response
            return {
                "response_type": "response"
            }
            
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"⚠️ Classifier parsing error: {e}")
        return {
            "response_type": "response"
        }
