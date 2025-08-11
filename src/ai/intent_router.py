"""AI Intent Router for intelligent routing between Reclaim and Nylas."""
import json
from typing import Dict, Any, Optional
import logging
import os
from openai import OpenAI
import src.ai.openai_utils as openai_utils

logger = logging.getLogger(__name__)


class IntentRouter:
    """Routes user queries to the appropriate provider using AI analysis."""
    
    def __init__(self, openai_client=None):
        """Initialize the router with OpenAI client."""
        self.client = openai_client or OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def analyze_intent(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze user query using AI to determine provider and intent.
        
        Returns:
            Dict with:
            - provider: 'reclaim' or 'nylas'
            - intent_type: 'task' or 'calendar'
            - confidence: 0.0-1.0
            - reasoning: explanation of decision
            - involves_others: bool
            - extracted_time: time-related info
            - operation: 'create', 'update', 'complete', or 'cancel'
            - task_details: task-specific details
            - event_details: event-specific details
        """
        return self._openai_analysis(query, user_context)
    
    def _openai_analysis(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Use OpenAI for intelligent intent analysis."""
        try:
            # Build context for GPT
            context_str = ""
            if user_context:
                context_str = f"""
Current user time: {user_context.get('now', 'Unknown')}
User timezone: {user_context.get('timezone', 'Unknown')}
Current date: {user_context.get('current_date', 'Unknown')}
"""
            
            # Define the function tool (minimal strict schema for reliable routing)
            analyze_intent_tool = {
                "type": "function",
                "function": {
                    "name": "analyze_intent",
                    "description": "Classify request and detect if it involves other people.",
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "provider": {"type": "string", "enum": ["reclaim", "nylas"]},
                            "intent_type": {"type": "string", "enum": ["task", "calendar"]},
                            "involves_others": {
                                "type": "boolean",
                                "description": "True if the event/task involves other people (team standup, meeting with someone, group activity). False for solo activities."
                            }
                        },
                        "required": ["provider", "intent_type", "involves_others"]
                    }
                }
            }
            
            
            messages = [
                {
                    "role": "system", 
                    "content": """You are a request classifier for a productivity system.

CLASSIFICATION RULES:
RULE 1: If the query contains the word "task" → Return provider="reclaim", intent_type="task", involves_others=false (unless explicitly collaborative)
RULE 2: Otherwise, if it mentions meetings/appointments/calendar OR has a specific time (like "at 3pm", "tomorrow morning", "Monday at 10am") → Return provider="nylas", intent_type="calendar"
RULE 3: Otherwise → Return provider="reclaim", intent_type="task", involves_others=false

CRITICAL: The word "task" ALWAYS means Reclaim. No exceptions.

PARTICIPANT DETECTION for involves_others field:
Set involves_others=true if the request clearly involves multiple people:
- Event types that imply groups: team standup, team meeting, all-hands, staff meeting
- Named participants: "with John", "and Sarah", "the marketing team"
- Collaborative terms: interview, review with, sync with, 1:1, one-on-one, demo, workshop

Set involves_others=false for solo activities:
- Personal appointments, deep work, focus time, study time
- Individual tasks without mention of others

IMPORTANT TIME RULES:
- "at 3pm", "tomorrow at 10am", "Monday morning" = specific time → calendar event
- "by Friday", "end of week", "next month" = due date → task
- "tomorrow morning" = specific time (defaults to 9am) → calendar event

You must call analyze_intent for every request."""
                },
                {
                    "role": "user",
                    "content": f"{context_str}\n\nUser request: {query}"
                }
            ]
            
            # Responses API call via helper
            # Extract system and user content from messages
            system_text = messages[0]["content"]
            user_text = messages[1]["content"]
            
            result = openai_utils.call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_text,
                user_text=user_text,
                tool_def=analyze_intent_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
            
            # COMPREHENSIVE DEBUG: Intent classification
            logger.info(f"Intent Classification - Query: '{query[:50]}...'")
            logger.info(f"  → Provider: {result.get('provider')} | Intent: {result.get('intent_type')} | Confidence: {result.get('confidence', 0):.2f}")
            logger.info(f"  → Reasoning: {result.get('reasoning', 'N/A')[:100]}...")
            
            # DEBUG: Log raw minimal result
            logger.info(f"[DEBUG] Router minimal result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"AI intent analysis failed: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Full exception details: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return error response asking for clarification
            return {
                'provider': None,
                'intent_type': None,
                'confidence': 0.0,
                'reasoning': f'AI analysis failed: {str(e)}. Please try rephrasing your request.',
                'involves_others': False,
                'extracted_time': {},
                'error': True,
                'error_message': 'I had trouble understanding your request. Could you please rephrase it?',
                'debug': {
                    'exception_type': type(e).__name__,
                    'exception_message': str(e)
                }
            }