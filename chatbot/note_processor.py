import os
import json
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from django.conf import settings


def summarize_note(raw_note: str) -> Dict[str, Any]:
    
    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.9,
        openai_api_key=api_key
    )
    
    system_prompt = """You are a note summarizer. Transform messy notes into clean, structured summaries.

    Output as JSON:
    {
    "summary": "Clean, well-written summary (4-10 sentences max)",
    "points": ["point 1", "point 2"] // Only include if note has multiple distinct items
    }

    Rules:
    - Simple note → only summary, empty points array
    - Complex note with multiple items → summary + points
    - Be concise and clear
    - Fix grammar
    - Output ONLY JSON"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Summarize:\n\n{raw_note}")
    ]
    
    response = llm.invoke(messages)
    
    try:
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        result = json.loads(content)
        
        return {
            "summary": result.get("summary", ""),
            "points": result.get("points", [])
        }
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️ Summarizer error: {e}")
        return {
            "summary": raw_note[:300] + "..." if len(raw_note) > 300 else raw_note,
            "points": []
        }
