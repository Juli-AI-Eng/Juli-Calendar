"""AI component for analyzing availability queries."""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pytz
import logging
import os
import json
from openai import OpenAI

logger = logging.getLogger(__name__)


class AvailabilityChecker:
    """Analyzes availability queries to understand intent and extract parameters."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the AvailabilityChecker with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
    
    def analyze_availability_query(
        self, 
        query: str, 
        user_context: Dict[str, Any],
        default_duration: int = 60
    ) -> Dict[str, Any]:
        """
        Analyze an availability query using AI to determine type and parameters.
        """
        logger.info(f"Analyzing availability query: {query}")
        logger.debug(f"User context: {user_context}")
        
        try:
            # Try AI analysis first
            result = self._ai_analysis(query, user_context, default_duration)
            logger.info(f"AI analysis result: {result}")
            return result
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Return error instead of bad fallback
            return {
                "type": "error",
                "error": str(e),
                "message": "I had trouble understanding your availability request. Please try rephrasing it."
            }
    
    def _ai_analysis(self, query: str, user_context: Dict[str, Any], default_duration: int) -> Dict[str, Any]:
        """Use OpenAI to intelligently analyze the availability query."""
        
        # Define the function tool for availability analysis
        analyze_availability_tool = {
            "type": "function",
            "function": {
                "name": "analyze_availability",
                "description": "Extract availability check parameters from user query",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["specific_time", "find_slots"],
                            "description": "Whether checking a specific time or finding available slots"
                        },
                        "datetime": {
                            "type": ["string", "null"],
                            "description": "ISO format datetime for specific time check (e.g., '2024-01-15T14:00:00')"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duration of the meeting/event in minutes",
                            "minimum": 15,
                            "maximum": 480
                        },
                        "time_range": {
                            "type": ["string", "null"],
                            "description": "Natural language time range to search for available slots (e.g., 'today', 'next Wednesday', 'the week after next', etc.)"
                        },
                        "preferences": {
                            "type": "object",
                            "properties": {
                                "prefer_morning": {"type": "boolean"},
                                "prefer_afternoon": {"type": "boolean"},
                                "prefer_evening": {"type": "boolean"},
                                "earliest_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                                "latest_hour": {"type": "integer", "minimum": 0, "maximum": 23}
                            },
                            "description": "Time preferences for finding slots"
                        }
                    },
                    "required": ["type", "duration_minutes"]
                }
            }
        }
        
        system_message = f"""You are analyzing availability queries for a calendar system.
Current date/time: {user_context.get('current_date')} {user_context.get('current_time')} {user_context.get('timezone', 'UTC')}
User's current datetime: {user_context['now'].isoformat()}
Day of week: {user_context['now'].strftime('%A')}

Extract availability check parameters from the user's query. Consider:
- Is the user checking a specific time ("Am I free at 2pm tomorrow?") or finding available slots ("Find me time for a meeting")
- What date/time are they asking about (parse natural language like "tomorrow at 2pm", "next Tuesday", etc.)
- How long should the meeting be (default to {default_duration} minutes if not specified)
- For finding slots: what time range (today, this week, etc.) and preferences (morning, afternoon)

IMPORTANT for date parsing:
- "next Tuesday" means the Tuesday of NEXT week, not this week
- "this Tuesday" means the Tuesday of the current week
- "Tuesday" without qualifier usually means the next occurring Tuesday
- Always preserve the time specified (e.g., "3pm" should be 15:00, not 2am)
- Calculate dates relative to the current datetime shown above

For specific time checks, convert the mentioned time to ISO format.
For relative times like "tomorrow at 2pm", calculate from the current datetime."""

        try:
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=query,
                tool_def=analyze_availability_tool,
                reasoning_effort="low",
                force_tool=True,
            )
            
            # Convert datetime string to datetime object if present
            if result.get("datetime"):
                result["datetime"] = datetime.fromisoformat(result["datetime"].replace('Z', '+00:00'))
                # Ensure timezone awareness
                if result["datetime"].tzinfo is None:
                    tz = pytz.timezone(user_context.get('timezone', 'UTC'))
                    result["datetime"] = tz.localize(result["datetime"])
            
            # Set default duration if not provided
            if "duration_minutes" not in result:
                result["duration_minutes"] = default_duration
            
            logger.info(f"AI availability analysis result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"OpenAI call failed: {str(e)}")
            raise
    
    def _fallback_analysis(self, query: str, user_context: Dict[str, Any], default_duration: int) -> Dict[str, Any]:
        """Fallback to simple pattern matching if AI fails."""
        query_lower = query.lower()
        
        # Detect if checking specific time vs finding slots
        if any(word in query_lower for word in ["am i free", "available at", "free at", "check"]):
            # Specific time check
            return self._parse_specific_time_check(query_lower, user_context, default_duration)
        else:
            # Find available slots
            return self._parse_find_slots(query_lower, user_context, default_duration)
    
    def _parse_specific_time_check(
        self, 
        query: str, 
        user_context: Dict[str, Any],
        default_duration: int
    ) -> Dict[str, Any]:
        """Parse a specific time availability check."""
        result = {
            "type": "specific_time",
            "duration_minutes": default_duration
        }
        
        # Parse time references (stub implementation)
        user_now = user_context["now"]
        
        if "tomorrow" in query:
            # Tomorrow at 2pm example
            if "2pm" in query or "2 pm" in query:
                target_time = user_now + timedelta(days=1)
                target_time = target_time.replace(hour=14, minute=0, second=0, microsecond=0)
                result["datetime"] = target_time
            else:
                # Default to 9am tomorrow
                target_time = user_now + timedelta(days=1)
                target_time = target_time.replace(hour=9, minute=0, second=0, microsecond=0)
                result["datetime"] = target_time
        else:
            # Default to next hour
            target_time = user_now + timedelta(hours=1)
            target_time = target_time.replace(minute=0, second=0, microsecond=0)
            result["datetime"] = target_time
        
        # Extract duration if mentioned
        if "30 min" in query or "30min" in query:
            result["duration_minutes"] = 30
        elif "1 hour" in query or "1hr" in query:
            result["duration_minutes"] = 60
        elif "2 hour" in query or "2hr" in query:
            result["duration_minutes"] = 120
        
        return result
    
    def _parse_find_slots(
        self,
        query: str,
        user_context: Dict[str, Any],
        default_duration: int
    ) -> Dict[str, Any]:
        """Parse a find available slots request."""
        result = {
            "type": "find_slots",
            "duration_minutes": default_duration,
            "preferences": {}
        }
        
        # Extract duration
        if "30 min" in query or "30min" in query:
            result["duration_minutes"] = 30
        elif "1 hour" in query or "1hr" in query or "1-hour" in query:
            result["duration_minutes"] = 60
        elif "2 hour" in query or "2hr" in query or "2 hour" in query:
            result["duration_minutes"] = 120
        
        # Extract time range
        if "today" in query:
            result["time_range"] = "today"
        elif "tomorrow" in query:
            result["time_range"] = "tomorrow"
        elif "this week" in query or "week" in query:
            result["time_range"] = "this_week"
        elif "next week" in query:
            result["time_range"] = "next_week"
        else:
            result["time_range"] = "this_week"  # Default
        
        # Extract preferences
        if "morning" in query:
            result["preferences"]["prefer_morning"] = True
        elif "afternoon" in query:
            result["preferences"]["prefer_afternoon"] = True
        elif "evening" in query:
            result["preferences"]["prefer_evening"] = True
        
        return result