"""Manage tasks tool for natural language task management."""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from src.tools.base import BaseTool
from src.ai.task_ai import TaskAI
from reclaim_sdk.client import ReclaimClient
from reclaim_sdk.resources.task import Task, TaskStatus
import logging

logger = logging.getLogger(__name__)


class ManageTasksTool(BaseTool):
    """Tool for managing tasks through natural language."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "manage_tasks"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return "Create, update, complete, or manage your tasks naturally. Just tell me what you need!"
    
    def __init__(self):
        """Initialize the manage tasks tool."""
        super().__init__()
        self.task_ai = TaskAI()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What do you want to do? Examples: 'create a task to review Q4 budget by Friday', 'mark the client presentation as complete', 'push the code review to next week', 'add 2 more hours to the design task'"
                },
                "task_context": {
                    "type": "string",
                    "description": "Any additional context about the task (optional)"
                },
                "user_timezone": {
                    "type": "string",
                    "description": "User's timezone from context injection",
                    "x-context-injection": "user_timezone"
                },
                "current_date": {
                    "type": "string", 
                    "description": "Current date in user's timezone",
                    "x-context-injection": "current_date"
                },
                "current_time": {
                    "type": "string",
                    "description": "Current time in user's timezone",
                    "x-context-injection": "current_time"
                }
            },
            "required": ["query"]
        }
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean input data."""
        if not data.get("query"):
            raise ValueError("Query is required")
        
        # Ensure we have default values for context
        return {
            "query": data["query"],
            "task_context": data.get("task_context", ""),
            "user_timezone": data.get("user_timezone", "UTC"),
            "current_date": data.get("current_date", datetime.now().strftime("%Y-%m-%d")),
            "current_time": data.get("current_time", datetime.now().strftime("%H:%M:%S"))
        }
    
    async def execute(self, data: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
        """Execute the manage tasks tool."""
        # Extract API key
        api_key = (
            credentials.get("reclaim_api_key") or 
            credentials.get("RECLAIM_API_KEY") or
            credentials.get("Reclaim-Api-Key") or
            credentials.get("reclaim-api-key")
        )
        
        if not api_key:
            return {
                "error": "Reclaim API key not found",
                "needs_setup": True
            }
        
        # Build user context
        user_context = {
            "timezone": data["user_timezone"],
            "current_date": data["current_date"],
            "current_time": data["current_time"],
            "now": self._parse_user_datetime(data)
        }
        
        try:
            # Use AI to understand the request
            understanding = self.task_ai.understand_task_request(
                data["query"], 
                user_context
            )
            
            # Create Reclaim client
            client = ReclaimClient.configure(token=api_key)
            
            # Execute based on intent
            intent = understanding.get("intent")
            
            if intent == "create":
                return await self._create_task(understanding, client)
            elif intent == "update":
                return await self._update_task(understanding, client)
            elif intent == "complete":
                return await self._complete_task(understanding, client)
            elif intent == "add_time":
                return await self._add_time_to_task(understanding, client)
            else:
                return {
                    "error": f"Unknown intent: {intent}",
                    "understanding": understanding
                }
                
        except Exception as e:
            logger.error(f"Error executing manage_tasks: {str(e)}")
            return {
                "error": str(e),
                "success": False
            }
    
    def _find_task_by_reference(self, task_ref: str, client: ReclaimClient) -> Tuple[Optional[Task], Optional[Dict[str, Any]]]:
        """Find a task by reference string.
        
        Returns:
            Tuple of (task, error_dict). If task is found, error_dict is None.
            If error, task is None and error_dict contains error info.
        """
        try:
            # Get all tasks
            all_tasks = Task.list(client)
            
            # Filter tasks to find matches
            matching_tasks = []
            for task in all_tasks:
                if task.status not in [TaskStatus.COMPLETE, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]:
                    # Check if task reference matches task title
                    if task_ref.lower() in task.title.lower():
                        matching_tasks.append(task)
            
            if not matching_tasks:
                return None, {
                    "success": False,
                    "error": f"No tasks found matching '{task_ref}'",
                    "suggestion": "Try being more specific about the task name"
                }
            
            if len(matching_tasks) > 1:
                return None, {
                    "success": False,
                    "error": f"Multiple tasks found matching '{task_ref}'",
                    "matches": [{"id": t.id, "title": t.title, "due": str(t.due) if t.due else None} 
                               for t in matching_tasks[:5]],
                    "suggestion": "Please be more specific about which task you mean"
                }
            
            return matching_tasks[0], None
            
        except Exception as e:
            return None, {
                "success": False,
                "error": str(e),
                "task_reference": task_ref
            }
    
    def _parse_user_datetime(self, data: Dict[str, Any]) -> datetime:
        """Parse user's current datetime from context."""
        import pytz
        
        try:
            tz = pytz.timezone(data.get("user_timezone", "UTC"))
        except pytz.exceptions.UnknownTimeZoneError:
            tz = pytz.UTC
        
        dt_str = f"{data.get('current_date', '')} {data.get('current_time', '')}"
        
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            return tz.localize(dt)
        except:
            return datetime.now(pytz.UTC)
    
    async def _create_task(self, understanding: Dict[str, Any], client: ReclaimClient) -> Dict[str, Any]:
        """Create a new task."""
        task_data = understanding.get("task", {})
        
        # Create task through Reclaim API
        task = Task(
            title=task_data.get("title", "New Task"),
            priority=task_data.get("priority", "P3"),
            duration=task_data.get("duration", 1.0),
            due=task_data.get("due"),
            status="NEW"
        )
        
        try:
            created_task = client.tasks.create(task)
            return {
                "success": True,
                "action": "created",
                "task": {
                    "id": created_task.id,
                    "title": created_task.title,
                    "due": str(created_task.due) if created_task.due else None,
                    "priority": created_task.priority,
                    "duration": created_task.duration
                },
                "message": f"Created task: {created_task.title}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task_data": task_data
            }
    
    async def _update_task(self, understanding: Dict[str, Any], client: ReclaimClient) -> Dict[str, Any]:
        """Update an existing task."""
        task_ref = understanding.get("task_reference")
        updates = understanding.get("updates", {})
        
        # Find the task
        task, error = self._find_task_by_reference(task_ref, client)
        if error:
            return error
        
        try:
            
            # Apply updates
            if "title" in updates:
                task.title = updates["title"]
            if "priority" in updates:
                task.priority = updates["priority"]
            if "due" in updates:
                task.due = updates["due"]
            if "duration" in updates:
                task.duration = updates["duration"]
            
            # Save the task
            task.save()
            
            return {
                "success": True,
                "action": "updated",
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "due": str(task.due) if task.due else None,
                    "priority": task.priority,
                    "duration": task.duration
                },
                "message": f"Updated task: {task.title}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task_reference": task_ref
            }
    
    async def _complete_task(self, understanding: Dict[str, Any], client: ReclaimClient) -> Dict[str, Any]:
        """Complete a task."""
        task_ref = understanding.get("task_reference")
        
        # Find the task
        task, error = self._find_task_by_reference(task_ref, client)
        if error:
            return error
        
        try:
            task.mark_complete()
            
            return {
                "success": True,
                "action": "completed",
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "completed_at": str(task.finished) if task.finished else str(datetime.now())
                },
                "message": f"Completed task: {task.title}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task_reference": task_ref
            }
    
    async def _add_time_to_task(self, understanding: Dict[str, Any], client: ReclaimClient) -> Dict[str, Any]:
        """Add time to a task."""
        task_ref = understanding.get("task_reference")
        time_to_add = understanding.get("time_to_add", 0)
        
        # Find the task
        task, error = self._find_task_by_reference(task_ref, client)
        if error:
            return error
        
        try:
            old_duration = task.duration or 0
            task.add_time(time_to_add)
            
            return {
                "success": True,
                "action": "added_time",
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "old_duration": old_duration,
                    "new_duration": task.duration,
                    "time_added": time_to_add
                },
                "message": f"Added {time_to_add} hours to task: {task.title}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "task_reference": task_ref
            }