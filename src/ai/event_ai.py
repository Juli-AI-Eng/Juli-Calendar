"""AI component for parsing and understanding event requests."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz

import os
from openai import OpenAI
from src.ai import openai_utils

logger = logging.getLogger(__name__)


class EventAI:
    """AI component for parsing calendar event requests."""
    
    def __init__(self, openai_api_key: Optional[str] = None, model="gpt-5"):
        """Initialize EventAI with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
    
    def understand_event_request(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Parse a natural language event request and extract structured data.
        
        Args:
            query: Natural language event request
            user_context: User timezone and current time information
            
        Returns:
            Dict with event details including:
            - operation: create, update, cancel, etc.
            - title: Event title
            - start_time: ISO format start time
            - end_time: ISO format end time
            - participants: List of participant names
            - location: Event location
            - description: Event description
            - event_reference: For updates/cancellations
        """
        user_context = user_context or {}
        
        # Build context string
        context_str = f"""
Current date: {user_context.get('current_date', 'Unknown')}
Current time: {user_context.get('current_time', 'Unknown')}
User timezone: {user_context.get('timezone', 'UTC')}
"""
        
        # Define the function for event parsing
        event_parse_function = {
            "type": "function",
            "function": {
                "name": "parse_event",
                "description": "Extract structured event information from natural language.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["create", "update", "cancel", "delete"],
                            "description": "The operation to perform"
                        },
                        "title": {
                            "type": "string",
                            "description": "Event title or subject"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Event start time in ISO format YYYY-MM-DDTHH:MM:SS"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "Event end time in ISO format YYYY-MM-DDTHH:MM:SS"
                        },
                        "participants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of participant names"
                        },
                        "location": {
                            "type": ["string", "null"],
                            "description": "Event location or null if not specified"
                        },
                        "description": {
                            "type": ["string", "null"],
                            "description": "Event description or notes or null if not specified"
                        },
                        "event_reference": {
                            "type": ["string", "null"],
                            "description": "Reference to existing event for update/cancel operations or null if not applicable"
                        }
                    },
                    "required": ["operation", "title", "start_time", "end_time", "participants", "location", "description", "event_reference"]
                }
            }
        }
        
        # Build system message
        system_text = f"""You are an event parser. Extract structured event information from natural language.

{context_str}

OPERATION DETECTION:
- "schedule", "book", "create", "add" → operation="create"
- "reschedule", "update", "change", "modify" → operation="update"
- "cancel", "delete", "remove" → operation="cancel"

TIME PARSING:
- "tomorrow at 2pm" → use tomorrow's date + 14:00:00
- "Monday morning" → next Monday + 09:00:00
- "3pm" → today + 15:00:00
- Always output in ISO format: YYYY-MM-DDTHH:MM:SS
- If no end time specified, add 1 hour to start time

DEFAULT TIMES:
- "morning" → 09:00
- "afternoon" → 14:00
- "evening" → 17:00
- "lunch" → 12:00

PARTICIPANT EXTRACTION:
- "with John and Sarah" → participants: ["John", "Sarah"]
- "meeting with the team" → participants: ["team"]
- "team standup" → participants: ["team"] (standup implies team participation)
- "team meeting" → participants: ["team"]
- "all-hands" → participants: ["all-hands"]
- "1:1 with Bob" → participants: ["Bob"]
- "staff meeting" → participants: ["staff"]
- "interview" → participants: ["interviewer"] (implies other person)
- Extract all names mentioned as participants
- If the event type inherently involves multiple people (standup, team meeting, all-hands, etc.), include that as a participant

For UPDATE/CANCEL operations:
- Set event_reference to identify which event. This should be the core title of the event, not the full phrase.
  - E.g. "cancel the 3pm meeting" -> event_reference="3pm meeting"
  - E.g. "reschedule the team standup" -> event_reference="team standup"
  - E.g. "cancel Personal appointment tomorrow at 3pm" -> event_reference="Personal appointment"
  - Do NOT include dates or times in event_reference unless they are part of the core title
- Extract new values for updates

IMPORTANT: Always extract start_time for create operations. Use the current date/time context provided."""
        
        user_text = f"Parse this event request: {query}"
        
        try:
            # Call OpenAI to parse the event
            result = openai_utils.call_function_tool(
                client=self.client,
                model=self.model,
                system_text=system_text,
                user_text=user_text,
                tool_def=event_parse_function,
                reasoning_effort="medium",
                force_tool=True
            )
            
            logger.info(f"EventAI parsed: operation={result.get('operation')}, "
                       f"title={result.get('title')}, start_time={result.get('start_time')}")
            
            # Post-process to ensure we have required fields
            if result.get('operation') == 'create':
                # Ensure we have a start time for create operations
                if not result.get('start_time'):
                    # Try to infer from context
                    result['start_time'] = self._infer_start_time(query, user_context)
                
                # Ensure we have an end time
                if not result.get('end_time') and result.get('start_time'):
                    result['end_time'] = self._calculate_end_time(result['start_time'])
                
                # Ensure we have a title
                if not result.get('title'):
                    result['title'] = self._extract_title(query, result)
            
            return result
            
        except Exception as e:
            logger.error(f"EventAI parsing failed: {e}")
            return {
                "operation": "create",
                "error": str(e)
            }
    
    def _infer_start_time(self, query: str, user_context: Dict[str, Any]) -> str:
        """Infer start time from query if not explicitly extracted."""
        # This is a fallback - should rarely be needed
        current_date = user_context.get('current_date', datetime.now().strftime('%Y-%m-%d'))
        
        # Look for time indicators
        query_lower = query.lower()
        if 'morning' in query_lower:
            return f"{current_date}T09:00:00"
        elif 'afternoon' in query_lower:
            return f"{current_date}T14:00:00"
        elif 'evening' in query_lower:
            return f"{current_date}T17:00:00"
        elif 'tomorrow' in query_lower:
            # Add one day to current date
            tomorrow = datetime.strptime(current_date, '%Y-%m-%d') + timedelta(days=1)
            return f"{tomorrow.strftime('%Y-%m-%d')}T09:00:00"
        else:
            # Default to next hour
            return f"{current_date}T{datetime.now().hour + 1:02d}:00:00"
    
    def _calculate_end_time(self, start_time: str) -> str:
        """Calculate end time as 1 hour after start time."""
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = start_dt + timedelta(hours=1)
            return end_dt.strftime('%Y-%m-%dT%H:%M:%S')
        except:
            # Fallback
            return start_time
    
    def _extract_title(self, query: str, parsed_data: Dict[str, Any]) -> str:
        """Extract a title from the query."""
        # Use participants if available
        if parsed_data.get('participants'):
            participants = parsed_data['participants']
            if len(participants) == 1:
                return f"Meeting with {participants[0]}"
            elif len(participants) == 2:
                return f"Meeting with {' and '.join(participants)}"
            else:
                return f"Meeting with {', '.join(participants[:-1])} and {participants[-1]}"
        
        # Look for meeting type keywords
        query_lower = query.lower()
        if 'standup' in query_lower:
            return "Standup Meeting"
        elif 'sync' in query_lower:
            return "Sync Meeting"
        elif 'review' in query_lower:
            return "Review Meeting"
        elif '1:1' in query_lower or 'one on one' in query_lower:
            return "1:1 Meeting"
        else:
            return "Meeting"