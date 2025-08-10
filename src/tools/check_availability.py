"""Hybrid tool for checking availability across tasks and calendar."""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import pytz
import logging

from src.tools.base import BaseTool
from src.ai.availability_checker import AvailabilityChecker
from src.ai.date_parser import DateParser
from src.auth.credential_manager import CredentialManager
from reclaim_sdk.client import ReclaimClient
from nylas import Client as NylasClient

logger = logging.getLogger(__name__)


class CheckAvailabilityTool(BaseTool):
    """Tool for checking availability and finding free time slots."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "check_availability"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Check your availability and find free time slots. Ask if you're free at specific times, "
            "find available slots for meetings or focused work, check for conflicts, "
            "or get suggestions for the best times to schedule activities."
        )
    
    def __init__(self):
        """Initialize the tool."""
        super().__init__()
        self.availability_checker = AvailabilityChecker()
        self.date_parser = DateParser()
        self.credential_manager = CredentialManager()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What availability do you want to check? Examples: "
                        "'am I free tomorrow at 2pm?', "
                        "'find 2 hours for deep work this week', "
                        "'when can I schedule a 1-hour meeting?', "
                        "'do I have time this afternoon?'"
                    )
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration needed in minutes (if not specified in query)"
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
        
        # Ensure defaults
        return {
            "query": data["query"],
            "duration_minutes": data.get("duration_minutes", 60),  # Default 1 hour
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
        except Exception as e:
            logger.error(f"Error in check_availability.execute: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Validation error: {str(e)}"
            }
        
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
                "message": "Both Reclaim.ai and Nylas must be connected to check availability across your full schedule"
            }
        
        # Build user context
        user_context = {
            "timezone": validated_data["user_timezone"],
            "current_date": validated_data["current_date"],
            "current_time": validated_data["current_time"],
            "now": self._parse_user_datetime(validated_data)
        }
        
        # Analyze availability query
        availability_request = self.availability_checker.analyze_availability_query(
            validated_data["query"],
            user_context,
            validated_data["duration_minutes"]
        )
        
        # Handle errors from AI analysis
        if availability_request.get("type") == "error":
            return {
                "success": False,
                "error": availability_request.get("error", "Failed to analyze query"),
                "message": availability_request.get("message", "I had trouble understanding your request.")
            }
        
        # Handle different types of availability checks
        if availability_request["type"] == "specific_time":
            return await self._check_specific_time(
                credentials, availability_request, user_context
            )
        elif availability_request["type"] == "find_slots":
            return await self._find_time_slots(
                credentials, availability_request, user_context
            )
        else:
            return {
                "success": False,
                "error": f"Unknown availability check type: {availability_request['type']}"
            }
    
    async def _check_specific_time(
        self,
        credentials: Dict[str, str],
        request: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if a specific time is available."""
        start_time = request["datetime"]
        end_time = start_time + timedelta(minutes=request["duration_minutes"])
        
        # Get conflicts from both systems
        conflicts = await self._get_conflicts(
            credentials, start_time, end_time, user_context
        )
        
        available = len(conflicts) == 0
        
        return {
            "success": True,
            "available": available,
            "conflicts": conflicts,
            "requested_time": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_minutes": request["duration_minutes"]
            },
            "message": (
                f"You are {'available' if available else 'not available'} "
                f"at {start_time.strftime('%I:%M %p on %A, %B %d')}"
            )
        }
    
    async def _find_time_slots(
        self,
        credentials: Dict[str, str],
        request: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Find available time slots."""
        duration_minutes = request["duration_minutes"]
        time_range = request.get("time_range", "this_week")
        # Normalize preferences: tests may pass a list like ["morning"]. Convert to dict flags.
        raw_prefs = request.get("preferences", {})
        if isinstance(raw_prefs, list):
            preferences = {
                "prefer_morning": any("morning" in str(p).lower() for p in raw_prefs),
                "prefer_afternoon": any("afternoon" in str(p).lower() for p in raw_prefs),
                "prefer_evening": any("evening" in str(p).lower() for p in raw_prefs),
            }
        elif isinstance(raw_prefs, dict):
            preferences = raw_prefs
        else:
            preferences = {}
        
        # Calculate search time range
        start_date, end_date = self._calculate_time_range(time_range, user_context)
        
        # Get busy times from both systems
        busy_times = await self._get_busy_times(credentials, start_date, end_date, user_context)
        
        # Find available slots
        available_slots = self._calculate_available_slots(
            start_date, end_date, busy_times, duration_minutes, preferences, user_context
        )
        
        # Sort by preference and limit results
        available_slots.sort(key=lambda s: s["confidence"], reverse=True)
        top_slots = available_slots[:5]  # Return top 5 slots
        
        return {
            "success": True,
            "slots": top_slots,
            "duration_minutes": duration_minutes,
            "time_range": time_range,
            "message": f"Found {len(top_slots)} available slots for {duration_minutes} minutes"
        }
    
    async def _get_conflicts(
        self,
        credentials: Dict[str, str],
        start_time: datetime,
        end_time: datetime,
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get conflicts from both Reclaim and Nylas."""
        conflicts = []
        
        # Check Reclaim tasks
        try:
            client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
            tasks = client.tasks.list()
            
            # Ensure tasks is a list
            if not isinstance(tasks, list):
                logger.warning(f"Expected list of tasks, got {type(tasks)}")
                tasks = []
            
            # Check for task conflicts
            for task in tasks:
                if task.status in ["SCHEDULED", "IN_PROGRESS"]:
                    # Check if task has scheduled instances that conflict
                    # Tasks in Reclaim have time chunks that might overlap
                    if hasattr(task, "instances") and task.instances:
                        for instance in task.instances:
                            # Instances can be dicts or objects with attributes
                            if isinstance(instance, dict):
                                instance_start = instance.get("start")
                                instance_end = instance.get("end")
                            else:
                                instance_start = getattr(instance, "start", None)
                                instance_end = getattr(instance, "end", None)
                            
                            if instance_start and instance_end:
                                # Check if times overlap
                                if (instance_start < end_time and instance_end > start_time):
                                    conflicts.append({
                                        "type": "task",
                                        "provider": "reclaim",
                                        "title": task.title,
                                        "start": instance_start.isoformat(),
                                        "end": instance_end.isoformat(),
                                        "id": task.id
                                    })
            
        except Exception as e:
            logger.error(f"Failed to check Reclaim conflicts: {e}")
        
        # Check Nylas events
        try:
            client = NylasClient(
                api_key=credentials["nylas_api_key"],
                api_uri="https://api.us.nylas.com"
            )
            
            # Query events in the time range
            events = client.events.list(
                identifier=credentials["nylas_grant_id"],
                query_params={
                    "calendar_id": "primary",
                    "start": int(start_time.timestamp()),
                    "end": int(end_time.timestamp())
                }
            )
            
            # Handle both list and object with data attribute
            event_list = events.data if hasattr(events, 'data') else events
            if not isinstance(event_list, list):
                logger.warning(f"Expected list of events, got {type(event_list)}")
                event_list = []
            
            for event in event_list:
                if event.status != "cancelled":
                    event_start = datetime.fromtimestamp(event.when.start_time, tz=user_context["now"].tzinfo)
                    event_end = datetime.fromtimestamp(event.when.end_time, tz=user_context["now"].tzinfo) if hasattr(event.when, "end_time") else event_start + timedelta(hours=1)
                    
                    conflicts.append({
                        "type": "event",
                        "provider": "nylas",
                        "title": event.title,
                        "start": event_start.isoformat(),
                        "end": event_end.isoformat(),
                        "id": event.id,
                        "participants": len(event.participants) if hasattr(event, "participants") else 0
                    })
            
        except Exception as e:
            logger.error(f"Failed to check Nylas conflicts: {e}")
        
        return conflicts
    
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
    
    def _calculate_time_range(
        self,
        time_range: str,
        user_context: Dict[str, Any]
    ) -> Tuple[datetime, datetime]:
        """Calculate start and end dates for the time range."""
        now = user_context["now"]
        
        # Handle common cases quickly
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
        elif time_range == "next_week":
            # Start of next week
            start = now - timedelta(days=now.weekday()) + timedelta(days=7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        else:
            # Use DateParser for natural language time ranges
            try:
                # Try to parse the time range as a specific date/time
                parsed_date = self.date_parser.parse_date(time_range, user_context)
                if parsed_date:
                    # If it's a specific date, search that day
                    start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end = start + timedelta(days=1)
                else:
                    # If we can't parse it, default to next 7 days
                    logger.warning(f"Could not parse time range '{time_range}', defaulting to next 7 days")
                    start = now
                    end = now + timedelta(days=7)
            except Exception as e:
                logger.error(f"Error parsing time range '{time_range}': {e}")
                # Default to next 7 days
                start = now
                end = now + timedelta(days=7)
        
        return start, end
    
    async def _get_busy_times(
        self,
        credentials: Dict[str, str],
        start_date: datetime,
        end_date: datetime,
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get all busy times from both Reclaim and Nylas."""
        busy_times = []
        
        # Get Reclaim task scheduled times
        try:
            client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
            tasks = client.tasks.list()
            
            # Ensure tasks is a list
            if not isinstance(tasks, list):
                logger.warning(f"Expected list of tasks, got {type(tasks)}")
                tasks = []
            
            for task in tasks:
                if task.status in ["SCHEDULED", "IN_PROGRESS"]:
                    # Add task scheduled time blocks
                    # Tasks have duration in hours
                    if task.due and task.duration:
                        # Assume task is scheduled near due date
                        task_start = task.due - timedelta(hours=task.duration)
                        task_end = task.due
                        
                        if task_start < end_date and task_end > start_date:
                            busy_times.append({
                                "start": task_start,
                                "end": task_end,
                                "type": "task",
                                "title": task.title
                            })
        except Exception as e:
            logger.error(f"Failed to get Reclaim busy times: {e}")
        
        # Get Nylas calendar events
        try:
            client = NylasClient(
                api_key=credentials["nylas_api_key"],
                api_uri="https://api.us.nylas.com"
            )
            
            events = client.events.list(
                identifier=credentials["nylas_grant_id"],
                query_params={
                    "calendar_id": "primary",
                    "start": int(start_date.timestamp()),
                    "end": int(end_date.timestamp())
                }
            )
            
            # Handle both list and object with data attribute
            event_list = events.data if hasattr(events, 'data') else events
            if not isinstance(event_list, list):
                logger.warning(f"Expected list of events, got {type(event_list)}")
                event_list = []
            
            for event in event_list:
                if event.status != "cancelled":
                    event_start = datetime.fromtimestamp(event.when.start_time, tz=user_context["now"].tzinfo)
                    event_end = datetime.fromtimestamp(event.when.end_time, tz=user_context["now"].tzinfo) if hasattr(event.when, "end_time") else event_start + timedelta(hours=1)
                    
                    busy_times.append({
                        "start": event_start,
                        "end": event_end,
                        "type": "event",
                        "title": event.title
                    })
        except Exception as e:
            logger.error(f"Failed to get Nylas busy times: {e}")
        
        return busy_times
    
    def _calculate_available_slots(
        self,
        start_date: datetime,
        end_date: datetime,
        busy_times: List[Dict[str, Any]],
        duration_minutes: int,
        preferences: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate available time slots based on busy times."""
        # Sort busy times by start
        busy_times.sort(key=lambda x: x["start"])
        
        available_slots = []
        
        # Define working hours (default 9 AM to 6 PM)
        work_start_hour = preferences.get("work_start_hour", 9)
        work_end_hour = preferences.get("work_end_hour", 18)
        
        # Iterate through each day
        current_date = start_date.date()
        while current_date <= end_date.date():
            # Set working hours for this day
            day_start = user_context["now"].tzinfo.localize(
                datetime.combine(current_date, datetime.min.time().replace(hour=work_start_hour))
            )
            day_end = user_context["now"].tzinfo.localize(
                datetime.combine(current_date, datetime.min.time().replace(hour=work_end_hour))
            )
            
            # Skip weekends if preferred
            if preferences.get("skip_weekends", True) and current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Find gaps in busy times for this day
            day_busy = [bt for bt in busy_times if bt["start"].date() == current_date]
            
            # Check slots throughout the day
            slot_start = day_start
            
            for busy in day_busy:
                # Check if there's a gap before this busy time
                if slot_start + timedelta(minutes=duration_minutes) <= busy["start"]:
                    # Found a potential slot
                    confidence = self._calculate_slot_confidence(
                        slot_start, duration_minutes, preferences
                    )
                    
                    available_slots.append({
                        "start": slot_start.isoformat(),
                        "end": (slot_start + timedelta(minutes=duration_minutes)).isoformat(),
                        "confidence": confidence
                    })
                
                # Move slot start to after this busy time
                slot_start = max(slot_start, busy["end"])
            
            # Check if there's time at the end of the day
            if slot_start + timedelta(minutes=duration_minutes) <= day_end:
                confidence = self._calculate_slot_confidence(
                    slot_start, duration_minutes, preferences
                )
                
                available_slots.append({
                    "start": slot_start.isoformat(),
                    "end": (slot_start + timedelta(minutes=duration_minutes)).isoformat(),
                    "confidence": confidence
                })
            
            current_date += timedelta(days=1)
        
        return available_slots
    
    def _calculate_slot_confidence(
        self,
        slot_start: datetime,
        duration_minutes: int,
        preferences: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for a time slot based on preferences."""
        confidence = 0.5  # Base confidence
        
        hour = slot_start.hour
        
        # Prefer morning slots
        if preferences.get("prefer_morning") and 9 <= hour <= 11:
            confidence += 0.3
        
        # Prefer afternoon slots
        if preferences.get("prefer_afternoon") and 14 <= hour <= 16:
            confidence += 0.3
        
        # Avoid early morning
        if hour < 9:
            confidence -= 0.2
        
        # Avoid late evening
        if hour >= 17:
            confidence -= 0.2
        
        # Prefer longer duration slots for deep work
        if duration_minutes >= 120 and preferences.get("deep_work"):
            confidence += 0.2
        
        # Ensure confidence is between 0 and 1
        return max(0.0, min(1.0, confidence))