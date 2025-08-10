"""AI component for schedule optimization."""
from typing import Dict, Any, List, Optional
import logging
import os
import json
from openai import OpenAI

logger = logging.getLogger(__name__)


class ScheduleOptimizer:
    """Analyzes schedules and generates optimization suggestions."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the ScheduleOptimizer with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
    
    def analyze_optimization_request(
        self,
        request: str,
        preferences: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze an optimization request to understand goals and constraints.
        
        This is a stub implementation. In production, this would use
        OpenAI function calling to understand the request.
        """
        logger.info(f"Analyzing optimization request: {request}")
        
        request_lower = request.lower()
        
        # Detect optimization type
        if any(word in request_lower for word in ["focus", "deep work", "concentrate"]):
            optimization_type = "focus_time"
            goals = ["maximize_deep_work", "minimize_context_switching"]
        elif any(word in request_lower for word in ["balance", "workload", "distribute"]):
            optimization_type = "workload_balance"
            goals = ["even_distribution", "prevent_overload"]
        elif any(word in request_lower for word in ["energy", "morning", "afternoon"]):
            optimization_type = "energy_alignment"
            goals = ["match_energy_levels", "optimize_performance"]
        elif any(word in request_lower for word in ["priority", "urgent", "important"]):
            optimization_type = "priority_based"
            goals = ["prioritize_urgent", "ensure_important_done"]
        elif any(word in request_lower for word in ["meeting", "overload", "reduce"]):
            optimization_type = "meeting_reduction"
            goals = ["batch_meetings", "create_focus_blocks"]
        else:
            optimization_type = "general"
            goals = ["improve_productivity"]
        
        # Extract time range
        if "today" in request_lower:
            time_range = "today"
        elif "tomorrow" in request_lower:
            time_range = "tomorrow"
        elif "week" in request_lower:
            time_range = "this_week"
        else:
            time_range = "this_week"
        
        return {
            "optimization_type": optimization_type,
            "goals": goals,
            "time_range": time_range,
            "preferences": self._parse_preferences(preferences)
        }
    
    def generate_optimization_plan(
        self,
        current_schedule: Dict[str, Any],
        optimization_request: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate an optimization plan using AI based on current schedule and goals.
        """
        try:
            return self._ai_optimization_plan(current_schedule, optimization_request, user_context)
        except Exception as e:
            logger.error(f"AI optimization failed: {e}")
            return {
                "suggestions": [],
                "metrics": {},
                "summary": "Unable to generate optimization suggestions at this time.",
                "error": str(e)
            }
    
    def _ai_optimization_plan(
        self,
        current_schedule: Dict[str, Any],
        optimization_request: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use AI to generate specific optimization suggestions based on actual schedule."""
        
        # Define the function tool for optimization suggestions
        generate_suggestions_tool = {
            "type": "function",
            "function": {
                "name": "generate_optimization_suggestions",
                "description": "Generate specific schedule optimization suggestions",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "suggestions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["reschedule", "block_time", "batch_meetings", "redistribute", "cancel", "delegate"],
                                        "description": "Type of optimization action"
                                    },
                                    "action": {
                                        "type": "string",
                                        "description": "Specific action to take (e.g., 'Move Team Standup from Monday 9am to Tuesday 3pm')"
                                    },
                                    "command": {
                                        "type": "string",
                                        "description": "Natural language command the user can say to execute this (e.g., 'Reschedule Team Standup to Tuesday at 3pm')"
                                    },
                                    "impact": {
                                        "type": "string",
                                        "enum": ["high", "medium", "low"],
                                        "description": "Expected impact of this change"
                                    },
                                    "reasoning": {
                                        "type": "string",
                                        "description": "Why this suggestion would help"
                                    },
                                    "affects_others": {
                                        "type": "boolean",
                                        "description": "Whether this change affects other people"
                                    }
                                },
                                "required": ["type", "action", "command", "impact", "reasoning"]
                            },
                            "description": "List of specific optimization suggestions"
                        },
                        "metrics": {
                            "type": "object",
                            "properties": {
                                "current_focus_hours": {"type": "number"},
                                "potential_focus_hours": {"type": "number"},
                                "meeting_hours_saved": {"type": "number"},
                                "workload_balance_improvement": {"type": "string"},
                                "estimated_productivity_gain": {"type": "string"}
                            },
                            "description": "Quantitative improvements from suggestions"
                        },
                        "summary": {
                            "type": "string",
                            "description": "Brief summary of the optimization plan"
                        }
                    },
                    "required": ["suggestions", "metrics", "summary"]
                }
            }
        }
        
        # Create a summary of the current schedule
        schedule_summary = {
            "tasks": [
                {
                    "title": task.get("title"),
                    "due": task.get("due"),
                    "duration": task.get("duration_hours", 1),
                    "priority": task.get("priority")
                }
                for task in current_schedule.get("tasks", [])[:20]  # Limit to avoid token overflow
            ],
            "events": [
                {
                    "title": event.get("title"),
                    "when": event.get("when", {}).get("start_time"),
                    "duration": (event.get("when", {}).get("end_time", 0) - event.get("when", {}).get("start_time", 0)) / 60 if event.get("when") else 60,
                    "participants": len(event.get("participants", [])) > 1
                }
                for event in current_schedule.get("events", [])[:20]  # Limit to avoid token overflow
            ]
        }
        
        system_message = f"""You are a schedule optimization expert analyzing a user's calendar.
Current date/time: {user_context.get('current_date')} {user_context.get('current_time')} {user_context.get('timezone', 'UTC')}

Optimization request:
- Type: {optimization_request.get('optimization_type')}
- Goals: {', '.join(optimization_request.get('goals', []))}
- Time range: {optimization_request.get('time_range')}
- Preferences: {json.dumps(optimization_request.get('preferences', {}))}

Generate SPECIFIC suggestions based on the actual tasks and events in the schedule.
Your suggestions must reference specific task/event titles and times.

Analyze the schedule carefully:
- If there are genuine optimization opportunities, provide specific suggestions
- If the schedule is already well-optimized, you may return fewer or no suggestions
- Always explain your reasoning in the summary

Common optimization opportunities to look for:
- Back-to-back meetings without breaks
- High-priority tasks scheduled during low-energy times
- Fragmented focus time that could be consolidated
- Uneven workload distribution across days

For each suggestion, provide:
1. action: A clear description of what to do (e.g., "Move 'Team Standup' from Monday 9am to Tuesday 3pm")
2. command: A natural language command the user can say to execute it (e.g., "Reschedule Team Standup to Tuesday at 3pm")

Consider:
- Focus time blocks (look for gaps in the schedule)
- Meeting clustering (batch similar meetings)
- Workload distribution (balance across days)
- Priority alignment (ensure high-priority items get prime time slots)
- Energy optimization (match tasks to preferred times)

Be specific! Reference actual task/event names from the schedule."""

        try:
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=f"Current schedule:\n{json.dumps(schedule_summary, indent=2)}\n\nGenerate specific optimization suggestions.",
                tool_def=generate_suggestions_tool,
                reasoning_effort="medium",
                force_tool=True,
            )
            
            logger.info(f"AI optimization suggestions: {len(result.get('suggestions', []))} suggestions generated")
            return result
            
        except Exception as e:
            logger.error(f"OpenAI call failed: {str(e)}")
            raise
    
    
    def _parse_preferences(self, preferences: str) -> Dict[str, Any]:
        """Parse user preferences from natural language."""
        prefs = {}
        
        if not preferences:
            return prefs
        
        pref_lower = preferences.lower()
        
        # Time preferences
        if "morning" in pref_lower:
            prefs["preferred_focus_time"] = "morning"
        elif "afternoon" in pref_lower:
            prefs["preferred_focus_time"] = "afternoon"
        
        # Duration preferences
        if "2-hour" in pref_lower or "2 hour" in pref_lower:
            prefs["preferred_block_duration"] = 120
        elif "1-hour" in pref_lower or "1 hour" in pref_lower:
            prefs["preferred_block_duration"] = 60
        
        # Day preferences
        if "friday" in pref_lower and "free" in pref_lower:
            prefs["keep_free"] = ["friday_afternoon"]
        
        return prefs