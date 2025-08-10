"""AI component for understanding natural language task requests using OpenAI."""
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class TaskAI:
    """Natural language understanding for task management using OpenAI function calling.
    
    This specialized calendar AI uses OpenAI to parse complex natural language
    into structured task data that the Reclaim API can understand.
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the TaskAI with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
        
        # Define the function schema for task parsing
        self.task_parse_function = {
            "type": "function",
            "function": {
                "name": "parse_task_request",
                "description": "Parse a natural language task request into structured data",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": ["create", "update", "complete", "add_time", "find", "delete"],
                            "description": "The action the user wants to perform"
                        },
                        "task": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "The task title/description"
                                },
                                "due_date": {
                                    "type": ["string", "null"],
                                    "description": "Due date in ISO format (YYYY-MM-DDTHH:MM:SS) or null if no due date"
                                },
                                "duration_hours": {
                                    "type": ["number", "null"],
                                    "description": "Duration in hours (e.g., 2.5 for 2.5 hours) or null if no duration"
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["P1", "P2", "P3", "P4"],
                                    "description": "Priority level (P1=urgent, P2=high, P3=normal, P4=low)"
                                }
                            },
                            "required": ["title", "due_date", "duration_hours", "priority"]
                        },
                        "task_reference": {
                            "type": ["string", "null"],
                            "description": "Reference to existing task (for update/complete/add_time) or null if not applicable"
                        },
                        "updates": {
                            "anyOf": [
                                {"type": "null"},
                                {
                                    "type": "object", 
                                    "additionalProperties": False,
                                    "properties": {}
                                }
                            ],
                            "description": "Fields to update (for update intent) or null if not applicable"
                        },
                        "time_to_add": {
                            "type": ["number", "null"],
                            "description": "Hours to add to task (for add_time intent) or null if not applicable"
                        }
                    },
                    "required": ["intent", "task", "task_reference", "updates", "time_to_add"]
                },
                "strict": True
            }
        }
    
    def understand_task_request(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Understand a natural language task request using OpenAI."""
        # Prepare the system message with context
        system_message = self._build_system_message(user_context)
        
        try:
            # Call OpenAI with Responses API + function tool
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=query,
                tool_def=self.task_parse_function,
                reasoning_effort="minimal",
                force_tool=True,
            )
            
            # Post-process the result
            return self._post_process_result(result, query, user_context)
            
        except Exception as e:
            logger.error(f"Error parsing task request: {str(e)}")
            # Fallback to basic parsing
            return self._fallback_parse(query, user_context)
    
    def _build_system_message(self, user_context: Dict[str, Any]) -> str:
        """Build system message with user context."""
        timezone = user_context.get("timezone", "UTC")
        current_date = user_context.get("current_date", datetime.now().strftime("%Y-%m-%d"))
        current_time = user_context.get("current_time", datetime.now().strftime("%H:%M:%S"))
        
        return f"""You are a specialized calendar AI that parses natural language task requests.

User Context:
- Current date/time: {current_date} {current_time} {timezone}
- Timezone: {timezone}

When parsing dates:
- "today" means {current_date}
- "tomorrow" means the day after {current_date}
- "Friday" means the next Friday from today
- "next week" means Monday of next week
- "end of day" means 5 PM in the user's timezone
- All times should be in the user's timezone

When inferring priority:
- P1: urgent, critical, ASAP, immediately, blocker
- P2: important, high priority, soon
- P3: normal, regular (default)
- P4: low priority, whenever, eventually

For delete/remove/cancel operations:
- Set intent to "delete"
- Put the task description/reference in task_reference field
- Example: "Delete the budget review task" → intent="delete", task_reference="budget review task"

Always convert relative dates to absolute ISO format dates."""
    
    def _post_process_result(self, result: Dict[str, Any], query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process the OpenAI result."""
        # Add original query context
        result["context"] = {
            "original_query": query,
            "timezone": user_context.get("timezone", "UTC")
        }
        
        # Convert due_date string to datetime if present
        if result.get("task", {}).get("due_date"):
            try:
                due_str = result["task"]["due_date"]
                # Parse the ISO format date
                due_dt = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                result["task"]["due"] = due_dt
                del result["task"]["due_date"]
            except:
                pass
        
        # Rename duration_hours to duration
        if result.get("task", {}).get("duration_hours") is not None:
            result["task"]["duration"] = result["task"]["duration_hours"]
            del result["task"]["duration_hours"]
        
        return result
    
    def _fallback_parse(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Simple fallback parser if OpenAI fails."""
        query_lower = query.lower()
        
        # Determine intent
        intent = "create"  # Default
        if any(word in query_lower for word in ["complete", "done", "finish"]):
            intent = "complete"
        elif any(word in query_lower for word in ["delete", "remove", "cancel"]):
            intent = "delete"
        elif any(word in query_lower for word in ["update", "change", "modify", "push", "move"]):
            intent = "update"
        elif any(word in query_lower for word in ["add time", "add hours", "add minutes"]):
            intent = "add_time"
        
        # Extract basic title
        title = query
        for prefix in ["create task", "add task", "new task", "create a task"]:
            if query_lower.startswith(prefix):
                title = query[len(prefix):].strip()
                break
        
        # Remove "to" at the beginning
        if title.lower().startswith("to "):
            title = title[3:]
        
        # Capitalize first letter
        if title:
            title = title[0].upper() + title[1:]
        
        return {
            "intent": intent,
            "task": {
                "title": title,
                "priority": "P3"  # Default priority
            },
            "context": {
                "original_query": query,
                "timezone": user_context.get("timezone", "UTC"),
                "fallback": True
            }
        }
    
    def find_tasks_by_query(self, query: str, tasks: List[Dict[str, Any]], user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use AI to find tasks based on natural language query."""
        if not tasks:
            return []
        
        # Define the function tool for task filtering
        find_tasks_tool = {
            "type": "function",
            "function": {
                "name": "find_matching_tasks",
                "description": "Find tasks that match the user's query",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "matching_task_ids": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Array of task IDs that match the query"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Explanation of why these tasks were selected"
                        }
                    },
                    "required": ["matching_task_ids", "reasoning"]
                },
                "strict": True
            }
        }
        
        # Build a prompt for filtering
        system_message = f"""You are filtering tasks based on a user query.
User's current date/time: {user_context.get('current_date')} {user_context.get('current_time')} {user_context.get('timezone')}

Analyze the user's query and identify which tasks match their request. Consider:
- Time references (today, this week, overdue, etc.)
- Priority levels (urgent, high priority, etc.)
- Task content and titles
- Status (complete, incomplete, in progress)

Always call the find_matching_tasks function with the IDs of tasks that match."""
        
        # Create a simplified task list for the prompt
        task_summaries = []
        for task in tasks:
            summary = {
                "id": task.get("id"),
                "title": task.get("title"),
                "due": str(task.get("due")) if task.get("due") else None,
                "priority": task.get("priority"),
                "status": task.get("status")
            }
            task_summaries.append(summary)
        
        try:
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=f"Query: {query}\n\nTasks: {json.dumps(task_summaries)}",
                tool_def=find_tasks_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
            matching_ids = result.get("matching_task_ids", [])
            
            # Filter tasks by matching IDs
            return [task for task in tasks if task.get("id") in matching_ids]
            
        except Exception as e:
            logger.error(f"Error filtering tasks: {str(e)}")
            # Fallback to simple filtering
            return self._fallback_filter(query, tasks, user_context)
    
    def _fallback_filter(self, query: str, tasks: List[Dict[str, Any]], user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Simple fallback filter if AI fails."""
        query_lower = query.lower()
        
        # Filter based on common patterns
        if "today" in query_lower:
            # Return tasks due today
            today = datetime.now().date()
            return [t for t in tasks if t.get("due") and t["due"].date() == today]
        elif "overdue" in query_lower:
            # Return overdue tasks
            now = datetime.now()
            return [t for t in tasks if t.get("due") and t["due"] < now]
        elif "high priority" in query_lower or "urgent" in query_lower:
            # Return high priority tasks
            return [t for t in tasks if t.get("priority") in ["P1", "P2"]]
        else:
            # Return all tasks
            return tasks
    
    def find_single_task_for_operation(self, query: str, operation: str, tasks: List[Dict[str, Any]], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to find a single task for an operation (complete, update, cancel)."""
        
        if not tasks:
            return {"found": False, "error": "No tasks available"}
        
        # Define the function tool
        find_task_tool = {
            "type": "function",
            "function": {
                "name": "identify_task",
                "description": f"Identify which task the user wants to {operation}",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "found": {
                            "type": "boolean",
                            "description": "Whether a matching task was found"
                        },
                        "task_id": {
                            "type": ["string", "null"],
                            "description": "ID of the matching task (null if not found or ambiguous)"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-1 (1 = certain match)"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Explanation of the match or why no match found"
                        },
                        "ambiguous_matches": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": "If multiple possible matches, list their IDs"
                        }
                    },
                    "required": ["found", "task_id", "confidence", "reasoning", "ambiguous_matches"]
                },
                "strict": True
            }
        }
        
        # Build prompt
        system_message = f"""You are identifying which task the user wants to {operation}.
User's current date/time: {user_context.get('current_date')} {user_context.get('current_time')} {user_context.get('timezone')}

Guidelines:
- Match based on task content, time references, and context
- When user says "the task about X", look for tasks where X is a key topic/theme
- Example: "Delete the task about testing" should match tasks with "test" in the title
- "that task" or "the task" often refers to recently mentioned or important tasks  
- "meeting tomorrow" means a task scheduled for tomorrow that sounds like a meeting
- "budget task" could match "Review Q4 budget" or "Budget planning"
- Consider semantic matches, not just substring matches
- Require meaningful overlap between query and task content
- If multiple tasks could match, return them in ambiguous_matches
- Only return found=true with high confidence (>0.8) for operations like complete/cancel
- IMPORTANT: If user says "my task" and there are only 2-3 tasks, set ambiguous_matches with those task IDs
- Never generate custom error messages - use the reasoning field to explain why no match was found

Always call the identify_task function with your analysis."""

        # Filter out already completed tasks for complete operation
        if operation == "complete":
            active_tasks = [t for t in tasks if t.get("status") not in ["COMPLETE", "ARCHIVED", "CANCELLED"]]
        else:
            active_tasks = tasks
        
        # Create task summaries
        task_summaries = []
        for task in active_tasks:
            summary = {
                "id": str(task.get("id")),
                "title": task.get("title"),
                "due": str(task.get("due")) if task.get("due") else None,
                "priority": task.get("priority"),
                "status": task.get("status"),
                "notes": task.get("notes", "")[:100] if task.get("notes") else None
            }
            task_summaries.append(summary)
        
        try:
            user_message = f"User wants to {operation}: \"{query}\"\n\nAvailable tasks: {json.dumps(task_summaries, indent=2)}"
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=user_message,
                tool_def=find_task_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error finding task for operation: {str(e)}")
            # Fallback to simple search
            return self._fallback_single_task_search(query, active_tasks, operation)
    
    def _fallback_single_task_search(self, query: str, tasks: List[Dict[str, Any]], operation: str) -> Dict[str, Any]:
        """Fallback to simple substring matching if AI fails."""
        query_lower = query.lower()
        matches = []
        
        for task in tasks:
            if query_lower in task.get("title", "").lower():
                matches.append(task)
        
        if not matches:
            return {
                "found": False,
                "error": f"No task found matching '{query}'",
                "reasoning": "No tasks contain the search text"
            }
        elif len(matches) == 1:
            return {
                "found": True,
                "task_id": str(matches[0].get("id")),
                "confidence": 0.9,
                "reasoning": f"Found exact match: {matches[0].get('title')}"
            }
        else:
            return {
                "found": False,
                "task_id": None,
                "confidence": 0.5,
                "reasoning": f"Multiple tasks match '{query}'",
                "ambiguous_matches": [str(m.get("id")) for m in matches[:5]]
            }
    
    def find_single_event_for_operation(self, query: str, operation: str, events: List[Dict[str, Any]], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to find a single event for an operation (update, cancel)."""
        if not events:
            return {"found": False, "error": "No events available"}
        
        # Define the function tool
        find_event_tool = {
            "type": "function",
            "function": {
                "name": "identify_event",
                "description": f"Identify which event the user wants to {operation}",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "found": {
                            "type": "boolean",
                            "description": "Whether a matching event was found"
                        },
                        "event_id": {
                            "type": ["string", "null"],
                            "description": "ID of the matching event (null if not found or ambiguous)"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-1 (1 = certain match)"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Explanation of the match or why no match found"
                        },
                        "ambiguous_matches": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": "If multiple possible matches, list their IDs"
                        }
                    },
                    "required": ["found", "event_id", "confidence", "reasoning", "ambiguous_matches"]
                },
                "strict": True
            }
        }
        
        # Build prompt
        system_message = f"""You are identifying which calendar event the user wants to {operation}.
User's current date/time: {user_context.get('current_date')} {user_context.get('current_time')} {user_context.get('timezone')}

Guidelines:
- Match based on event content, time references, and context
- "that meeting" or "the meeting" often refers to recently mentioned or upcoming meetings
- "meeting tomorrow" means an event scheduled for tomorrow
- "standup" could match "Team Standup", "Daily Standup", etc.
- Consider partial matches and context clues
- Time context is important - "meeting at 2pm" means the 2pm meeting
- If multiple events could match, return them in ambiguous_matches
- Only return found=true with high confidence (>0.8) for operations

Always call the identify_event function with your analysis."""

        # Create event summaries
        event_summaries = []
        for event in events:
            summary = {
                "id": event.get("id"),
                "title": event.get("title"),
                "start_time": event.get("start_time"),
                "end_time": event.get("end_time"),
                "location": event.get("location"),
                "description": (event.get("description") or "")[:100] if event.get("description") else None,
                "participants": event.get("participants", [])
            }
            event_summaries.append(summary)
        
        try:
            from src.ai.openai_utils import call_function_tool
            user_text = f"User wants to {operation}: \"{query}\"\n\nAvailable events: {json.dumps(event_summaries, indent=2)}"
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=user_text,
                tool_def=find_event_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
            return result
            
        except Exception as e:
            logger.error(f"Error finding event for operation: {str(e)}")
            # Fallback to simple search
            return self._fallback_single_event_search(query, events, operation)
    
    def _fallback_single_event_search(self, query: str, events: List[Dict[str, Any]], operation: str) -> Dict[str, Any]:
        """Fallback to simple substring matching for events if AI fails."""
        query_lower = query.lower()
        matches = []
        
        for event in events:
            if query_lower in event.get("title", "").lower():
                matches.append(event)
        
        if not matches:
            return {
                "found": False,
                "error": f"No event found matching '{query}'",
                "reasoning": "No events contain the search text"
            }
        elif len(matches) == 1:
            return {
                "found": True,
                "event_id": matches[0].get("id"),
                "confidence": 0.9,
                "reasoning": f"Found exact match: {matches[0].get('title')}"
            }
        else:
            return {
                "found": False,
                "event_id": None,
                "confidence": 0.5,
                "reasoning": f"Multiple events match '{query}'",
                "ambiguous_matches": [m.get("id") for m in matches[:5]]
            }
    
    def understand_query(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Understand a query for finding and analyzing tasks."""
        query_lower = query.lower()
        
        # Determine query type
        analysis_keywords = ['workload', 'productivity', 'analysis', 'insights', 'trends', 'how\'s', 'am i']
        find_keywords = ['show', 'find', 'what', 'list', 'get', 'display']
        
        is_analysis = any(keyword in query_lower for keyword in analysis_keywords)
        is_find = any(keyword in query_lower for keyword in find_keywords)
        
        if is_analysis and is_find:
            query_type = 'mixed'
        elif is_analysis:
            query_type = 'analyze'
        else:
            query_type = 'find'
        
        # Extract filters
        time_filter = None
        if 'today' in query_lower:
            time_filter = 'today'
        elif 'overdue' in query_lower:
            time_filter = 'overdue'
        elif 'this week' in query_lower:
            time_filter = 'this_week'
        elif 'upcoming' in query_lower:
            time_filter = 'upcoming'
        
        priority_filter = None
        if 'high priority' in query_lower or 'urgent' in query_lower:
            priority_filter = 'high'
        elif 'low priority' in query_lower:
            priority_filter = 'low'
        
        status_filter = None
        if 'complete' in query_lower or 'done' in query_lower:
            status_filter = 'complete'
        elif 'incomplete' in query_lower or 'pending' in query_lower:
            status_filter = 'incomplete'
        elif 'in progress' in query_lower:
            status_filter = 'in_progress'
        
        # Extract search terms
        search_terms = []
        # Simple approach: extract quoted terms or project names
        words = query.split()
        for i, word in enumerate(words):
            if word.lower() in ['about', 'for', 'regarding', 'on'] and i + 1 < len(words):
                search_terms.append(words[i + 1])
        
        return {
            'type': query_type,
            'time_filter': time_filter,
            'priority_filter': priority_filter,
            'status_filter': status_filter,
            'search_terms': search_terms
        }
    
    def understand_scheduling_request(self, request: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Understand a scheduling optimization request."""
        request_lower = request.lower()
        
        # Determine request type
        if 'find time' in request_lower or 'schedule' in request_lower:
            request_type = 'find_time'
        elif 'balance' in request_lower or 'distribute' in request_lower:
            request_type = 'balance_workload'
        elif 'focus' in request_lower or 'deep work' in request_lower:
            request_type = 'optimize_focus'
        elif 'urgent' in request_lower or 'priority' in request_lower or 'asap' in request_lower:
            request_type = 'prioritize_urgent'
        else:
            request_type = 'general'
        
        # Extract duration
        duration = 2.0  # Default
        if 'hour' in request_lower:
            import re
            duration_match = re.search(r'(\d+(?:\.\d+)?)\s*hours?', request_lower)
            if duration_match:
                duration = float(duration_match.group(1))
        
        # Extract time frame
        time_frame = 'this_week'  # Default
        if 'tomorrow' in request_lower:
            time_frame = 'tomorrow'
        elif 'today' in request_lower:
            time_frame = 'today'
        elif 'next week' in request_lower:
            time_frame = 'next_week'
        
        return {
            'type': request_type,
            'duration': duration,
            'time_frame': time_frame,
            'preferences': user_context.get('preferences', '')
        }