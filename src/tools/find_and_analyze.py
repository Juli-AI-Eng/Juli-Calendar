"""Hybrid tool for finding and analyzing tasks and events."""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz
import logging

from src.tools.base import BaseTool
from src.ai.search_analyzer import SearchAnalyzer
from src.ai.semantic_search import SemanticSearch
from src.auth.credential_manager import CredentialManager
from reclaim_sdk.client import ReclaimClient
from nylas import Client as NylasClient

logger = logging.getLogger(__name__)


class FindAndAnalyzeTool(BaseTool):
    """Tool for finding and analyzing tasks and events across both systems."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "find_and_analyze"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Find and analyze your tasks, meetings, and schedule. Search for specific items, "
            "check what's coming up, analyze your workload, find overdue items, "
            "or get insights about your productivity patterns across both tasks and calendar events."
        )
    
    def __init__(self):
        """Initialize the tool."""
        super().__init__()
        self.search_analyzer = SearchAnalyzer()
        self.semantic_search = SemanticSearch()
        self.credential_manager = CredentialManager()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What do you want to find or know? Examples: "
                        "'what's on my calendar today?', "
                        "'show me overdue tasks', "
                        "'find all meetings with Sarah', "
                        "'how's my workload this week?', "
                        "'what's high priority?'"
                    )
                },
                "scope": {
                    "type": "string",
                    "description": "Search scope: 'tasks', 'events', or 'both' (default: both)"
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
            "scope": data.get("scope", "both"),
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
                "message": "Both Reclaim.ai and Nylas must be connected to search across your productivity suite"
            }
        
        # Build user context
        user_context = {
            "timezone": validated_data["user_timezone"],
            "current_date": validated_data["current_date"],
            "current_time": validated_data["current_time"],
            "now": self._parse_user_datetime(validated_data)
        }
        
        # Analyze search intent
        search_intent = self.search_analyzer.analyze_search_query(
            validated_data["query"],
            user_context
        )
        logger.info(f"[find_and_analyze] Search intent from analyzer: {search_intent}")
        
        # Store the original query for semantic search
        self.last_query = validated_data["query"]
        
        # Execute search based on intent
        if search_intent.get("intent") == "workload_analysis":
            return await self._analyze_workload(
                validated_data, credentials, search_intent, user_context
            )
        else:
            return await self._search_items(
                validated_data, credentials, search_intent, user_context
            )
    
    async def _search_items(
        self, 
        data: Dict[str, Any], 
        credentials: Dict[str, str],
        search_intent: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Search for tasks and events."""
        tasks = []
        events = []
        
        # Search based on scope
        scope = data.get("scope", "both")
        search_both = search_intent.get("search_both", True)
        
        logger.info(f"[find_and_analyze] Searching with scope: {scope}, search_both: {search_both}")
        
        if scope in ["both", "tasks"]:
            tasks = await self._search_reclaim_tasks(
                credentials, search_intent, user_context
            )
        
        if scope in ["both", "events"]:
            events = await self._search_nylas_events(
                credentials, search_intent, user_context
            )
        
        # Format results
        if not tasks and not events:
            return {
                "success": True,
                "data": {
                    "tasks": [],
                    "events": []
                },
                "message": "No items found matching your search"
            }
        
        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "events": events,
                "summary": self._generate_summary(tasks, events, search_intent)
            },
            "message": f"Found {len(tasks)} tasks and {len(events)} events"
        }
    
    async def _search_reclaim_tasks(
        self,
        credentials: Dict[str, str],
        search_intent: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search Reclaim tasks using semantic search."""
        try:
            client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
            
            # Get all tasks first
            from reclaim_sdk.resources.task import Task, TaskStatus
            all_tasks = Task.list(client)
            
            # Convert to standardized format
            task_dicts = []
            for task in all_tasks:
                # Skip completed/archived tasks unless specifically requested
                # Default to excluding completed tasks if not specified
                include_completed = search_intent.get("include_completed", False)
                if not include_completed:
                    if task.status in [TaskStatus.COMPLETE, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]:
                        continue
                
                task_dicts.append({
                    "id": task.id,
                    "title": task.title,
                    "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                    "priority": str(task.priority),
                    "due": task.due.isoformat() if task.due else None,
                    "duration_hours": task.duration if task.duration else 0,
                    "notes": task.notes,
                    "provider": "reclaim",
                    "type": "task"
                })
            
            # Apply time filtering if specified (similar to event search)
            if search_intent.get("time_range"):
                time_range = search_intent["time_range"]
                now = user_context["now"]
                logger.info(f"Applying time filter for range: {time_range}")
                
                filtered_tasks = []
                for task in task_dicts:
                    if not task.get("due"):
                        continue  # Skip tasks without due dates for time-based searches
                    
                    try:
                        task_due = datetime.fromisoformat(task["due"].replace("Z", "+00:00"))
                        # Ensure both datetimes have timezone info for comparison
                        if task_due.tzinfo is None:
                            task_due = task_due.replace(tzinfo=now.tzinfo)
                        
                        if time_range == "today":
                            # Check if task is due today (same date)
                            if task_due.date() == now.date():
                                filtered_tasks.append(task)
                        elif time_range == "this_week":
                            week_start = now - timedelta(days=now.weekday())
                            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                            week_end = week_start + timedelta(days=7)
                            if week_start <= task_due < week_end:
                                filtered_tasks.append(task)
                        elif time_range == "overdue":
                            if task_due < now:
                                filtered_tasks.append(task)
                    except Exception as e:
                        logger.warning(f"Failed to parse due date for task {task['id']}: {e}")
                        continue
                
                task_dicts = filtered_tasks
                logger.info(f"Time filtering reduced tasks to {len(task_dicts)} items")
            
            # Use semantic search to filter with the full original query
            query = self.last_query if hasattr(self, 'last_query') else ""
            logger.info(f"Using semantic search with query: '{query}', found {len(task_dicts)} tasks")
            
            # Log the actual tasks for debugging
            if task_dicts:
                logger.info(f"Tasks found: {[{'id': t['id'], 'title': t['title'], 'status': t['status']} for t in task_dicts[:5]]}")
            
            # Only use semantic search if there are actual keywords to semantically match
            if query and task_dicts and search_intent.get("search_text"):
                filtered_tasks, search_metadata = self.semantic_search.analyze_and_filter(
                    query=query,
                    items=task_dicts,
                    item_type="task",
                    user_context=user_context
                )
                logger.info(f"Semantic search returned {len(filtered_tasks)} tasks from {len(task_dicts)} total")
                logger.info(f"Search metadata: {search_metadata}")
                return filtered_tasks
            else:
                # Pure time query or no semantic keywords - return time-filtered results
                logger.info(f"Returning {len(task_dicts)} time-filtered tasks without semantic search")
                return task_dicts
            
        except Exception as e:
            logger.error(f"Failed to search Reclaim tasks: {e}")
            return []
    
    async def _search_nylas_events(
        self,
        credentials: Dict[str, str],
        search_intent: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search Nylas events based on intent."""
        try:
            client = NylasClient(
                api_key=credentials["nylas_api_key"],
                api_uri="https://api.us.nylas.com"
            )
            
            # Build query parameters based on search intent
            query_params = {
                "calendar_id": search_intent.get("calendar_id", "primary")
            }
            
            # Add time range filters
            if search_intent.get("time_range"):
                time_range = search_intent["time_range"]
                if time_range == "today":
                    start = user_context["now"].replace(hour=0, minute=0, second=0)
                    end = start + timedelta(days=1)
                elif time_range == "this_week":
                    start = user_context["now"] - timedelta(days=user_context["now"].weekday())
                    start = start.replace(hour=0, minute=0, second=0)
                    end = start + timedelta(days=7)
                elif time_range == "next_week":
                    start = user_context["now"] - timedelta(days=user_context["now"].weekday()) + timedelta(days=7)
                    start = start.replace(hour=0, minute=0, second=0)
                    end = start + timedelta(days=7)
                else:
                    # Default to next 30 days
                    start = user_context["now"]
                    end = start + timedelta(days=30)
                
                query_params["start"] = int(start.timestamp())
                query_params["end"] = int(end.timestamp())
            
            # Get events
            response = client.events.list(
                identifier=credentials["nylas_grant_id"],
                query_params=query_params
            )
            
            # Format and filter events
            events = []
            for event in response.data:
                # Skip cancelled events unless requested
                if not search_intent.get("include_cancelled", False) and event.status == "cancelled":
                    continue
                
                # Apply text search
                if search_intent.get("search_text"):
                    search_text = search_intent["search_text"].lower()
                    title_lower = event.title.lower()
                    description_lower = event.description.lower() if hasattr(event, "description") and event.description else ""
                    
                    # Check if all words in search_text appear in title or description
                    search_words = search_text.split()
                    title_matches = all(word in title_lower for word in search_words)
                    description_matches = all(word in description_lower for word in search_words) if description_lower else False
                    
                    if not (title_matches or description_matches):
                        continue
                
                # Extract participant info
                participants = []
                if hasattr(event, "participants") and event.participants:
                    participants = [
                        {"email": p.email, "name": getattr(p, "name", ""), "status": getattr(p, "status", "unknown")}
                        for p in event.participants
                    ]
                
                # Format event data
                event_start = datetime.fromtimestamp(event.when.start_time, tz=user_context["now"].tzinfo)
                event_end = datetime.fromtimestamp(event.when.end_time, tz=user_context["now"].tzinfo) if hasattr(event.when, "end_time") else event_start + timedelta(hours=1)
                
                events.append({
                    "id": event.id,
                    "title": event.title,
                    "description": getattr(event, "description", ""),
                    "location": getattr(event, "location", ""),
                    "start": event_start.isoformat(),
                    "end": event_end.isoformat(),
                    "duration_hours": (event_end - event_start).total_seconds() / 3600,
                    "participants": participants,
                    "status": event.status,
                    "provider": "nylas",
                    "type": "event"
                })
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to search Nylas events: {e}")
            return []
    
    async def _analyze_workload(
        self,
        data: Dict[str, Any],
        credentials: Dict[str, str],
        search_intent: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze workload across both systems."""
        # Get tasks and events for analysis
        tasks = await self._search_reclaim_tasks(credentials, search_intent, user_context)
        events = await self._search_nylas_events(credentials, search_intent, user_context)
        
        # Calculate workload metrics
        now = user_context["now"]
        
        # Task metrics
        total_tasks = len(tasks)
        overdue_tasks = sum(1 for t in tasks if t.get("due") and datetime.fromisoformat(t["due"]) < now)
        tasks_this_week = sum(1 for t in tasks if t.get("due") and self._is_this_week(datetime.fromisoformat(t["due"]), now))
        total_task_hours = sum(t.get("duration_hours", 0) for t in tasks)
        
        # Event metrics
        total_events = len(events)
        events_today = sum(1 for e in events if self._is_today(datetime.fromisoformat(e["start"]), now))
        events_this_week = sum(1 for e in events if self._is_this_week(datetime.fromisoformat(e["start"]), now))
        total_event_hours = sum(e.get("duration_hours", 0) for e in events)
        meetings_with_others = sum(1 for e in events if len(e.get("participants", [])) > 1)
        
        # Calculate busy percentage for this week
        work_hours_per_week = 40  # Standard work week
        total_committed_hours = total_task_hours + total_event_hours
        busy_percentage = min(100, (total_committed_hours / work_hours_per_week) * 100)
        
        # Generate insights
        insights = []
        
        if overdue_tasks > 0:
            insights.append(f"You have {overdue_tasks} overdue tasks that need attention")
        
        if busy_percentage > 80:
            insights.append(f"Your schedule is {busy_percentage:.0f}% full - consider delegating or rescheduling")
        elif busy_percentage < 40:
            insights.append(f"You have good availability this week ({busy_percentage:.0f}% scheduled)")
        
        if meetings_with_others > 5:
            insights.append(f"Heavy meeting load: {meetings_with_others} meetings with others")
        
        if events_today > 4:
            insights.append(f"Busy day ahead with {events_today} events")
        
        # Build analysis response
        analysis = {
            "metrics": {
                "tasks": {
                    "total": total_tasks,
                    "overdue": overdue_tasks,
                    "this_week": tasks_this_week,
                    "total_hours": round(total_task_hours, 1)
                },
                "events": {
                    "total": total_events,
                    "today": events_today,
                    "this_week": events_this_week,
                    "total_hours": round(total_event_hours, 1),
                    "with_others": meetings_with_others
                },
                "overall": {
                    "total_committed_hours": round(total_committed_hours, 1),
                    "busy_percentage": round(busy_percentage, 1),
                    "available_hours": round(max(0, work_hours_per_week - total_committed_hours), 1)
                }
            },
            "insights": insights,
            "summary": self._generate_workload_summary(total_tasks, total_events, busy_percentage, insights)
        }
        
        return {
            "success": True,
            "data": analysis,
            "message": "Workload analysis complete"
        }
    
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
    
    def _is_today(self, dt: datetime, now: datetime) -> bool:
        """Check if a datetime is today."""
        return dt.date() == now.date()
    
    def _is_this_week(self, dt: datetime, now: datetime) -> bool:
        """Check if a datetime is in the current week."""
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        return week_start <= dt < week_end
    
    def _generate_workload_summary(
        self,
        total_tasks: int,
        total_events: int,
        busy_percentage: float,
        insights: List[str]
    ) -> str:
        """Generate a natural language summary of workload."""
        if busy_percentage > 80:
            load_description = "very busy"
        elif busy_percentage > 60:
            load_description = "busy"
        elif busy_percentage > 40:
            load_description = "moderately busy"
        else:
            load_description = "light"
        
        summary = f"Your workload is {load_description} with {total_tasks} tasks and {total_events} events scheduled. "
        
        if insights:
            summary += insights[0]  # Add the most important insight
        
        return summary
    
    def _generate_summary(
        self, 
        tasks: List[Dict[str, Any]], 
        events: List[Dict[str, Any]], 
        search_intent: Dict[str, Any]
    ) -> str:
        """Generate a summary of the search results."""
        if not tasks and not events:
            return "No items found matching your search criteria."
        
        summary_parts = []
        
        # Task summary
        if tasks:
            task_summary = f"Found {len(tasks)} task{'s' if len(tasks) != 1 else ''}"
            
            # Add status breakdown if relevant
            status_counts = {}
            for task in tasks:
                status = task.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            if len(status_counts) > 1:
                status_parts = []
                for status, count in status_counts.items():
                    if count > 0:
                        status_parts.append(f"{count} {status.lower()}")
                task_summary += f" ({', '.join(status_parts)})"
            
            summary_parts.append(task_summary)
        
        # Event summary
        if events:
            event_summary = f"Found {len(events)} event{'s' if len(events) != 1 else ''}"
            
            # Add participant info if relevant
            meetings = sum(1 for e in events if len(e.get("participants", [])) > 1)
            if meetings > 0:
                event_summary += f" ({meetings} with other participants)"
            
            summary_parts.append(event_summary)
        
        # Time range context
        if search_intent.get("time_range"):
            time_range = search_intent["time_range"]
            summary_parts.append(f"for {time_range.replace('_', ' ')}")
        
        return ". ".join(summary_parts) + "."