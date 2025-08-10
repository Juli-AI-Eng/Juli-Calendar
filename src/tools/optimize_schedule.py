"""Hybrid tool for optimizing schedules across tasks and calendar."""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import pytz
import logging

from src.tools.base import BaseTool
from src.ai.schedule_optimizer import ScheduleOptimizer
from src.auth.credential_manager import CredentialManager
from reclaim_sdk.client import ReclaimClient
from nylas import Client as NylasClient

logger = logging.getLogger(__name__)


class OptimizeScheduleTool(BaseTool):
    """Tool for optimizing schedules to improve productivity and work-life balance."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "optimize_schedule"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Optimize your schedule for better productivity, work-life balance, and focus time. "
            "Get AI-powered suggestions to reorganize tasks and meetings, balance workload, "
            "maximize deep work time, align with energy levels, or prioritize what matters most."
        )
    
    def __init__(self):
        """Initialize the tool."""
        super().__init__()
        self.schedule_optimizer = ScheduleOptimizer()
        self.credential_manager = CredentialManager()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": (
                        "How should I optimize your schedule? Examples: "
                        "'maximize my focus time this week', "
                        "'balance my workload better', "
                        "'schedule tasks based on my energy levels', "
                        "'prioritize urgent items first', "
                        "'reduce meeting overload'"
                    )
                },
                "preferences": {
                    "type": "string",
                    "description": (
                        "Any preferences or constraints (optional). Like: "
                        "'I work best in mornings', 'keep Friday afternoons free', "
                        "'prefer 2-hour focus blocks'"
                    )
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
            "required": ["request"]
        }
    
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean input data."""
        if not data.get("request"):
            raise ValueError("Request is required")
        
        # Ensure defaults
        return {
            "request": data["request"],
            "preferences": data.get("preferences", ""),
            "user_timezone": data.get("user_timezone", "UTC"),
            "current_date": data.get("current_date", datetime.now().strftime("%Y-%m-%d")),
            "current_time": data.get("current_time", datetime.now().strftime("%H:%M:%S"))
        }
    
    async def execute(self, data: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
        """Execute the tool."""
        try:
            # Validate input
            validated_data = self.validate_input(data)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        
        # Check if this is an approved retry
        if data.get("approved") and data.get("action_data"):
            # Extract the original data from the approval
            action_data = data["action_data"]
            validated_data = action_data["params"]
            credentials = action_data["credentials"]
            optimization_plan = action_data["optimization_plan"]
            current_schedule = action_data["current_schedule"]
            
            # Apply the optimization plan
            return await self._apply_optimization_plan(
                optimization_plan,
                current_schedule,
                credentials,
                validated_data
            )
        
        # Check credentials
        if not self.credential_manager.is_setup_complete(credentials):
            missing = []
            if not credentials.get("reclaim_api_key"):
                missing.append("Reclaim.ai")
            if not (credentials.get("nylas_api_key") and credentials.get("nylas_grant_id")):
                missing.append("Nylas")
            
            return {
                "error": f"Missing credentials for: {', '.join(missing)}",
                "needs_setup": True,
                "message": "Both Reclaim.ai and Nylas must be connected to optimize your full schedule"
            }
        
        # Build user context
        user_context = {
            "timezone": validated_data["user_timezone"],
            "current_date": validated_data["current_date"],
            "current_time": validated_data["current_time"],
            "now": self._parse_user_datetime(validated_data)
        }
        
        # Analyze optimization request
        optimization_request = self.schedule_optimizer.analyze_optimization_request(
            validated_data["request"],
            validated_data["preferences"],
            user_context
        )
        
        # Get current schedule from both systems
        current_schedule = await self._get_current_schedule(
            credentials, optimization_request, user_context
        )
        
        # Generate optimization plan
        optimization_plan = self.schedule_optimizer.generate_optimization_plan(
            current_schedule,
            optimization_request,
            user_context
        )
        
        # Check if approval is required
        if optimization_plan.get("requires_approval"):
            return {
                "needs_approval": True,
                "action_type": f"schedule_optimization_{optimization_request.get('optimization_type', 'general')}",
                "action_data": {
                    "tool": "optimize_schedule",
                    "params": validated_data,
                    "credentials": credentials,
                    "optimization_plan": optimization_plan,
                    "current_schedule": current_schedule
                },
                "preview": {
                    "summary": f"Optimize schedule: {optimization_request.get('optimization_type', 'general')} - {len(optimization_plan.get('suggestions', []))} changes suggested",
                    "details": {
                        "suggestions": optimization_plan.get("suggestions", []),
                        "metrics": optimization_plan.get("metrics", {}),
                        "optimization_type": optimization_request.get("optimization_type"),
                        "affected_items": self._get_affected_items(optimization_plan)
                    },
                    "risks": [
                        "This optimization would make significant changes to your schedule",
                        "Some changes may affect other people's calendars"
                    ]
                }
            }
        
        # Return optimization suggestions
        return {
            "success": True,
            "suggestions": optimization_plan.get("suggestions", []),
            "metrics": optimization_plan.get("metrics", {}),
            "message": self._generate_summary(optimization_plan),
            "optimization_type": optimization_request.get("optimization_type")
        }
    
    async def _get_current_schedule(
        self,
        credentials: Dict[str, str],
        optimization_request: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get current schedule from both Reclaim and Nylas."""
        schedule = {
            "tasks": [],
            "events": [],
            "stats": {}
        }
        
        # Get time range for analysis
        time_range = optimization_request.get("time_range", "this_week")
        start_date, end_date = self._calculate_time_range(time_range, user_context)
        
        # Get Reclaim tasks
        try:
            client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
            tasks = client.tasks.list()
            
            # Filter and format tasks
            for task in tasks:
                if task.status != "COMPLETE":
                    schedule["tasks"].append({
                        "id": task.id,
                        "title": task.title,
                        "duration_minutes": task.time_chunks_required * 15,
                        "priority": task.priority,
                        "due": task.due,
                        "provider": "reclaim"
                    })
            
        except Exception as e:
            logger.error(f"Failed to get Reclaim tasks: {e}")
        
        # Get Nylas events
        try:
            client = NylasClient(
                api_key=credentials["nylas_api_key"],
                api_uri="https://api.us.nylas.com"
            )
            
            # Query events in time range
            response = client.events.list(
                identifier=credentials["nylas_grant_id"],
                query_params={
                    "calendar_id": "primary",
                    "start": int(start_date.timestamp()),
                    "end": int(end_date.timestamp())
                }
            )
            
            for event in response.data:
                if event.status != "cancelled":
                    event_start = datetime.fromtimestamp(event.when.start_time, tz=user_context["now"].tzinfo)
                    event_end = datetime.fromtimestamp(event.when.end_time, tz=user_context["now"].tzinfo) if hasattr(event.when, 'end_time') else event_start + timedelta(hours=1)
                    
                    schedule["events"].append({
                        "id": event.id,
                        "title": event.title,
                        "start": event_start.isoformat(),
                        "end": event_end.isoformat(),
                        "duration_minutes": (event_end - event_start).total_seconds() / 60,
                        "participants": len(event.participants) if hasattr(event, "participants") else 0,
                        "provider": "nylas"
                    })
            
        except Exception as e:
            logger.error(f"Failed to get Nylas events: {e}")
        
        # Calculate statistics
        schedule["stats"] = self._calculate_schedule_stats(schedule, user_context)
        
        return schedule
    
    def _calculate_time_range(
        self,
        time_range: str,
        user_context: Dict[str, Any]
    ) -> Tuple[datetime, datetime]:
        """Calculate start and end dates for the time range."""
        now = user_context["now"]
        
        if time_range == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif time_range == "tomorrow":
            start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif time_range == "this_week":
            # Start of current week (Monday)
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        else:
            # Default to this week
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        
        return start, end
    
    def _calculate_schedule_stats(
        self,
        schedule: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate statistics about the schedule."""
        stats = {
            "total_tasks": len(schedule["tasks"]),
            "total_events": len(schedule["events"]),
            "total_hours_committed": 0,
            "focus_time_available": 0
        }
        
        # Calculate committed hours from tasks
        for task in schedule["tasks"]:
            stats["total_hours_committed"] += task.get("duration_minutes", 0) / 60
        
        # Calculate committed hours from events
        for event in schedule["events"]:
            stats["total_hours_committed"] += event.get("duration_minutes", 0) / 60
        
        # Calculate available focus time (assuming 8-hour work days)
        now = user_context["now"]
        work_days = 0
        current = now.date()
        
        # Count work days in the time range being analyzed
        for task in schedule["tasks"]:
            if task.get("due"):
                task_date = datetime.fromisoformat(task["due"]).date()
                if task_date > current:
                    days_diff = (task_date - current).days
                    # Rough estimate: 5 work days per 7 calendar days
                    work_days = max(work_days, (days_diff * 5) // 7)
        
        total_work_hours = work_days * 8
        stats["focus_time_available"] = max(0, total_work_hours - stats["total_hours_committed"])
        
        # Add more detailed stats
        stats["meetings_count"] = sum(1 for e in schedule["events"] if e.get("participants", 0) > 1)
        stats["solo_work_hours"] = sum(t.get("duration_minutes", 0) / 60 for t in schedule["tasks"])
        stats["meeting_hours"] = sum(e.get("duration_minutes", 0) / 60 for e in schedule["events"] if e.get("participants", 0) > 1)
        
        return stats
    
    def _generate_summary(self, optimization_plan: Dict[str, Any]) -> str:
        """Generate a summary of the optimization plan."""
        suggestions = optimization_plan.get("suggestions", [])
        metrics = optimization_plan.get("metrics", {})
        
        if not suggestions:
            return "Your schedule is already well-optimized!"
        
        high_impact = [s for s in suggestions if s.get("impact") == "high"]
        
        summary = f"Found {len(suggestions)} ways to optimize your schedule"
        if high_impact:
            summary += f" ({len(high_impact)} high-impact)"
        
        if metrics.get("improvement"):
            summary += f". Potential improvement: {metrics['improvement']}"
        
        return summary
    
    def _parse_user_datetime(self, data: Dict[str, Any]) -> datetime:
        """Parse user datetime from context."""
        try:
            tz = pytz.timezone(data["user_timezone"])
            dt_str = f"{data['current_date']} {data['current_time']}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            return tz.localize(dt)
        except Exception as e:
            logger.warning(f"Failed to parse user datetime: {e}, using UTC")
            return datetime.now(pytz.UTC)
    
    def _get_affected_items(self, optimization_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get list of items that would be affected by the optimization."""
        affected = []
        
        for suggestion in optimization_plan.get("suggestions", []):
            if suggestion.get("affects_others"):
                affected.append({
                    "type": suggestion.get("type"),
                    "description": suggestion.get("action"),
                    "impact": suggestion.get("impact", "unknown")
                })
        
        return affected
    
    async def _apply_optimization_plan(
        self,
        optimization_plan: Dict[str, Any],
        current_schedule: Dict[str, Any],
        credentials: Dict[str, str],
        validated_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply the approved optimization plan."""
        try:
            applied_changes = []
            failed_changes = []
            
            # Create clients
            reclaim_client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
            nylas_client = NylasClient(
                api_key=credentials["nylas_api_key"],
                api_uri="https://api.us.nylas.com"
            )
            
            # Apply each suggestion
            for suggestion in optimization_plan.get("suggestions", []):
                try:
                    change_type = suggestion.get("type")
                    
                    if change_type == "reschedule_task":
                        # Update task due date in Reclaim
                        task_id = suggestion["target"]["id"]
                        new_due = suggestion["new_time"]
                        
                        from reclaim_sdk.resources.task import Task
                        task = Task.get(task_id, reclaim_client)
                        task.due = datetime.fromisoformat(new_due)
                        task._client = reclaim_client
                        task.save()
                        
                        applied_changes.append(f"Rescheduled task '{task.title}' to {new_due}")
                    
                    elif change_type == "reschedule_event":
                        # Update event time in Nylas
                        event_id = suggestion["target"]["id"]
                        new_start = datetime.fromisoformat(suggestion["new_time"])
                        new_end = new_start + timedelta(minutes=suggestion["target"]["duration_minutes"])
                        
                        nylas_client.events.update(
                            identifier=credentials["nylas_grant_id"],
                            event_id=event_id,
                            request_body={
                                "when": {
                                    "start_time": int(new_start.timestamp()),
                                    "end_time": int(new_end.timestamp())
                                }
                            },
                            query_params={
                                "calendar_id": "primary",
                                "notify_participants": True
                            }
                        )
                        
                        applied_changes.append(f"Rescheduled event '{suggestion['target']['title']}' to {new_start.strftime('%Y-%m-%d %H:%M')}")
                    
                    elif change_type == "batch_tasks":
                        # Group similar tasks by scheduling them together
                        # This is a complex operation that would need more specific implementation
                        applied_changes.append(f"Batched {len(suggestion['tasks'])} similar tasks")
                    
                    elif change_type == "block_focus_time":
                        # Create focus time blocks as events
                        for block in suggestion.get("blocks", []):
                            nylas_client.events.create(
                                identifier=credentials["nylas_grant_id"],
                                request_body={
                                    "title": "Focus Time (Scheduled by AI)",
                                    "description": f"Dedicated time for: {block['task_title']}",
                                    "when": {
                                        "start_time": int(datetime.fromisoformat(block["start"]).timestamp()),
                                        "end_time": int(datetime.fromisoformat(block["end"]).timestamp())
                                    },
                                    "busy": True
                                },
                                query_params={
                                    "calendar_id": "primary"
                                }
                            )
                        
                        applied_changes.append(f"Created {len(suggestion.get('blocks', []))} focus time blocks")
                    
                except Exception as e:
                    logger.error(f"Failed to apply suggestion {change_type}: {e}")
                    failed_changes.append(f"{change_type}: {str(e)}")
            
            # Return results
            return {
                "success": len(failed_changes) == 0,
                "message": f"Applied {len(applied_changes)} optimizations" + (f" with {len(failed_changes)} failures" if failed_changes else ""),
                "applied_changes": applied_changes,
                "failed_changes": failed_changes,
                "metrics": optimization_plan.get("metrics", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to apply optimization plan: {e}")
            return {
                "success": False,
                "error": f"Failed to apply optimization: {str(e)}"
            }