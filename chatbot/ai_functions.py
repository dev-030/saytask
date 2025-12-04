import os
import json
from typing import List, Dict, Any
from datetime import datetime, timezone
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from django.conf import settings


def chatbot(convo_history: List[Dict], query: str) -> Dict[str, Any]:
    """
    Chatbot that classifies user queries and returns structured responses.
    
    Args:
        convo_history: List of conversation messages with 'role', 'timestamp', 'message'
        query: User's current query
        
    Returns:
        Dict with 'response_type' (response/event/note/task), 'content', and optional 'date'/'time'
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.7,
        openai_api_key=api_key
    )
    
    system_prompt = """You are a friendly and helpful personal assistant that helps users manage their day.
Your responses should be warm, conversational, and encouraging.

Classify the user's request and respond accordingly:
- response: General conversation or questions
- event: Time-specific activities or appointments
- note: Information to remember or save
- task: Action items or todos

Format your response as JSON:
{
  "type": "response|event|note|task",
  "content": "your conversational response",
  "date": "YYYY-MM-DD (if applicable)",
  "time": "HH:MM (if applicable)"
}

RESPONSE STYLE GUIDELINES:
- Be conversational and friendly (use "I've", "Sure!", "Got it!", etc.)
- Confirm what you understood from the user
- For events/tasks: acknowledge with enthusiasm (e.g., "Great! I've scheduled...", "✓ Added...", "All set!")
- For notes: confirm you've saved it (e.g., "Noted! I'll remember...", "Got it, saved!")
- Use emojis sparingly for warmth (✓, 📅, ✅)
- Keep responses concise but warm

CRITICAL FORMATTING RULES:
1. date MUST be in YYYY-MM-DD format (e.g., "2025-12-04"). NEVER use words like "today", "tomorrow"
2. time MUST be in HH:MM 24-hour format (e.g., "19:00" for 7 PM, "09:00" for 9 AM)
3. Only include date and time fields if they are mentioned or can be inferred
4. If you cannot determine a specific date/time, omit those fields entirely

EXAMPLES:
User: "meeting at 7pm with mir"
Response: {
  "type": "event",
  "content": "Perfect! I've scheduled your meeting with Mir for today at 7 PM ✓",
  "date": "2025-12-04",
  "time": "19:00"
}

User: "remind me to buy milk"
Response: {
  "type": "task",
  "content": "Sure thing! I'll remind you to buy milk ✓"
}

User: "note that the wifi password is abc123"
Response: {
  "type": "note",
  "content": "Got it! I've saved the WiFi password for you 📝"
}"""

    
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
        
        output = {
            "response_type": result.get("type", "response"),
            "content": result.get("content", response.content)
        }
        
        # Add date and time if present
        if "date" in result and result["date"]:
            output["date"] = result["date"]
        if "time" in result and result["time"]:
            output["time"] = result["time"]
            
        return output
    except (json.JSONDecodeError, ValueError, KeyError):
        # Fallback if JSON parsing fails
        return {
            "response_type": "response",
            "content": response.content
        }


def classifier(convo_history: List[Dict], query: str) -> Dict[str, Any]:
    """
    Classifier that only identifies the type of user query without generating responses.
    
    Args:
        convo_history: List of conversation messages with 'role', 'timestamp', 'message'
        query: User's current query
        
    Returns:
        Dict with 'response_type' (response/event/note/task) and optional 'date'/'time'
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.3,
        openai_api_key=api_key
    )
    
    system_prompt = """You are a classification system that categorizes user queries.
Classify the user's request into one of these categories:
- response: General conversation or questions that don't require action
- event: Time-specific activities, appointments, or scheduled items
- note: Information to remember or save for later
- task: Action items, todos, or things that need to be done

Extract dates and times if mentioned.

Format your response as JSON with ONLY classification data (no conversational content):
{
  "type": "response|event|note|task",
  "date": "YYYY-MM-DD (if applicable)",
  "time": "HH:MM (if applicable)"
}

Only include date and time fields if they are explicitly mentioned."""
    
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
        
        output = {
            "response_type": result.get("type", "response")
        }
        
        if "date" in result and result["date"]:
            output["date"] = result["date"]
        if "time" in result and result["time"]:
            output["time"] = result["time"]
            
        return output
    except (json.JSONDecodeError, ValueError, KeyError):
        return {
            "response_type": "response"
        }
