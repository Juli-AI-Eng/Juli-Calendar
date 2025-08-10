"""Find and analyze tasks tool for Reclaim.ai."""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz
from src.tools.base import BaseTool
from src.ai.task_ai import TaskAI
from src.ai.date_parser import DateParser
from reclaim_sdk.client import ReclaimClient
from reclaim_sdk.resources.task import Task, TaskStatus, TaskPriority
import logging

logger = logging.getLogger(__name__)


class FindAndAnalyzeTasksTool(BaseTool):
    """Tool for finding tasks and providing productivity insights."""
    
    def __init__(self):
        super().__init__()
        self.task_ai = TaskAI()
        self.date_parser = DateParser()
    
    @property
    def name(self) -> str:
        return "find_and_analyze_tasks"
    
    @property
    def description(self) -> str:
        return "Find tasks and get insights about your workload, productivity, and patterns. Ask me anything about what's on your plate!"
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool's input schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What do you want to know? Examples: 'what do I need to do today?', 'show me overdue tasks', 'how's my workload looking?', 'what's taking up most of my time?'"
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
        """Validate and process input data."""
        if "query" not in data or not data["query"]:
            raise ValueError("Missing required parameter: query")
        return data
    
    async def execute(self, data: Dict[str, Any], credentials: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute the find and analyze tasks tool."""
        query = data.get("query", "")
        user_timezone = data.get("user_timezone", "UTC")
        current_date = data.get("current_date")
        current_time = data.get("current_time")
        
        # Get API key from credentials
        api_key = None
        if credentials:
            api_key = (
                credentials.get("reclaim_api_key") or 
                credentials.get("RECLAIM_API_KEY") or
                credentials.get("Reclaim-Api-Key") or
                credentials.get("reclaim-api-key")
            )
        
        if not api_key:
            return {
                "error": "Reclaim.ai API key not found in credentials",
                "needs_setup": True
            }
        
        try:
            # Create Reclaim client
            client = ReclaimClient.configure(token=api_key)
            
            # Get all tasks
            tasks = client.list(Task)
            
            # Parse user's timezone and current time
            tz = pytz.timezone(user_timezone)
            if current_date and current_time:
                user_now = self.date_parser.parse_datetime(f"{current_date} {current_time}", tz)
            else:
                user_now = datetime.now(tz)
            
            # Understand the query
            intent = self.task_ai.understand_query(query, {
                'now': user_now,
                'timezone': user_timezone,
                'current_date': current_date,
                'current_time': current_time
            })
            
            # Handle different types of queries
            if intent.get('type') == 'find':
                return await self._find_tasks(tasks, intent, user_now)
            elif intent.get('type') == 'analyze':
                return await self._analyze_tasks(tasks, intent, user_now)
            elif intent.get('type') == 'mixed':
                # Handle queries that are both finding and analyzing
                find_result = await self._find_tasks(tasks, intent, user_now)
                analyze_result = await self._analyze_tasks(tasks, intent, user_now)
                
                return {
                    "success": True,
                    "tasks": find_result.get("tasks", []),
                    "insights": analyze_result.get("insights", {}),
                    "summary": f"Found {len(find_result.get('tasks', []))} tasks with analysis"
                }
            else:
                # Default to finding tasks
                return await self._find_tasks(tasks, intent, user_now)
                
        except Exception as e:
            logger.error(f"Error executing find and analyze tasks: {str(e)}")
            return {
                "error": f"Failed to find/analyze tasks: {str(e)}",
                "success": False
            }
    
    async def _find_tasks(self, tasks: List[Task], intent: Dict[str, Any], user_now: datetime) -> Dict[str, Any]:
        """Find tasks based on the query intent."""
        filtered_tasks = []
        
        # Apply filters based on intent
        for task in tasks:
            # Skip deleted or archived tasks
            if task.deleted or task.status == TaskStatus.ARCHIVED:
                continue
            
            # Time-based filtering
            if intent.get('time_filter'):
                time_filter = intent['time_filter']
                
                if time_filter == 'today':
                    if task.due:
                        task_date = task.due.date()
                        if task_date != user_now.date():
                            continue
                    else:
                        # Include tasks without due dates if asking for today
                        pass
                
                elif time_filter == 'overdue':
                    if not task.due or task.due.date() >= user_now.date():
                        continue
                
                elif time_filter == 'this_week':
                    if task.due:
                        week_start = user_now - timedelta(days=user_now.weekday())
                        week_end = week_start + timedelta(days=6)
                        if not (week_start.date() <= task.due.date() <= week_end.date()):
                            continue
                
                elif time_filter == 'upcoming':
                    if not task.due or task.due.date() <= user_now.date():
                        continue
            
            # Priority filtering
            if intent.get('priority_filter'):
                priority = intent['priority_filter']
                if priority == 'high' and task.priority not in [TaskPriority.P1, TaskPriority.P2]:
                    continue
                elif priority == 'low' and task.priority not in [TaskPriority.P3, TaskPriority.P4]:
                    continue
            
            # Status filtering
            if intent.get('status_filter'):
                status = intent['status_filter']
                if status == 'complete' and task.status != TaskStatus.COMPLETE:
                    continue
                elif status == 'incomplete' and task.status == TaskStatus.COMPLETE:
                    continue
                elif status == 'in_progress' and task.status != TaskStatus.IN_PROGRESS:
                    continue
            
            # Text search in title and notes
            if intent.get('search_terms'):
                search_text = ' '.join(intent['search_terms']).lower()
                task_text = f"{task.title or ''} {task.notes or ''}".lower()
                if search_text not in task_text:
                    continue
            
            filtered_tasks.append(task)
        
        # Sort tasks
        filtered_tasks.sort(key=lambda t: (
            t.due if t.due else datetime.max.replace(tzinfo=pytz.UTC),
            t.priority.value if t.priority else 'P4'
        ))
        
        # Format tasks for response
        formatted_tasks = []
        for task in filtered_tasks:
            formatted_task = {
                "id": task.id,
                "title": task.title,
                "status": task.status.value if task.status else "NEW",
                "priority": task.priority.value if task.priority else "P4",
                "due": task.due.isoformat() if task.due else None,
                "duration": task.duration,
                "notes": task.notes,
                "on_deck": task.on_deck,
                "at_risk": task.at_risk
            }
            formatted_tasks.append(formatted_task)
        
        return {
            "success": True,
            "tasks": formatted_tasks,
            "count": len(formatted_tasks),
            "summary": self._generate_find_summary(filtered_tasks, intent)
        }
    
    async def _analyze_tasks(self, tasks: List[Task], intent: Dict[str, Any], user_now: datetime) -> Dict[str, Any]:
        """Analyze tasks for productivity insights."""
        # Filter to active tasks
        active_tasks = [t for t in tasks if not t.deleted and t.status != TaskStatus.ARCHIVED]
        
        # Calculate insights
        insights = {
            "total_tasks": len(active_tasks),
            "completed_tasks": len([t for t in active_tasks if t.status == TaskStatus.COMPLETE]),
            "in_progress_tasks": len([t for t in active_tasks if t.status == TaskStatus.IN_PROGRESS]),
            "overdue_tasks": len([t for t in active_tasks if t.due and t.due.date() < user_now.date()]),
            "high_priority_tasks": len([t for t in active_tasks if t.priority in [TaskPriority.P1, TaskPriority.P2]]),
            "at_risk_tasks": len([t for t in active_tasks if t.at_risk]),
            "on_deck_tasks": len([t for t in active_tasks if t.on_deck])
        }
        
        # Time-based analysis
        today_tasks = [t for t in active_tasks if t.due and t.due.date() == user_now.date()]
        this_week_tasks = self._get_week_tasks(active_tasks, user_now)
        
        insights.update({
            "today_tasks": len(today_tasks),
            "this_week_tasks": len(this_week_tasks),
            "completion_rate": insights["completed_tasks"] / max(1, insights["total_tasks"]) * 100
        })
        
        # Workload calculation
        total_duration = sum([t.duration or 0 for t in active_tasks if t.status != TaskStatus.COMPLETE])
        insights["total_hours_remaining"] = total_duration
        
        # Generate analysis summary
        summary = self._generate_analysis_summary(insights, intent)
        
        return {
            "success": True,
            "insights": insights,
            "summary": summary,
            "recommendations": self._generate_recommendations(insights, active_tasks)
        }
    
    def _get_week_tasks(self, tasks: List[Task], user_now: datetime) -> List[Task]:
        """Get tasks for this week."""
        week_start = user_now - timedelta(days=user_now.weekday())
        week_end = week_start + timedelta(days=6)
        
        return [
            t for t in tasks 
            if t.due and week_start.date() <= t.due.date() <= week_end.date()
        ]
    
    def _generate_find_summary(self, tasks: List[Task], intent: Dict[str, Any]) -> str:
        """Generate a summary for found tasks."""
        if not tasks:
            return "No tasks found matching your criteria."
        
        count = len(tasks)
        if intent.get('time_filter') == 'today':
            return f"Found {count} task{'s' if count != 1 else ''} for today."
        elif intent.get('time_filter') == 'overdue':
            return f"Found {count} overdue task{'s' if count != 1 else ''}."
        elif intent.get('priority_filter') == 'high':
            return f"Found {count} high priority task{'s' if count != 1 else ''}."
        else:
            return f"Found {count} task{'s' if count != 1 else ''} matching your search."
    
    def _generate_analysis_summary(self, insights: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Generate a summary for task analysis."""
        total = insights["total_tasks"]
        completed = insights["completed_tasks"]
        overdue = insights["overdue_tasks"]
        high_priority = insights["high_priority_tasks"]
        
        summary_parts = [
            f"You have {total} total tasks",
            f"{completed} completed ({insights['completion_rate']:.1f}%)"
        ]
        
        if overdue > 0:
            summary_parts.append(f"{overdue} overdue")
        
        if high_priority > 0:
            summary_parts.append(f"{high_priority} high priority")
        
        return ", ".join(summary_parts) + "."
    
    def _generate_recommendations(self, insights: Dict[str, Any], tasks: List[Task]) -> List[str]:
        """Generate productivity recommendations."""
        recommendations = []
        
        if insights["overdue_tasks"] > 0:
            recommendations.append("Consider addressing overdue tasks first to get back on track.")
        
        if insights["at_risk_tasks"] > 0:
            recommendations.append("Review at-risk tasks and consider adjusting deadlines or priorities.")
        
        if insights["completion_rate"] < 50:
            recommendations.append("Your completion rate is below 50%. Consider breaking large tasks into smaller ones.")
        
        if insights["high_priority_tasks"] > 5:
            recommendations.append("You have many high-priority tasks. Consider if all are truly urgent.")
        
        if insights["total_hours_remaining"] > 40:
            recommendations.append("Heavy workload detected. Consider delegating or deferring non-critical tasks.")
        
        return recommendations