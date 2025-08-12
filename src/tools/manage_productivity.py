"""Hybrid tool for managing both tasks and calendar events."""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pytz
import logging

from src.tools.base import BaseTool
from src.ai.intent_router import IntentRouter
from src.ai.calendar_intelligence import CalendarIntelligence
from src.ai.task_ai import TaskAI
from src.ai.event_ai import EventAI
from src.auth.credential_manager import CredentialManager
from src.config.approval_config import requires_approval
from reclaim_sdk.client import ReclaimClient
from reclaim_sdk.resources.task import Task, TaskStatus
from nylas import Client as NylasClient

logger = logging.getLogger(__name__)


class ManageProductivityTool(BaseTool):
    """Tool for managing tasks and calendar events through natural language."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "manage_productivity"
    
    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Manage all aspects of your productivity: create and track tasks, "
            "schedule meetings and appointments, check availability, block time for work, "
            "and coordinate your entire schedule. Handles both one-time items and recurring commitments."
        )
    
    def __init__(self):
        """Initialize the tool."""
        super().__init__()
        self.intent_router = IntentRouter()
        self.task_ai = TaskAI()
        self.event_ai = EventAI()
        self.credential_manager = CredentialManager()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What productivity action do you need? Examples: "
                        "'create a task to review Q4 budget by Friday', "
                        "'schedule a 1-hour meeting with Sarah tomorrow', "
                        "'am I free Tuesday afternoon?', "
                        "'block 2 hours for deep work this week', "
                        "'mark the presentation as complete'"
                    )
                },
                "context": {
                    "type": "string",
                    "description": "Any additional context about the request (optional)"
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
            "context": data.get("context", ""),
            "user_timezone": data.get("user_timezone", "UTC"),
            "current_date": data.get("current_date", datetime.now().strftime("%Y-%m-%d")),
            "current_time": data.get("current_time", datetime.now().strftime("%H:%M:%S"))
        }
    
    async def execute(self, data: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
        """Execute the tool."""
        # DEBUG: Log at the very beginning
        
        # Check if this is an approved retry first
        if data.get("approved") and data.get("action_data"):
            # Extract the original data from the approval
            action_data = data["action_data"]
            action_type = data.get("action_type", "")
            logger.info(f"[DEBUG] Processing approved action, action_type: {action_type}")
            logger.info(f"[DEBUG] action_data keys: {list(action_data.keys())}")
            logger.info(f"[DEBUG] Has task_details: {bool(action_data.get('task_details'))}")
            logger.info(f"[DEBUG] Has event_details: {bool(action_data.get('event_details'))}")
            
            # Handle different approval types based on action_type
            if action_type == "task_create_duplicate" and action_data.get("task_details"):
                # Approved duplicate task creation
                # Use credentials from the function parameter, not action_data
                task_details = action_data["task_details"]
                
                # Build user context from current request data
                # Use the original params from action_data, not the approval request data
                validated_data = action_data.get("params", {})
                # Ensure user context fields have defaults
                validated_data.setdefault("user_timezone", data.get("user_timezone", "UTC"))
                validated_data.setdefault("current_date", data.get("current_date", datetime.now().strftime("%Y-%m-%d")))
                validated_data.setdefault("current_time", data.get("current_time", datetime.now().strftime("%H:%M:%S")))
                user_context = self._build_user_context(validated_data)
                
                # Create the task directly without duplicate check
                client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
                task = Task(
                    title=task_details.get("title", "New Task"),
                    notes=task_details.get("description", ""),
                    priority=task_details.get("priority", "P3"),
                    due=task_details.get("due_date"),
                    duration=(task_details.get("duration_minutes") or 60) / 60,
                    min_work_duration=(task_details.get("min_duration_minutes") or 30) / 60,
                    max_work_duration=(task_details.get("max_duration_minutes") or 120) / 60,
                    event_category="WORK"
                )
                task._client = client
                task.save()
                
                return self._success_response(
                    provider="reclaim",
                    action="created",
                    data=self._serialize_task(task),
                    message=f"Created duplicate task '{task.title}'. You now have multiple tasks with similar titles. Consider adding more context to distinguish them. New task ID: {task.id}"
                )
            elif action_type == "event_create_duplicate" and action_data.get("event_details"):
                # Approved duplicate event creation
                logger.info(f"[DEBUG] Processing approved duplicate event creation")
                logger.info(f"[DEBUG] action_data keys: {list(action_data.keys())}")
                event_details = action_data["event_details"]
                intent_result = action_data["intent"]
                validated_data = action_data.get("params", {})
                
                # Ensure user context fields have defaults
                validated_data.setdefault("user_timezone", data.get("user_timezone", "UTC"))
                validated_data.setdefault("current_date", data.get("current_date", datetime.now().strftime("%Y-%m-%d")))
                validated_data.setdefault("current_time", data.get("current_time", datetime.now().strftime("%H:%M:%S")))
                user_context = self._build_user_context(validated_data)
                
                # Create Nylas client
                nylas_client = NylasClient(
                    api_key=credentials["nylas_api_key"],
                    api_uri="https://api.us.nylas.com"
                )
                
                # Create the event directly without duplicate check
                logger.info(f"[DEBUG] Calling _create_nylas_event_skip_checks with event_details: {event_details}")
                return await self._create_nylas_event_skip_checks(
                    nylas_client, 
                    credentials["nylas_grant_id"], 
                    event_details, 
                    intent_result, 
                    user_context,
                    action_type="event_create_duplicate"
                )
            elif action_type == "task_complete":
                # Approved task complete operation - check if it's actually a bulk operation
                intent_result = action_data.get("intent", {})
                validated_data = action_data.get("params", {})
                query = validated_data.get("query", "")
                
                # Check if this should have been a bulk operation
                bulk_keywords = ["all tasks", "all of them", "all my tasks", "every task", 
                               "multiple tasks", "many tasks", "everything", "all the"]
                if any(keyword in query.lower() for keyword in bulk_keywords):
                    logger.info(f"[REDIRECT] Redirecting task_complete to bulk_complete for: '{query}'")
                    # Redirect to bulk handler
                    action_type = "bulk_complete"
                # Continue to bulk_complete handler
            
            if action_type == "bulk_complete":
                # Approved bulk complete operation
                logger.info(f"[DEBUG] Processing approved bulk complete operation")
                intent_result = action_data.get("intent", {})
                task_details = intent_result.get("task_details", {})
                validated_data = action_data.get("params", {})
                
                # Ensure user context fields have defaults
                validated_data.setdefault("user_timezone", data.get("user_timezone", "UTC"))
                validated_data.setdefault("current_date", data.get("current_date", datetime.now().strftime("%Y-%m-%d")))
                validated_data.setdefault("current_time", data.get("current_time", datetime.now().strftime("%H:%M:%S")))
                user_context = self._build_user_context(validated_data)
                
                # Create Reclaim client and execute bulk operation
                # Use the original query to maintain bulk context
                client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
                
                # For bulk operations, use the original query as the task reference
                # This will trigger the bulk logic in _complete_reclaim_task
                original_query = validated_data.get("query", "")
                task_details["title"] = original_query
                logger.info(f"[BULK_APPROVED] Using original query for bulk operation: '{original_query}'")
                
                return await self._complete_reclaim_task(client, task_details, user_context)
            elif action_type == "event_create_conflict_reschedule" and action_data.get("event_details"):
                # Approved conflict reschedule - create event at suggested alternative time
                logger.info(f"[DEBUG] Processing approved conflict reschedule")
                logger.info(f"[DEBUG] action_data keys: {list(action_data.keys())}")
                event_details = action_data["event_details"]
                intent_result = action_data["intent"]
                validated_data = action_data.get("params", {})
                
                # Ensure user context fields have defaults
                validated_data.setdefault("user_timezone", data.get("user_timezone", "UTC"))
                validated_data.setdefault("current_date", data.get("current_date", datetime.now().strftime("%Y-%m-%d")))
                validated_data.setdefault("current_time", data.get("current_time", datetime.now().strftime("%H:%M:%S")))
                user_context = self._build_user_context(validated_data)
                
                # Create Nylas client
                nylas_client = NylasClient(
                    api_key=credentials["nylas_api_key"],
                    api_uri="https://api.us.nylas.com"
                )
                
                # Create the event at the suggested alternative time without conflict check
                logger.info(f"[DEBUG] Creating event at alternative time with event_details: {event_details}")
                return await self._create_nylas_event_skip_checks(
                    nylas_client, 
                    credentials["nylas_grant_id"], 
                    event_details, 
                    intent_result, 
                    user_context,
                    action_type="event_create_conflict_reschedule"
                )
            else:
                # Regular approved request (events)
                validated_data = action_data["params"]
                # Use credentials from the function parameter, not action_data
                intent_result = action_data["intent"]
                user_context = self._build_user_context(validated_data)
                
                # Skip approval check and proceed directly
                if intent_result["provider"] == "reclaim":
                    return await self._handle_reclaim_request(
                        validated_data, credentials, intent_result, user_context
                    )
                else:
                    return await self._handle_nylas_request(
                        validated_data, credentials, intent_result, user_context,
                        skip_approval_check=True  # Already approved
                    )
        
        # For non-approved requests, validate input
        try:
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
                "message": "Both Reclaim.ai and Nylas must be connected to use this productivity suite"
            }
        
        # Build user context
        user_context = self._build_user_context(validated_data)
        
        # Analyze intent
        intent_result = self.intent_router.analyze_intent(
            validated_data["query"],
            user_context
        )
        
        # Check if intent analysis failed
        if not intent_result:
            return {
                "success": False,
                "error": "Failed to understand your request. Please try rephrasing it.",
                "provider": None
            }
        
        # Check if there was an error in intent analysis
        if intent_result.get("error"):
            # On AI error, return structured failure without heuristic labeling
            return {
                "success": False,
                "error": intent_result.get("error_message", "Failed to understand your request"),
                "provider": None,
                "debug": intent_result.get("debug")
            }
            return {
                "success": False,
                "error": intent_result.get("error_message", "Failed to understand your request"),
                "provider": None
            }
        
        # Route to appropriate provider
        if intent_result["provider"] == "reclaim":
            # Parse task details using TaskAI
            task_parsed = self.task_ai.understand_task_request(
                validated_data["query"],
                user_context
            )
            
            # Merge task AI results with intent router results
            intent_result["task_details"] = task_parsed.get("task", {})
            intent_result["operation"] = task_parsed.get("intent", "create")
            intent_result["task_reference"] = task_parsed.get("task_reference")
            
            logger.info(f"[TASK_AI_RESULT] operation from task AI: '{task_parsed.get('intent')}', task_reference: '{task_parsed.get('task_reference')}'")
            
            # For Reclaim tasks, check approval for bulk operations
            operation = intent_result.get('operation', 'create')
            operation_type = f"{intent_result['intent_type']}_{operation}"
            
            # Detect bulk operations from query
            query_lower = data["query"].lower()
            is_bulk = False
            logger.info(f"[BULK_CHECK_START] operation='{operation}', query='{data['query']}'")
            if operation in ["complete", "cancel", "delete", "update"]:
                bulk_keywords = ["all tasks", "all of them", "all my tasks", "every task", 
                               "multiple tasks", "many tasks", "everything", "all the"]
                is_bulk = any(keyword in query_lower for keyword in bulk_keywords)
                # Additional debug logging
                logger.info(f"[BULK_DEBUG] Checking keywords against query: '{query_lower}'")
                for keyword in bulk_keywords:
                    if keyword in query_lower:
                        logger.info(f"[BULK_DEBUG] Matched keyword: '{keyword}'")
            
            approval_context = {
                "has_participants": False,  # Tasks don't have participants
                "is_bulk": is_bulk
            }
            
            # Debug logging for bulk operation detection
            logger.info(f"[DEBUG] Bulk check for task: operation={operation}, query_lower='{query_lower}', is_bulk={is_bulk}")
            logger.info(f"[DEBUG] Approval context for task: {approval_context}")
            logger.info(f"[DEBUG] operation_type for task approval: {operation_type}")
            
            approval_required = requires_approval(operation_type, approval_context)
            logger.info(f"[APPROVAL_CHECK] requires_approval returned: {approval_required}")
            
            if approval_required:
                # Build warning message based on operation
                warning = self._get_operation_warning(operation_type, intent_result)
                
                # Use bulk-specific action type if it's a bulk operation
                # Additional check to ensure bulk operations get bulk_ prefix
                bulk_keywords = ["all tasks", "all of them", "all my tasks", "every task", 
                               "multiple tasks", "many tasks", "everything", "all the"]
                query_lower = data["query"].lower()
                is_definitely_bulk = any(keyword in query_lower for keyword in bulk_keywords)
                
                if is_definitely_bulk and operation in ["complete", "cancel", "delete", "update"]:
                    final_action_type = f"bulk_{operation}"
                    logger.info(f"[FORCED_BULK] Detected bulk operation, setting action_type to: {final_action_type}")
                else:
                    final_action_type = f"bulk_{operation}" if is_bulk else operation_type
                    logger.info(f"[APPROVAL_DEBUG] is_bulk={is_bulk}, operation={operation}, final_action_type={final_action_type}")
                
                return {
                    "needs_approval": True,
                    "action_type": final_action_type,
                    "action_data": {
                        "tool": "manage_productivity",
                        "params": validated_data,
                        "credentials": credentials,
                        "intent": intent_result
                    },
                    "preview": {
                        "summary": f"{intent_result.get('operation', 'Create').capitalize()} {intent_result['intent_type']} - {validated_data['query'][:50]}...",
                        "details": {
                            "provider": intent_result["provider"],
                            "intent_type": intent_result["intent_type"],
                            "query": validated_data["query"],
                            "reasoning": intent_result.get("reasoning"),
                            "user_context": user_context
                        },
                        "risks": [warning] if warning else []
                    }
                }
            
            # No approval needed, execute Reclaim request
            return await self._handle_reclaim_request(
                validated_data, 
                credentials, 
                intent_result,
                user_context
            )
        else:  # nylas
            # For Nylas events, check approval based on actual participants data
            # We need to route through the handler to check participants
            return await self._handle_nylas_request(
                validated_data,
                credentials,
                intent_result,
                user_context
            )
    
    async def _handle_reclaim_request(
        self, 
        data: Dict[str, Any], 
        credentials: Dict[str, str],
        intent: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Reclaim.ai requests."""
        try:
            # Create Reclaim client
            client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
            
            # Extract task details from intent
            task_details = intent.get("task_details", {})
            
            # For operations that need task reference, add it to task_details
            if intent.get("task_reference"):
                task_details["task_reference"] = intent.get("task_reference")
            
            # Handle different operations
            operation = intent.get("operation", "create")
            
            if operation == "create":
                return await self._create_reclaim_task(client, task_details, user_context)
            elif operation == "update":
                return await self._update_reclaim_task(client, task_details, user_context)
            elif operation == "complete":
                # Complete operation - bulk handling is in _complete_reclaim_task
                return await self._complete_reclaim_task(client, task_details, user_context)
            elif operation == "cancel" or operation == "delete":
                return await self._cancel_reclaim_task(client, task_details, user_context)
            else:
                return {
                    "success": False,
                    "error": f"Operation '{operation}' not implemented yet"
                }
            
        except Exception as e:
            logger.error(f"Reclaim operation failed: {e}")
            return self._error_response("reclaim", str(e))
    
    async def _handle_nylas_request(
        self,
        data: Dict[str, Any],
        credentials: Dict[str, str],
        intent: Dict[str, Any],
        user_context: Dict[str, Any],
        skip_approval_check: bool = False
    ) -> Dict[str, Any]:
        """Handle Nylas requests with participant-based approval checking."""
        try:
            # Create Nylas client
            nylas_client = NylasClient(
                api_key=credentials["nylas_api_key"],
                api_uri="https://api.us.nylas.com"
            )
            
            # Parse event details using EventAI
            event_parsed = self.event_ai.understand_event_request(
                data["query"],
                user_context
            )
            
            # Check for parse errors
            if event_parsed.get("error"):
                return self._error_response("nylas", f"Failed to understand event request: {event_parsed.get('error')}")
            
            # Use parsed event details
            event_details = event_parsed
            operation = event_parsed.get("operation", "create")
            
            # Store parsed details in intent for later use
            intent["event_details"] = event_details
            intent["operation"] = operation
            
            # Check if approval is needed based on actual participants
            has_participants = await self._check_has_participants(
                nylas_client, credentials["nylas_grant_id"], operation, event_details, intent
            )
            
            # For create operations, check duplicates FIRST before any approval checks
            if operation == "create" and not skip_approval_check:
                # Extract time details for duplicate checking
                start_time_iso = event_details.get("start_time")
                end_time_iso = event_details.get("end_time")
                
                if start_time_iso:
                    start_time = self._iso_to_unix_timestamp(start_time_iso, user_context.get("timezone", "UTC"))
                    end_time = self._iso_to_unix_timestamp(end_time_iso, user_context.get("timezone", "UTC")) if end_time_iso else start_time + 3600
                    
                    # Check for duplicate events before any approval flow
                    duplicate_check = await self._check_duplicate_event(
                        nylas_client, credentials["nylas_grant_id"], 
                        event_details.get("title", ""), start_time, end_time, user_context
                    )
                    
                    if duplicate_check["has_duplicate"]:
                        # Return duplicate approval request
                        existing = duplicate_check["existing_event"]
                        return {
                            "needs_approval": True,
                            "action_type": "event_create_duplicate",
                            "action_data": {
                                "tool": "manage_productivity",
                                "params": {
                                    "query": intent.get("query", ""), 
                                    "context": "Creating duplicate event",
                                    "user_timezone": user_context.get("timezone", "UTC"),
                                    "current_date": user_context.get("current_date"),
                                    "current_time": user_context.get("current_time")
                                },
                                "credentials": {"nylas_api_key": nylas_client.api_key, "nylas_grant_id": credentials["nylas_grant_id"]},
                                "intent": intent,
                                "event_details": event_details
                            },
                            "preview": {
                                "summary": f"Duplicate event detected: '{event_details.get('title', 'Event')}'",
                                "details": {
                                    "existing_event": {
                                        "title": existing.get("title"),
                                        "time": existing.get("time_display"),
                                        "id": existing.get("id")
                                    },
                                    "message": f"An event with this title already exists at {existing.get('time_display', 'this time')}. Do you want to create another one?"
                                },
                                "risks": ["This will create a duplicate event at the same time"]
                            }
                        }
                    
                    # Check for conflicts BEFORE approval check (but after duplicate check)
                    conflict_check = await self._check_time_conflicts(
                        nylas_client, credentials["nylas_grant_id"], start_time, end_time, user_context
                    )
                    
                    if conflict_check["has_conflict"]:
                        # Find next available slot
                        next_slot = await self._find_next_available_slot(
                            nylas_client, credentials["nylas_grant_id"], start_time, end_time - start_time, user_context
                        )
                        
                        if next_slot:
                            # Update the event details with the new time
                            alternative_event_details = event_details.copy()
                            # Use ISO format strings for the alternative times
                            alternative_event_details["start_time"] = next_slot["start"].strftime("%Y-%m-%dT%H:%M:%S")
                            alternative_event_details["end_time"] = next_slot["end"].strftime("%Y-%m-%dT%H:%M:%S")
                            
                            # For solo events, automatically reschedule without approval
                            if not intent.get("involves_others", False):
                                # Create the event at the alternative time directly
                                actual_start_time = int(next_slot["start"].timestamp())
                                actual_end_time = int(next_slot["end"].timestamp())
                                
                                new_event = nylas_client.events.create(
                                    credentials["nylas_grant_id"],
                                    request_body={
                                        "title": alternative_event_details["title"],
                                        "description": alternative_event_details["description"],
                                        "when": {
                                            "start_time": actual_start_time,
                                            "end_time": actual_end_time
                                        },
                                        "location": alternative_event_details.get("location"),
                                        "participants": []  # Solo event
                                    },
                                    query_params={"calendar_id": "primary"}
                                )
                                
                                return {
                                    "success": True,
                                    "action": "created",
                                    "provider": "nylas",
                                    "data": {
                                        "id": new_event.data.id,
                                        "title": new_event.data.title,
                                        "when": {
                                            "start": actual_start_time,
                                            "end": actual_end_time
                                        },
                                        "participants": []
                                    },
                                    "message": f"Successfully rescheduled '{alternative_event_details['title']}' to the scheduled time to avoid a time conflict. "
                                }
                            
                            # Format times for display
                            original_time = datetime.fromtimestamp(start_time, tz=user_context["now"].tzinfo)
                            suggested_time = next_slot["start"]
                            suggested_end = next_slot["end"]
                            duration_minutes = int((suggested_end - suggested_time).total_seconds() / 60)
                            
                            return {
                                "needs_approval": True,
                                "action_type": "event_create_conflict_reschedule",
                                "action_data": {
                                    "tool": "manage_productivity",
                                    "params": {
                                        "query": intent.get("query", ""), 
                                        "context": "Rescheduling due to conflict",
                                        "user_timezone": user_context.get("timezone", "UTC"),
                                        "current_date": user_context.get("current_date"),
                                        "current_time": user_context.get("current_time")
                                    },
                                    "credentials": {"nylas_api_key": nylas_client.api_key, "nylas_grant_id": credentials["nylas_grant_id"]},
                                    "intent": intent,
                                    "event_details": alternative_event_details  # Use alternative time
                                },
                                "preview": {
                                    "summary": f"Schedule conflict detected for '{event_details.get('title', 'Event')}'",
                                    "details": {
                                        "message": f"The requested time ({original_time.strftime('%B %d at %I:%M %p')}) conflicts with: {', '.join([c['title'] for c in conflict_check['conflicting_events']])}",
                                        "original_request": {
                                            "title": event_details.get("title"),
                                            "time": original_time.strftime("%B %d at %I:%M %p"),
                                            "duration": f"{int((end_time - start_time) / 60)} minutes"
                                        },
                                        "suggested_alternative": {
                                            "start": suggested_time.strftime("%B %d at %I:%M %p"),
                                            "end": suggested_end.strftime("%I:%M %p"),
                                            "duration": f"{duration_minutes} minutes"
                                        }
                                    },
                                    "risks": ["The originally requested time slot is not available"]
                                }
                            }
                        else:
                            return self._error_response(
                                "nylas",
                                "No available time slots found in the next 7 days for the requested duration"
                            )
            
            # Build operation type for approval checking
            operation_type = f"event_{operation}"
            
            # Detect bulk operations from query
            query_lower = data["query"].lower()
            is_bulk = False
            if operation in ["cancel", "delete", "update"]:
                bulk_keywords = ["all events", "all meetings", "all of them", "every meeting", 
                               "multiple events", "many meetings", "everything", "all the"]
                is_bulk = any(keyword in query_lower for keyword in bulk_keywords)
            
            approval_context = {
                "has_participants": has_participants,
                "is_bulk": is_bulk
            }
            
            # Check if approval is required (skip if already approved)
            if not skip_approval_check and requires_approval(operation_type, approval_context):
                # Build warning message based on operation
                warning = self._get_operation_warning(
                    f"{operation_type}_with_participants" if has_participants else operation_type, 
                    intent
                )
                
                return {
                    "needs_approval": True,
                    "action_type": f"{operation_type}_with_participants" if has_participants else operation_type,
                    "action_data": {
                        "tool": "manage_productivity",
                        "params": data,
                        "credentials": credentials,
                        "intent": intent
                    },
                    "preview": {
                        "summary": f"{operation.capitalize()} event - {data['query'][:50]}...",
                        "details": {
                            "provider": intent["provider"],
                            "intent_type": intent["intent_type"],
                            "query": data["query"],
                            "reasoning": intent.get("reasoning"),
                            "has_participants": has_participants,
                            "user_context": user_context
                        },
                        "risks": [warning] if warning else []
                    }
                }
            
            # No approval needed, execute the operation
            if operation == "create":
                return await self._create_nylas_event(nylas_client, credentials["nylas_grant_id"], event_details, intent, user_context)
            elif operation == "update":
                return await self._update_nylas_event(nylas_client, credentials["nylas_grant_id"], event_details, intent, user_context)
            elif operation == "cancel":
                return await self._cancel_nylas_event(nylas_client, credentials["nylas_grant_id"], event_details, intent, user_context)
            else:
                return {
                    "success": False,
                    "error": f"Operation '{operation}' not implemented yet"
                }
            
        except Exception as e:
            logger.error(f"Nylas operation failed: {e}")
            return self._error_response("nylas", str(e))
    
    async def _check_has_participants(
        self,
        nylas_client: NylasClient,
        grant_id: str,
        operation: str,
        event_details: Dict[str, Any],
        intent: Dict[str, Any]
    ) -> bool:
        """Check if an event has participants - use actual Nylas data when possible."""
        try:
            if operation == "create":
                # For create operations, check two sources:
                # 1. Explicit participants in event details (from AI parsing)
                participants = event_details.get("participants", [])
                if participants and len(participants) > 0:
                    logger.info(f"Found explicit participants in event details: {len(participants)} participants")
                    return True
                
                # 2. AI's involves_others detection (improved prompt should be more reliable)
                involves_others = intent.get("involves_others", False)
                if involves_others:
                    logger.info(f"AI detected involves_others=true from query analysis")
                    return True
                
                logger.info(f"No participants detected for create operation")
                return False
            
            elif operation in ["update", "cancel"]:
                # For update/cancel operations, fetch the actual event to check participants
                event_id = event_details.get("event_id")
                
                if event_id:
                    # We have event ID - fetch the actual event
                    try:
                        event_response = nylas_client.events.find(
                            identifier=grant_id,
                            event_id=event_id,
                            query_params={
                                "calendar_id": event_details.get("calendar_id", "primary")
                            }
                        )
                        event = event_response.data
                        
                        # Check if the event has participants
                        if hasattr(event, 'participants') and event.participants:
                            participants_count = len(event.participants)
                            logger.info(f"Found {participants_count} participants in existing event {event_id}")
                            return participants_count > 0
                        else:
                            logger.info(f"No participants found in existing event {event_id}")
                            return False
                            
                    except Exception as e:
                        logger.error(f"Failed to fetch event {event_id}: {e}")
                        # If we can't fetch the event, be conservative
                        return False
                else:
                    # No event ID - try to find by title but be strict
                    event_title = event_details.get("event_reference", event_details.get("title", ""))
                    if not event_title:
                        logger.warning(f"No event ID or title provided for {operation} operation")
                        return False
                    
                    try:
                        events_response = nylas_client.events.list(
                            identifier=grant_id,
                            query_params={
                                "calendar_id": event_details.get("calendar_id", "primary"),
                                "limit": 10
                            }
                        )
                        
                        # Exact title match only
                        matching_events = [
                            e for e in events_response.data 
                            if e.title and e.title.lower().strip() == event_title.lower().strip()
                        ]
                        
                        if len(matching_events) == 0:
                            logger.warning(f"No events found with exact title: '{event_title}'")
                            return False
                        elif len(matching_events) > 1:
                            logger.error(f"Multiple events found with title '{event_title}'. Cannot determine which to check.")
                            # Return False to avoid approval for ambiguous cases
                            return False
                        else:
                            event = matching_events[0]
                            if hasattr(event, 'participants') and event.participants:
                                participants_count = len(event.participants)
                                logger.info(f"Found {participants_count} participants in event '{event_title}'")
                                return participants_count > 0
                            else:
                                logger.info(f"No participants found in event '{event_title}'")
                                return False
                                
                    except Exception as e:
                        logger.error(f"Failed to search for events: {e}")
                        return False
            
            # Default to no participants for unknown operations
            return False
            
        except Exception as e:
            logger.warning(f"Error checking participants: {e}")
            # If we can't determine participants, err on the side of caution
            return False
    
    def _build_user_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build user context from validated data."""
        return {
            "timezone": data["user_timezone"],
            "current_date": data["current_date"],
            "current_time": data["current_time"],
            "now": self._parse_user_datetime(data)
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
    
    def _iso_to_unix_timestamp(self, iso_datetime_str: str, user_timezone: str) -> int:
        """Convert ISO datetime string to Unix timestamp using user's timezone.
        
        Args:
            iso_datetime_str: ISO format datetime (e.g., "2025-07-31T10:00:00")
            user_timezone: IANA timezone string (e.g., "America/New_York")
            
        Returns:
            Unix timestamp in seconds
        """
        # Parse the ISO datetime string (naive datetime)
        dt = datetime.fromisoformat(iso_datetime_str)
        
        # Apply the user's timezone
        tz = pytz.timezone(user_timezone)
        dt_with_tz = tz.localize(dt)
        
        # Convert to Unix timestamp (seconds since epoch)
        return int(dt_with_tz.timestamp())
    
    def _get_operation_warning(self, operation_type: str, intent: Dict[str, Any]) -> Optional[str]:
        """Get warning message for operations that need approval."""
        warnings = {
            "task_cancel": "This will permanently delete the task",
            "task_delete": "This will permanently delete the task",
            "event_cancel": "This will cancel the event and notify attendees" if intent.get("involves_others") else "This will cancel the event",
            "event_delete": "This will permanently delete the event",
            "bulk_delete": "This will delete multiple items",
            "event_create_with_participants": "This will send invitations to other participants",
            "event_update_with_participants": "This will notify all participants of the changes",
            "bulk_update": "This will update multiple items",
            "bulk_complete": "This will mark multiple tasks as complete",
            "recurring_create": "This will create a recurring series"
        }
        return warnings.get(operation_type)
    
    # Reclaim operation methods
    async def _create_reclaim_task(self, client: ReclaimClient, task_details: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Reclaim task."""
        try:
            # Ensure task_details is not None
            if task_details is None:
                logger.error("task_details is None in _create_reclaim_task")
                return self._error_response("reclaim", "No task details provided")
            
            # Check for duplicate tasks before creating
            task_title = task_details.get("title", "New Task")
            duplicate_check = await self._check_duplicate_task(client, task_title)
            
            if duplicate_check["has_duplicate"]:
                # Return approval request for duplicate
                existing = duplicate_check["existing_task"]
                return {
                    "needs_approval": True,
                    "action_type": "task_create_duplicate",
                    "action_data": {
                        "tool": "manage_productivity",
                        "params": {
                            "query": task_title, 
                            "context": "Creating duplicate task",
                            "user_timezone": user_context.get("timezone", "UTC"),
                            "current_date": user_context.get("current_date"),
                            "current_time": user_context.get("current_time")
                        },
                        "task_details": task_details
                    },
                    "preview": {
                        "summary": f"Duplicate task detected: '{task_title}'",
                        "details": {
                            "existing_task": {
                                "title": existing.get("title"),
                                "status": existing.get("status"),
                                "id": existing.get("id")
                            },
                            "message": f"A task with a similar title '{existing.get('title')}' already exists. Do you want to create another one?"
                        },
                        "risks": ["This will create a duplicate task with a similar title"]
                    }
                }
            
            # Create task object with proper field mapping from AI intent
            # Log what we're about to create for debugging
            logger.info(f"Creating task with details: {task_details}")
            
            # Handle due_date - it might be None or a string
            due_date = task_details.get("due_date")
            if due_date and isinstance(due_date, str):
                try:
                    # Parse ISO format date
                    from datetime import datetime
                    due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Failed to parse due_date '{due_date}': {e}")
                    due_date = None
            
            task = Task(
                title=task_details.get("title", "New Task"),
                notes=task_details.get("description", ""),
                priority=task_details.get("priority", "P3"),
                due=due_date,
                # Duration in hours, converted to 15-min chunks internally by the setter
                duration=(task_details.get("duration_minutes") or 60) / 60,
                min_work_duration=(task_details.get("min_duration_minutes") or 30) / 60,
                max_work_duration=(task_details.get("max_duration_minutes") or 120) / 60,
                event_category="WORK"  # Default to WORK category
            )
            
            # Save the task using the Reclaim API
            task._client = client
            task.save()
            
            return self._success_response(
                provider="reclaim",
                action="created",
                data=self._serialize_task(task),
                message=f"Created task: {task.title}"
            )
            
        except Exception as e:
            logger.error(f"Failed to create Reclaim task: {e}")
            return self._error_response("reclaim", f"Failed to create task: {str(e)}")
    
    async def _update_reclaim_task(self, client: ReclaimClient, task_details: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing Reclaim task."""
        try:
            task_id = task_details.get("task_id")
            if not task_id:
                # Use AI to find the task
                tasks = Task.list(client)
                task_reference = task_details.get("task_reference", "")
                
                # Filter to only active tasks and limit to recent 100 to prevent timeout
                active_tasks = [t for t in tasks if t.status in [TaskStatus.NEW, TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS]][:100]
                
                # Convert to dict format for AI
                task_dicts = [self._serialize_task(t) for t in active_tasks]
                
                # Use AI to find the matching task
                ai_result = self.task_ai.find_single_task_for_operation(
                    query=task_reference,
                    operation="update",
                    tasks=task_dicts,
                    user_context=user_context
                )
                
                if not ai_result["found"]:
                    return self._error_response("reclaim", ai_result.get("reasoning", f"No task found matching '{task_reference}'"))
                
                if ai_result.get("ambiguous_matches"):
                    # Multiple matches - need clarification
                    matches = []
                    for tid in ai_result["ambiguous_matches"][:3]:
                        task = next((t for t in active_tasks if str(t.id) == tid), None)
                        if task:
                            matches.append({"id": task.id, "title": task.title})
                    
                    matches_str = ', '.join([f"{m['title']} (ID: {m['id']})" for m in matches])
                    return self._error_response(
                        "reclaim", 
                        f"Multiple tasks match '{task_reference}'. Which one did you mean? Matches: {matches_str}"
                    )
                
                # Single match found
                task = next((t for t in active_tasks if str(t.id) == ai_result["task_id"]), None)
                if not task:
                    return self._error_response("reclaim", "Internal error: task not found")
            else:
                # Get task by ID
                task = Task.get(task_id, client)
            
            # Update fields that were provided
            updates = task_details.get("updates", {})
            
            if "title" in updates:
                task.title = updates["title"]
            if "description" in updates or "notes" in updates:
                task.notes = updates.get("description") or updates.get("notes")
            if "priority" in updates:
                task.priority = updates["priority"]
            if "due_date" in updates:
                task.due = updates["due_date"]
            if "duration_minutes" in updates:
                task.duration = (updates["duration_minutes"] or 60) / 60
            if "status" in updates:
                task.status = updates["status"]
            
            # Save the updated task
            task._client = client
            task.save()
            
            return self._success_response(
                provider="reclaim",
                action="updated",
                data=self._serialize_task(task),
                message=f"Updated task: {task.title}"
            )
            
        except Exception as e:
            logger.error(f"Failed to update Reclaim task: {e}")
            return self._error_response("reclaim", f"Failed to update task: {str(e)}")
    
    async def _complete_reclaim_task(self, client: ReclaimClient, task_details: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Complete a Reclaim task."""
        try:
            task_id = task_details.get("task_id")
            if not task_id:
                # Use AI to find the task
                tasks = Task.list(client)
                task_reference = task_details.get("task_reference", "")
                logger.info(f"[TEMP] Looking for task with reference: '{task_reference}'")
                
                # Check if this is a bulk operation (looking for multiple tasks)
                bulk_indicators = ['all tasks', 'all ', 'multiple', 'every', 'each']
                is_bulk = any(indicator in task_reference.lower() for indicator in bulk_indicators)
                
                if is_bulk:
                    # Handle bulk task completion - THIS REQUIRES APPROVAL!
                    logger.info(f"[BULK] Detected bulk operation for: '{task_reference}'")
                    
                    # This is an APPROVED request being executed
                    # The original approval check already happened, so we can proceed
                    # Check if we're in an approved context (i.e., this was called from an approved action)
                    
                    # Filter to only active tasks
                    active_tasks = [t for t in tasks if t.status in [TaskStatus.NEW, TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS]]
                    
                    # Find matching tasks based on the search term
                    # Extract the search term from phrases like "all tasks with 'X' in the title"
                    import re
                    search_terms = []
                    
                    # Try to extract quoted terms
                    quoted_matches = re.findall(r"'([^']+)'", task_reference)
                    if quoted_matches:
                        search_terms.extend(quoted_matches)
                    
                    # Also try common patterns
                    if "with" in task_reference.lower():
                        # Pattern: "all tasks with X in the title"
                        parts = task_reference.lower().split("with")
                        if len(parts) > 1:
                            term = parts[1].replace("in the title", "").replace("in title", "").strip()
                            term = term.strip("'\"")
                            if term and term not in search_terms:
                                search_terms.append(term)
                    
                    if not search_terms:
                        # Fallback: use the whole reference
                        search_terms = [task_reference]
                    
                    logger.info(f"[BULK] Search terms: {search_terms}")
                    
                    # Find tasks that match any of the search terms
                    matching_tasks = []
                    for task in active_tasks:
                        task_title_lower = task.title.lower()
                        for term in search_terms:
                            if term.lower() in task_title_lower:
                                matching_tasks.append(task)
                                break
                    
                    logger.info(f"[BULK] Found {len(matching_tasks)} matching tasks")
                    
                    if not matching_tasks:
                        return self._error_response("reclaim", f"No tasks found matching '{task_reference}'")
                    
                    # Complete all matching tasks
                    completed_tasks = []
                    failed_tasks = []
                    
                    for task in matching_tasks:
                        try:
                            task._client = client
                            task.mark_complete()
                            task.refresh()
                            completed_tasks.append({"id": task.id, "title": task.title})
                            logger.info(f"[BULK] Completed task: {task.title} (ID: {task.id})")
                        except Exception as e:
                            failed_tasks.append({"id": task.id, "title": task.title, "error": str(e)})
                            logger.error(f"[BULK] Failed to complete task {task.title}: {e}")
                    
                    # Return bulk operation result
                    if completed_tasks:
                        message = f"Completed {len(completed_tasks)} task(s): {', '.join([t['title'] for t in completed_tasks])}"
                        if failed_tasks:
                            message += f". Failed to complete {len(failed_tasks)} task(s): {', '.join([t['title'] for t in failed_tasks])}"
                        
                        return self._success_response(
                            provider="reclaim",
                            action="bulk_completed",
                            data={"completed": completed_tasks, "failed": failed_tasks},
                            message=message
                        )
                    else:
                        return self._error_response("reclaim", f"Failed to complete any tasks. Errors: {failed_tasks}")
                    
                # Not a bulk operation - continue with single task logic
                
                # Filter to only active tasks and limit to recent 100 to prevent timeout
                active_tasks = [t for t in tasks if t.status in [TaskStatus.NEW, TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS]][:100]
                
                # Convert to dict format for AI
                task_dicts = [self._serialize_task(t) for t in active_tasks]
                
                # Use AI to find the matching task
                ai_result = self.task_ai.find_single_task_for_operation(
                    query=task_reference,
                    operation="complete",
                    tasks=task_dicts,
                    user_context=user_context
                )
                
                if not ai_result["found"]:
                    return self._error_response("reclaim", ai_result.get("reasoning", f"No task found matching '{task_reference}'"))
                
                if ai_result.get("ambiguous_matches"):
                    # Multiple matches - need clarification
                    matches = []
                    for tid in ai_result["ambiguous_matches"][:3]:
                        task = next((t for t in active_tasks if str(t.id) == tid), None)
                        if task:
                            matches.append({"id": task.id, "title": task.title})
                    
                    matches_str = ', '.join([f"{m['title']} (ID: {m['id']})" for m in matches])
                    return self._error_response(
                        "reclaim", 
                        f"Multiple tasks match '{task_reference}'. Which one did you mean? Matches: {matches_str}"
                    )
                
                # Single match found
                task = next((t for t in active_tasks if str(t.id) == ai_result["task_id"]), None)
                if not task:
                    return self._error_response("reclaim", "Internal error: task not found")
            else:
                # Get task by ID
                task = Task.get(task_id, client)
            
            # Mark the task as complete using the special API endpoint
            task._client = client
            task.mark_complete()
            
            # Refresh to ensure we have the latest state from the server
            task.refresh()
            
            # Log the updated status for debugging
            logger.info(f"Task after completion - ID: {task.id}, Status: {task.status}, Title: {task.title}")
            
            return self._success_response(
                provider="reclaim",
                action="completed",
                data=self._serialize_task(task),
                message=f"Completed task: {task.title}"
            )
            
        except Exception as e:
            logger.error(f"Failed to complete Reclaim task: {e}")
            return self._error_response("reclaim", f"Failed to complete task: {str(e)}")
    
    async def _cancel_reclaim_task(self, client: ReclaimClient, task_details: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel/delete a Reclaim task."""
        try:
            task_id = task_details.get("task_id")
            # Also check for task_reference at the top level of task_details
            task_reference = task_details.get("task_reference") or task_details.get("title", "")
            
            if not task_id and task_reference:
                # Use AI to find the task - filter to only active tasks to avoid timeout
                tasks = Task.list(client)
                
                # Filter to only active tasks and limit to recent 100 to prevent timeout
                active_tasks = [t for t in tasks if t.status in [TaskStatus.NEW, TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS]][:100]
                
                # Convert to dict format for AI
                task_dicts = [self._serialize_task(t) for t in active_tasks]
                
                # Use AI to find the matching task
                ai_result = self.task_ai.find_single_task_for_operation(
                    query=task_reference,
                    operation="cancel",
                    tasks=task_dicts,
                    user_context=user_context
                )
                
                if not ai_result["found"]:
                    return self._error_response("reclaim", ai_result.get("reasoning", f"No task found matching '{task_reference}'"))
                
                if ai_result.get("ambiguous_matches"):
                    # Multiple matches - need clarification
                    matches = []
                    for tid in ai_result["ambiguous_matches"][:3]:
                        task = next((t for t in active_tasks if str(t.id) == tid), None)
                        if task:
                            matches.append({"id": task.id, "title": task.title})
                    
                    matches_str = ', '.join([f"{m['title']} (ID: {m['id']})" for m in matches])
                    return self._error_response(
                        "reclaim", 
                        f"Multiple tasks match '{task_reference}'. Which one did you mean? Matches: {matches_str}"
                    )
                
                # Single match found
                task = next((t for t in active_tasks if str(t.id) == ai_result["task_id"]), None)
                if not task:
                    return self._error_response("reclaim", "Internal error: task not found")
                task_id = task.id
            else:
                # Get task to ensure it exists
                task = Task.get(task_id, client)
            
            # Delete the task
            task._client = client
            task.delete()
            
            return self._success_response(
                provider="reclaim",
                action="cancelled",
                data={"id": task_id, "title": task.title if 'task' in locals() else "Task"},
                message=f"Cancelled task: {task.title if 'task' in locals() else 'Task'}"
            )
            
        except Exception as e:
            logger.error(f"Failed to cancel Reclaim task: {e}")
            return self._error_response("reclaim", f"Failed to cancel task: {str(e)}")
    
    # Nylas operation methods
    async def _create_nylas_event(self, client: NylasClient, grant_id: str, event_details: Dict[str, Any], intent: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Nylas event."""
        try:
            # Build request body for event creation
            start_time_iso = event_details.get("start_time")
            end_time_iso = event_details.get("end_time")
            
            # Convert ISO datetime strings to Unix timestamps
            if start_time_iso:
                start_time = self._iso_to_unix_timestamp(start_time_iso, user_context.get("timezone", "UTC"))
                
                # Verify the conversion
                verify_dt = datetime.fromtimestamp(start_time, pytz.timezone(user_context.get("timezone", "UTC")))
            else:
                # This shouldn't happen if AI is working correctly
                logger.error("No start_time provided by AI")
                return self._error_response("nylas", "No start time provided")
            
            # If no end_time provided, default to 1 hour after start
            if end_time_iso:
                end_time = self._iso_to_unix_timestamp(end_time_iso, user_context.get("timezone", "UTC"))
            else:
                end_time = start_time + 3600  # Add 1 hour
            
            # Note: Duplicate and conflict detection are now done in _handle_nylas_request before approval checks
            # This ensures duplicates and conflicts are caught even for events with participants
            
            request_body = {
                "title": event_details.get("title", "New Event"),
                "description": event_details.get("description", ""),
                "location": event_details.get("location", ""),
                "when": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_timezone": user_context.get("timezone", "UTC"),
                    "end_timezone": user_context.get("timezone", "UTC")
                }
            }
            
            # Add participants if provided
            if event_details.get("participants"):
                participants_list = []
                for p in event_details["participants"]:
                    if isinstance(p, str):
                        # If it's just a name string, create placeholder email
                        email_placeholder = f"{p.replace(' ', '.').lower()}@example.com"
                        participants_list.append({
                            "email": email_placeholder,
                            "name": p,
                            "status": "noreply"
                        })
                    else:
                        # It's already a dict, use existing email or generate placeholder
                        email_to_use = p.get("email", "")
                        if not email_to_use:
                            name_for_email = p.get("name", "unknown")
                            email_to_use = f"{name_for_email.replace(' ', '.').lower()}@example.com"
                        participants_list.append({
                            "email": email_to_use,
                            "name": p.get("name", ""),
                            "status": "noreply"
                        })
                request_body["participants"] = participants_list
            
            # Add reminders if provided
            if event_details.get("reminders"):
                request_body["reminders"] = {
                    "use_default": False,
                    "overrides": [
                        {
                            "reminder_minutes": r,
                            "reminder_method": "email"
                        }
                        for r in event_details["reminders"]
                    ]
                }
            
            # Create the event with calendar_id as query parameter
            event = client.events.create(
                identifier=grant_id,
                request_body=request_body,
                query_params={
                    "calendar_id": event_details.get("calendar_id", "primary"),
                    "notify_participants": event_details.get("notify_participants", True)
                }
            )
            
            # Get event title safely
            try:
                if hasattr(event, 'data') and hasattr(event.data, 'title'):
                    event_title = event.data.title
                elif hasattr(event, 'title'):
                    event_title = event.title
                else:
                    event_title = "Unknown Event"
            except:
                event_title = "Unknown Event"
            
            # Build intelligent message for regular event creation
            when_str = self._format_event_time(event)
            message = f"Successfully scheduled '{event_title}' for {when_str}."
            
            # Add participant information if event involves others
            if intent.get("involves_others") or event_details.get("participants"):
                # Get participant info from the created event response
                event_data = self._serialize_event_safe(event)
                participants = event_data.get("participants", [])
                
                if participants:
                    participant_count = len(participants)
                    # Get first 3 participant emails or names
                    participant_emails = []
                    for p in participants[:3]:
                        if isinstance(p, str):
                            participant_emails.append(p)  # Just a name
                        elif isinstance(p, dict):
                            if p.get("email"):
                                participant_emails.append(p["email"])
                            elif p.get("name"):
                                participant_emails.append(p["name"])
                    
                    if participant_count > 3:
                        participant_emails.append(f"and {participant_count - 3} others")
                    
                    if participant_emails:
                        message += f" Invitations have been sent to: {', '.join(participant_emails)}."
                    else:
                        message += f" All {participant_count} participants have been notified."
            
            result = self._success_response(
                provider="nylas",
                action="created",
                data=event_data if 'event_data' in locals() else self._serialize_event_safe(event),
                message=message
            )
            
            # Add warning if involves others (keep for compatibility)
            if intent.get("involves_others"):
                result["warning"] = intent.get("warning", "This event involves other people")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create Nylas event: {e}")
            return self._error_response("nylas", f"Failed to create event: {str(e)}")
    
    async def _create_nylas_event_skip_checks(self, client: NylasClient, grant_id: str, event_details: Dict[str, Any], intent: Dict[str, Any], user_context: Dict[str, Any], action_type: str = None) -> Dict[str, Any]:
        """Create a new Nylas event without duplicate/conflict checks (for approved duplicates)."""
        try:
            # Build request body for event creation
            start_time_iso = event_details.get("start_time")
            end_time_iso = event_details.get("end_time")
            
            # Convert ISO datetime strings to Unix timestamps
            if start_time_iso:
                start_time = self._iso_to_unix_timestamp(start_time_iso, user_context.get("timezone", "UTC"))
            else:
                # This shouldn't happen if AI is working correctly
                logger.error("No start_time provided by AI")
                return self._error_response("nylas", "No start time provided")
            
            # If no end_time provided, default to 1 hour after start
            if end_time_iso:
                end_time = self._iso_to_unix_timestamp(end_time_iso, user_context.get("timezone", "UTC"))
            else:
                end_time = start_time + 3600  # Add 1 hour
            
            request_body = {
                "title": event_details.get("title", "New Event"),
                "description": event_details.get("description", ""),
                "location": event_details.get("location", ""),
                "when": {
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_timezone": user_context.get("timezone", "UTC"),
                    "end_timezone": user_context.get("timezone", "UTC")
                }
            }
            
            # Add participants if provided
            if event_details.get("participants"):
                participants_list = []
                for p in event_details["participants"]:
                    if isinstance(p, str):
                        # If it's just a name string, create placeholder email
                        email_placeholder = f"{p.replace(' ', '.').lower()}@example.com"
                        participants_list.append({
                            "email": email_placeholder,
                            "name": p,
                            "status": "noreply"
                        })
                    else:
                        # It's already a dict, use existing email or generate placeholder
                        email_to_use = p.get("email", "")
                        if not email_to_use:
                            name_for_email = p.get("name", "unknown")
                            email_to_use = f"{name_for_email.replace(' ', '.').lower()}@example.com"
                        participants_list.append({
                            "email": email_to_use,
                            "name": p.get("name", ""),
                            "status": "noreply"
                        })
                request_body["participants"] = participants_list
            
            # Add reminders if provided
            if event_details.get("reminders"):
                request_body["reminders"] = {
                    "use_default": False,
                    "overrides": [
                        {
                            "reminder_minutes": r,
                            "reminder_method": "email"
                        }
                        for r in event_details["reminders"]
                    ]
                }
            
            # Create the event with calendar_id as query parameter
            event = client.events.create(
                identifier=grant_id,
                request_body=request_body,
                query_params={
                    "calendar_id": event_details.get("calendar_id", "primary"),
                    "notify_participants": event_details.get("notify_participants", True)
                }
            )
            
            # Get event title safely
            try:
                if hasattr(event, 'data') and hasattr(event.data, 'title'):
                    event_title = event.data.title
                elif hasattr(event, 'title'):
                    event_title = event.title
                else:
                    event_title = "Unknown Event"
            except:
                event_title = "Unknown Event"
            
            # Build intelligent message based on context and action type
            when_str = self._format_event_time(event)
            
            if action_type == "event_create_conflict_reschedule":
                # Get original time from params context if available
                original_time = "the originally requested time"
                params = intent.get("params", {})
                if params and isinstance(params, dict):
                    context = params.get("context", "")
                    # Try to extract original time from context if stored there
                
                message = f"Successfully rescheduled '{event_title}' to {when_str} to avoid a time conflict. "
                
                # Add participant notification info
                if intent.get("involves_others"):
                    participant_count = len(event_details.get("participants", []))
                    if participant_count > 0:
                        message += f"All {participant_count} participants have been notified of the time change."
                else:
                    message += "The event has been created at the suggested alternative time."
                    
            elif action_type == "event_create_duplicate":
                message = f"Created duplicate event '{event_title}' at {when_str}. You now have multiple events with similar titles at this time."
                
                # Add participant info if event involves others
                if intent.get("involves_others"):
                    participant_count = len(event_details.get("participants", []))
                    if participant_count > 0:
                        message += f" This duplicate event will send invitations to {participant_count} participants."
            else:
                # Default message for regular event creation
                message = f"Scheduled '{event_title}' at {when_str}."
                
                if intent.get("involves_others"):
                    participant_count = len(event_details.get("participants", []))
                    if participant_count > 0:
                        participants = event_details.get("participants", [])
                        # Get emails or names from participants
                        participant_emails = []
                        for p in participants[:3]:
                            if isinstance(p, str):
                                participant_emails.append(p)
                            elif isinstance(p, dict):
                                participant_emails.append(p.get("email", p.get("name", "")))
                        if len(participants) > 3:
                            participant_emails.append(f"and {len(participants) - 3} others")
                        message += f" Invitations have been sent to: {', '.join(participant_emails)}."
            
            result = self._success_response(
                provider="nylas",
                action="created",
                data=self._serialize_event_safe(event),
                message=message
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to create duplicate Nylas event: {e}")
            return self._error_response("nylas", f"Failed to create duplicate event: {str(e)}")
    
    async def _update_nylas_event(self, client: NylasClient, grant_id: str, event_details: Dict[str, Any], intent: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing Nylas event."""
        try:
            event_id = event_details.get("event_id")
            if not event_id:
                # COMPREHENSIVE DEBUG: Event lookup process
                logger.info(f"[DEBUG] EVENT LOOKUP STARTING:")
                logger.info(f"  Event reference from AI: '{event_details.get('event_reference', '')}'")
                logger.info(f"  Calendar ID: {event_details.get('calendar_id', 'primary')}")
                
                # Use AI to find the event
                events = client.events.list(
                    identifier=grant_id,
                    query_params={
                        "calendar_id": event_details.get("calendar_id", "primary")
                    }
                )
                
                logger.info(f"[DEBUG] Found {len(events.data)} events in calendar")
                for i, event in enumerate(events.data):
                    event_times = self._extract_event_times_safe(event)
                    logger.info(f"  Event {i}: ID={getattr(event, 'id', 'unknown')}, Title={getattr(event, 'title', 'unknown')}, Times={event_times}")
                
                event_reference = event_details.get("event_reference", "")
                
                # Convert to dict format for AI
                event_dicts = [self._serialize_event(e) for e in events.data]
                
                logger.info(f"[DEBUG] Asking AI to find event matching: '{event_reference}'")
                
                # Use AI to find the matching event
                ai_result = self.task_ai.find_single_event_for_operation(
                    query=event_reference,
                    operation="update",
                    events=event_dicts,
                    user_context=user_context
                )
                
                logger.info(f"[DEBUG] AI RESULT: {ai_result}")
                
                if not ai_result["found"]:
                    logger.error(f"[DEBUG] AI could not find event matching '{event_reference}'")
                    return self._error_response("nylas", ai_result.get("reasoning", f"No event found matching '{event_reference}'"))
                
                if ai_result.get("ambiguous_matches"):
                    # Multiple matches - need clarification
                    logger.warning(f"[DEBUG] Multiple matches found: {ai_result['ambiguous_matches']}")
                    matches = []
                    for eid in ai_result["ambiguous_matches"][:3]:
                        event = next((e for e in events.data if e.id == eid), None)
                        if event:
                            matches.append({"id": event.id, "title": event.title})
                    
                    matches_str = ', '.join([f"{m['title']} (ID: {m['id']})" for m in matches])
                    return self._error_response(
                        "nylas", 
                        f"Multiple events match '{event_reference}'. Which one did you mean? Matches: {matches_str}"
                    )
                
                event_id = ai_result["event_id"]
                logger.info(f"[DEBUG] AI selected event ID: {event_id}")
            
            # Fetch the original event to preserve data
            original_event = client.events.find(
                identifier=grant_id,
                event_id=event_id,
                query_params={
                    "calendar_id": event_details.get("calendar_id", "primary")
                }
            )
            
            # COMPREHENSIVE DEBUG: Updates structure from AI
            updates = event_details.get("updates", {})
            logger.info(f"[DEBUG] UPDATES STRUCTURE FROM AI:")
            logger.info(f"  Raw event_details: {event_details}")
            logger.info(f"  Extracted updates: {updates}")
            logger.info(f"  Updates keys: {list(updates.keys()) if updates else 'None'}")
            
            request_body = {}
            
            if "title" in updates:
                request_body["title"] = updates["title"]
            if "description" in updates:
                request_body["description"] = updates["description"]
            if "location" in updates:
                request_body["location"] = updates["location"]
            if "start_time" in updates or "end_time" in updates:
                # Get original event times safely
                original_start, original_end = self._extract_event_times_safe(original_event)
                
                logger.info(f"[DEBUG] Original event times:")
                logger.info(f"  Original start: {original_start} ({datetime.fromtimestamp(original_start) if original_start else 'None'})")
                logger.info(f"  Original end: {original_end} ({datetime.fromtimestamp(original_end) if original_end else 'None'})")
                
                # Convert ISO datetime strings to Unix timestamps
                start_time_iso = updates.get("start_time")
                end_time_iso = updates.get("end_time")
                
                logger.info(f"[DEBUG] Update times from intent:")
                logger.info(f"  Start time ISO: {start_time_iso}")
                logger.info(f"  End time ISO: {end_time_iso}")
                
                # If only time is being updated (date portion matches today), preserve original date
                if start_time_iso and "T" in start_time_iso:
                    # Parse the new time
                    new_time_parts = start_time_iso.split("T")[1]
                    # Get original date
                    original_dt = datetime.fromtimestamp(original_start, tz=pytz.timezone(user_context.get("timezone", "UTC")))
                    # Combine original date with new time
                    new_dt_str = f"{original_dt.strftime('%Y-%m-%d')}T{new_time_parts}"
                    start_time = self._iso_to_unix_timestamp(new_dt_str, user_context.get("timezone", "UTC"))
                else:
                    start_time = self._iso_to_unix_timestamp(start_time_iso, user_context.get("timezone", "UTC")) if start_time_iso else original_start
                
                if end_time_iso and "T" in end_time_iso:
                    # Parse the new time
                    new_time_parts = end_time_iso.split("T")[1]
                    # Get original date
                    original_dt = datetime.fromtimestamp(original_end, tz=pytz.timezone(user_context.get("timezone", "UTC")))
                    # Combine original date with new time
                    new_dt_str = f"{original_dt.strftime('%Y-%m-%d')}T{new_time_parts}"
                    end_time = self._iso_to_unix_timestamp(new_dt_str, user_context.get("timezone", "UTC"))
                else:
                    end_time = self._iso_to_unix_timestamp(end_time_iso, user_context.get("timezone", "UTC")) if end_time_iso else original_end
                
                logger.info(f"[DEBUG] Final calculated timestamps:")
                logger.info(f"  Final start: {start_time} ({datetime.fromtimestamp(start_time) if start_time else 'None'})")
                logger.info(f"  Final end: {end_time} ({datetime.fromtimestamp(end_time) if end_time else 'None'})")
                logger.info(f"  Timezone: {user_context.get('timezone', 'UTC')}")
                
                request_body["when"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_timezone": user_context.get("timezone", "UTC"),
                    "end_timezone": user_context.get("timezone", "UTC")
                }
            if "participants" in updates:
                participants_list = []
                for p in updates["participants"]:
                    if isinstance(p, str):
                        # If it's just a name string, create placeholder email
                        email_placeholder = f"{p.replace(' ', '.').lower()}@example.com"
                        participants_list.append({
                            "email": email_placeholder,
                            "name": p,
                            "status": "noreply"
                        })
                    else:
                        # It's already a dict, use existing email or generate placeholder
                        email_to_use = p.get("email", "")
                        if not email_to_use:
                            name_for_email = p.get("name", "unknown")
                            email_to_use = f"{name_for_email.replace(' ', '.').lower()}@example.com"
                        participants_list.append({
                            "email": email_to_use,
                            "name": p.get("name", ""),
                            "status": p.get("status", "noreply")
                        })
                request_body["participants"] = participants_list
            
            # Debug logging for the API call
            logger.info(f"[DEBUG] Nylas update request:")
            logger.info(f"  Event ID: {event_id}")
            logger.info(f"  Grant ID: {grant_id}")
            logger.info(f"  Request body: {request_body}")
            logger.info(f"  Query params: calendar_id={event_details.get('calendar_id', 'primary')}, notify_participants={event_details.get('notify_participants', True)}")
            
            # Update the event
            event = client.events.update(
                identifier=grant_id,
                event_id=event_id,
                request_body=request_body,
                query_params={
                    "calendar_id": event_details.get("calendar_id", "primary"),
                    "notify_participants": event_details.get("notify_participants", True)
                }
            )
            
            # Debug logging for the response
            logger.info(f"[DEBUG] Nylas update response:")
            logger.info(f"  Response type: {type(event)}")
            logger.info(f"  Response: {event}")
            if hasattr(event, 'data'):
                logger.info(f"  Response data: {event.data}")
            if hasattr(event, '__dict__'):
                logger.info(f"  Response dict: {event.__dict__}")
            
            # Validate that the update actually worked by checking timestamps
            serialized_event = self._serialize_event_safe(event)
            returned_start = serialized_event.get("when", {}).get("start")
            returned_end = serialized_event.get("when", {}).get("end")
            
            if "when" in request_body:
                expected_start = request_body["when"]["start_time"]
                expected_end = request_body["when"]["end_time"]
                
                logger.info(f"[DEBUG] Timestamp validation:")
                logger.info(f"  Expected start: {expected_start}")
                logger.info(f"  Returned start: {returned_start}")
                logger.info(f"  Expected end: {expected_end}")
                logger.info(f"  Returned end: {returned_end}")
                
                if returned_start != expected_start or returned_end != expected_end:
                    logger.error(f"[ERROR] Nylas update failed - timestamps don't match!")
                    logger.error(f"  Expected: {expected_start} - {expected_end}")
                    logger.error(f"  Got: {returned_start} - {returned_end}")
                    return self._error_response(
                        "nylas",
                        f"Event update failed - Nylas returned wrong timestamps. Expected {expected_start}-{expected_end}, got {returned_start}-{returned_end}"
                    )
                else:
                    logger.info(f"[DEBUG] Timestamp validation PASSED - update successful")
            
            # CRITICAL: Verify the update actually persisted by re-querying the event
            logger.info(f"[DEBUG] Re-querying event to verify update persisted...")
            try:
                verification_event = client.events.find(
                    identifier=grant_id,
                    event_id=event_id,
                    query_params={
                        "calendar_id": event_details.get("calendar_id", "primary")
                    }
                )
                
                # Check if the re-queried event has the updated times
                verification_serialized = self._serialize_event_safe(verification_event)
                verification_start = verification_serialized.get("when", {}).get("start")
                verification_end = verification_serialized.get("when", {}).get("end")
                
                logger.info(f"[DEBUG] Verification query results:")
                logger.info(f"  Re-queried start: {verification_start}")
                logger.info(f"  Re-queried end: {verification_end}")
                
                if "when" in request_body:
                    expected_start = request_body["when"]["start_time"]
                    expected_end = request_body["when"]["end_time"]
                    
                    if verification_start != expected_start or verification_end != expected_end:
                        logger.error(f"[CRITICAL] UPDATE DID NOT PERSIST!")
                        logger.error(f"  Expected: {expected_start} - {expected_end}")
                        logger.error(f"  Re-query shows: {verification_start} - {verification_end}")
                        logger.error(f"  This means Nylas returned success but the update didn't actually work!")
                        
                        return self._error_response(
                            "nylas",
                            f"Update failed - Event still shows old times after update. Expected {expected_start}-{expected_end}, but re-query shows {verification_start}-{verification_end}. This indicates a Nylas sync issue."
                        )
                    else:
                        logger.info(f"[DEBUG] Re-query CONFIRMS update persisted in Nylas")
                        
            except Exception as e:
                logger.error(f"[DEBUG] Failed to re-query event for verification: {e}")
                # Don't fail the whole operation, but log this issue
            
            # Get event title safely
            try:
                if hasattr(event, 'data') and hasattr(event.data, 'title'):
                    event_title = event.data.title
                elif hasattr(event, 'title'):
                    event_title = event.title
                else:
                    event_title = "Unknown Event"
            except:
                event_title = "Unknown Event"
            
            # Build intelligent message for event update
            event_data = self._serialize_event_safe(event)
            message = f"Successfully updated '{event_title}'."
            
            # Add specific details about what was updated
            update_details = []
            if "when" in request_body:
                when_str = self._format_event_time(event)
                update_details.append(f"rescheduled to {when_str}")
            if "title" in request_body:
                update_details.append("title changed")
            if "location" in request_body:
                update_details.append("location updated")
            if "participants" in request_body:
                update_details.append("participants modified")
            
            if update_details:
                message = f"Successfully updated '{event_title}' - {', '.join(update_details)}."
            
            # Add participant notification info if event involves others
            if intent.get("involves_others") or event_data.get("participants"):
                participants = event_data.get("participants", [])
                if participants:
                    participant_count = len(participants)
                    message += f" All {participant_count} participants have been notified of the changes."
            
            result = self._success_response(
                provider="nylas",
                action="updated",
                data=event_data,
                message=message
            )
            
            # Add warning if involves others (keep for compatibility)
            if intent.get("involves_others"):
                result["warning"] = intent.get("warning", "This change affects other people")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to update Nylas event: {e}")
            return self._error_response("nylas", f"Failed to update event: {str(e)}")
    
    async def _cancel_nylas_event(self, client: NylasClient, grant_id: str, event_details: Dict[str, Any], intent: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a Nylas event."""
        try:
            event_id = event_details.get("event_id")
            if not event_id:
                # Use AI to find the event
                events = client.events.list(
                    identifier=grant_id,
                    query_params={
                        "calendar_id": event_details.get("calendar_id", "primary")
                    }
                )
                
                event_reference = event_details.get("event_reference", "")
                
                # Convert to dict format for AI
                event_dicts = [self._serialize_event(e) for e in events.data]
                
                # Use AI to find the matching event
                ai_result = self.task_ai.find_single_event_for_operation(
                    query=event_reference,
                    operation="cancel",
                    events=event_dicts,
                    user_context=user_context
                )
                
                if not ai_result["found"]:
                    return self._error_response("nylas", ai_result.get("reasoning", f"No event found matching '{event_reference}'"))
                
                if ai_result.get("ambiguous_matches"):
                    # Multiple matches - need clarification
                    matches = []
                    for eid in ai_result["ambiguous_matches"][:3]:
                        event = next((e for e in events.data if e.id == eid), None)
                        if event:
                            matches.append({"id": event.id, "title": event.title})
                    
                    matches_str = ', '.join([f"{m['title']} (ID: {m['id']})" for m in matches])
                    return self._error_response(
                        "nylas", 
                        f"Multiple events match '{event_reference}'. Which one did you mean? Matches: {matches_str}"
                    )
                
                event_id = ai_result["event_id"]
                event = next((e for e in events.data if e.id == event_id), None)
                event_title = event.title if event else "Event"
            else:
                # Get event details for the title
                event = client.events.find(
                    identifier=grant_id,
                    event_id=event_id,
                    query_params={
                        "calendar_id": event_details.get("calendar_id", "primary")
                    }
                )
                # Get event title safely
                try:
                    if hasattr(event, 'data') and hasattr(event.data, 'title'):
                        event_title = event.data.title
                    elif hasattr(event, 'title'):
                        event_title = event.title
                    else:
                        event_title = "Unknown Event"
                except:
                    event_title = "Unknown Event"
            
            # Get event details before deletion for intelligent messaging
            event_before_delete = None
            try:
                event_before_delete = client.events.find(
                    identifier=grant_id,
                    event_id=event_id,
                    query_params={
                        "calendar_id": event_details.get("calendar_id", "primary")
                    }
                )
            except:
                pass  # If we can't fetch, we'll use basic info
            
            # Delete (cancel) the event
            client.events.destroy(
                identifier=grant_id,
                event_id=event_id,
                query_params={
                    "calendar_id": event_details.get("calendar_id", "primary"),
                    "notify_participants": event_details.get("notify_participants", True)
                }
            )
            
            # Build intelligent cancellation message
            message = f"Successfully cancelled '{event_title}'."
            
            # Add participant notification info if we have event details
            if event_before_delete:
                event_data = self._serialize_event_safe(event_before_delete)
                participants = event_data.get("participants", [])
                if participants:
                    participant_count = len(participants)
                    message += f" Cancellation notifications have been sent to all {participant_count} participants."
            elif intent.get("involves_others"):
                # Fallback if we couldn't fetch event details
                message += " All participants have been notified of the cancellation."
            
            result = self._success_response(
                provider="nylas",
                action="cancelled",
                data={"event_id": event_id, "title": event_title},
                message=message
            )
            
            # Add warning if involves others (keep for compatibility)
            if intent.get("involves_others"):
                result["warning"] = intent.get("warning", "Cancellation notification sent to participants")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to cancel Nylas event: {e}")
            return self._error_response("nylas", f"Failed to cancel event: {str(e)}")
    
    # Helper methods for duplicate and conflict detection
    async def _check_duplicate_task(
        self,
        client: ReclaimClient,
        title: str
    ) -> Dict[str, Any]:
        """Check if a task with a similar title already exists."""
        try:
            # Get all active tasks
            tasks = Task.list(client)
            
            # Look for tasks with similar titles using fuzzy matching
            for task in tasks:
                # Skip completed, archived, and cancelled tasks
                if task.status in [TaskStatus.COMPLETE, TaskStatus.ARCHIVED, TaskStatus.CANCELLED]:
                    continue
                
                if CalendarIntelligence.titles_are_similar(task.title, title):
                    return {
                        "has_duplicate": True,
                        "existing_task": {
                            "id": task.id,
                            "title": task.title,
                            "status": task.status.value if hasattr(task.status, 'value') else str(task.status)
                        }
                    }
            
            return {"has_duplicate": False}
            
        except Exception as e:
            logger.error(f"Error checking for duplicate tasks: {e}")
            # If we can't check, assume no duplicate
            return {"has_duplicate": False}
    
    async def _check_duplicate_event(
        self,
        client: NylasClient,
        grant_id: str,
        title: str,
        start_time: int,
        end_time: int,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if an event with a similar title exists around the same time."""
        try:
            # Query events in a time window around the requested time (±4 hours)
            search_start = start_time - 14400  # 4 hours before
            search_end = end_time + 14400  # 4 hours after
            
            events = client.events.list(
                identifier=grant_id,
                query_params={
                    "calendar_id": "primary",
                    "start": search_start,
                    "end": search_end
                }
            )
            
            # Look for events with similar titles using fuzzy matching
            for event in events.data:
                if event.title and CalendarIntelligence.titles_are_similar(event.title, title):
                    # Check if the times are close (within 1 hour)
                    event_start = event.when.start_time
                    event_end = event.when.end_time if hasattr(event.when, 'end_time') else event_start + 3600
                    
                    if abs(event_start - start_time) < 3600:  # Within 1 hour
                        # Use the user's timezone for display
                        user_tz = pytz.timezone(user_context.get("timezone", "UTC"))
                        event_time = datetime.fromtimestamp(event_start, tz=user_tz)
                        return {
                            "has_duplicate": True,
                            "existing_event": {
                                "id": event.id,
                                "title": event.title,
                                "start": event_start,
                                "end": event_end,
                                "time_display": event_time.strftime('%-I:%M %p on %A, %B %-d')
                            }
                        }
            
            return {"has_duplicate": False}
            
        except Exception as e:
            logger.error(f"Error checking for duplicate events: {e}")
            # If we can't check, assume no duplicate
            return {"has_duplicate": False}
    
    async def _check_time_conflicts(
        self,
        client: NylasClient,
        grant_id: str,
        start_time: int,
        end_time: int,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if there are any events at the requested time, considering buffer times."""
        try:
            # Convert timestamps to datetime for buffer calculation
            tz = user_context["now"].tzinfo
            new_start = datetime.fromtimestamp(start_time, tz=tz)
            new_end = datetime.fromtimestamp(end_time, tz=tz)
            
            # Query events with a wider window to catch buffer conflicts
            buffer_minutes = CalendarIntelligence.MEETING_BUFFER_MINUTES
            query_start = start_time - (buffer_minutes * 60)
            query_end = end_time + (buffer_minutes * 60)
            
            events = client.events.list(
                identifier=grant_id,
                query_params={
                    "calendar_id": "primary",
                    "start": query_start,
                    "end": query_end
                }
            )
            
            # Check for any overlapping events (including buffer time)
            conflicting_events = []
            for event in events.data:
                if event.status != "cancelled":
                    event_start_ts = event.when.start_time
                    event_end_ts = event.when.end_time if hasattr(event.when, 'end_time') else event_start_ts + 3600
                    
                    event_start = datetime.fromtimestamp(event_start_ts, tz=tz)
                    event_end = datetime.fromtimestamp(event_end_ts, tz=tz)
                    
                    # Check if times conflict (including buffer)
                    if CalendarIntelligence.check_buffer_conflict(
                        new_start, new_end, event_start, event_end
                    ):
                        conflicting_events.append({
                            "id": event.id,
                            "title": event.title,
                            "start": event_start_ts,
                            "end": event_end_ts
                        })
            
            if conflicting_events:
                return {
                    "has_conflict": True,
                    "conflicting_events": conflicting_events,
                    # Keep 'conflict' for backward compatibility (first conflict)
                    "conflict": conflicting_events[0]
                }
            
            return {"has_conflict": False}
            
        except Exception as e:
            logger.error(f"Error checking for time conflicts: {e}")
            # If we can't check, assume no conflict to allow creation
            return {"has_conflict": False}
    
    async def _find_next_available_slot(
        self,
        client: NylasClient,
        grant_id: str,
        preferred_start: int,
        duration_seconds: int,
        user_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Find the next available time slot after the preferred start time."""
        try:
            # Convert to datetime objects for easier manipulation
            tz = user_context["now"].tzinfo
            current_time = datetime.fromtimestamp(preferred_start, tz=tz)
            duration = timedelta(seconds=duration_seconds)
            
            # Search for up to 14 days (2 weeks)
            max_days = 14
            search_end = current_time + timedelta(days=max_days)
            
            # Round to next 15-minute increment for cleaner times
            minutes = current_time.minute
            if minutes % 15 != 0:
                current_time = current_time.replace(minute=(minutes // 15 + 1) * 15, second=0, microsecond=0)
                if current_time.minute == 60:
                    current_time = current_time.replace(minute=0) + timedelta(hours=1)
            
            attempts = 0
            max_attempts = 200  # Prevent infinite loops
            
            while current_time < search_end and attempts < max_attempts:
                attempts += 1
                
                # Calculate slot end time
                slot_end = current_time + duration
                
                # Skip times that are too early or too late (but don't exclude them completely)
                # Just note them as outside preferred hours
                outside_preferred = False
                if current_time.hour < 8 or slot_end.hour > 19 or (slot_end.hour == 19 and slot_end.minute > 0):
                    outside_preferred = True
                
                # Check if this slot has any conflicts
                conflict_check = await self._check_time_conflicts(
                    client,
                    grant_id,
                    int(current_time.timestamp()),
                    int(slot_end.timestamp()),
                    user_context
                )
                
                if not conflict_check["has_conflict"]:
                    # Found an available slot!
                    return {
                        "start": current_time,
                        "end": slot_end,
                        "outside_preferred_hours": outside_preferred
                    }
                
                # Move to the end of the conflicting event + buffer
                conflict_end = conflict_check["conflict"]["end"]
                buffer = CalendarIntelligence.MEETING_BUFFER_MINUTES * 60
                next_time = datetime.fromtimestamp(conflict_end + buffer, tz=tz)
                
                # Round to next 15-minute increment
                minutes = next_time.minute
                if minutes % 15 != 0:
                    next_time = next_time.replace(minute=(minutes // 15 + 1) * 15, second=0, microsecond=0)
                    if next_time.minute == 60:
                        next_time = next_time.replace(minute=0) + timedelta(hours=1)
                
                current_time = next_time
            
            # If we still haven't found a slot, just return the next available time
            # This ensures we ALWAYS return something
            return {
                "start": current_time,
                "end": current_time + duration,
                "outside_preferred_hours": True
            }
            
        except Exception as e:
            logger.error(f"Error finding next available slot: {e}")
            # Even on error, return something reasonable
            fallback_time = datetime.fromtimestamp(preferred_start, tz=user_context["now"].tzinfo)
            return {
                "start": fallback_time + timedelta(hours=1),
                "end": fallback_time + timedelta(hours=1) + timedelta(seconds=duration_seconds),
                "outside_preferred_hours": True
            }
    
    # Helper methods
    def _serialize_task(self, task: Task) -> Dict[str, Any]:
        """Serialize a Reclaim task."""
        return {
            "id": task.id,
            "title": task.title,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "due": task.due.isoformat() if task.due else None
        }
    
    def _serialize_event(self, event) -> Dict[str, Any]:
        """Serialize a Nylas event safely - now uses safe access."""
        return self._serialize_event_safe(event)
    
    def _format_event_time(self, event) -> str:
        """Format event time for human-readable messages."""
        try:
            if hasattr(event, 'when'):
                when = event.when
                if isinstance(when, dict):
                    start_timestamp = when.get('start_time', when.get('start'))
                    if start_timestamp:
                        from datetime import datetime
                        dt = datetime.fromtimestamp(start_timestamp)
                        return dt.strftime("%I:%M %p on %A, %B %d")
            return "the scheduled time"
        except:
            return "the scheduled time"
    
    def _serialize_event_safe(self, event) -> Dict[str, Any]:
        """Safely serialize a Nylas event, handling different response formats."""
        try:
            # Try the standard format first (event.data)
            if hasattr(event, 'data'):
                event_data = event.data
                when_data = event_data.when if hasattr(event_data, 'when') else None
                
                # Extract participants if available
                participants = []
                if hasattr(event_data, 'participants'):
                    participants = [
                        {
                            "email": getattr(p, 'email', ''),
                            "name": getattr(p, 'name', ''),
                            "status": getattr(p, 'status', '')
                        }
                        for p in event_data.participants
                    ]
                
                return {
                    "id": getattr(event_data, 'id', 'unknown'),
                    "title": getattr(event_data, 'title', 'Unknown Event'),
                    "when": {
                        "start": getattr(when_data, 'start_time', None) if when_data else None,
                        "end": getattr(when_data, 'end_time', None) if when_data and hasattr(when_data, 'end_time') else None
                    },
                    "participants": participants
                }
            # Try direct access (event.id, event.title)
            elif hasattr(event, 'id'):
                when_data = event.when if hasattr(event, 'when') else None
                
                # Extract participants if available
                participants = []
                if hasattr(event, 'participants'):
                    participants = [
                        {
                            "email": getattr(p, 'email', ''),
                            "name": getattr(p, 'name', ''),
                            "status": getattr(p, 'status', '')
                        }
                        for p in event.participants
                    ]
                
                return {
                    "id": getattr(event, 'id', 'unknown'),
                    "title": getattr(event, 'title', 'Unknown Event'),
                    "when": {
                        "start": getattr(when_data, 'start_time', None) if when_data else None,
                        "end": getattr(when_data, 'end_time', None) if when_data and hasattr(when_data, 'end_time') else None
                    },
                    "participants": participants
                }
            # Fallback for unknown formats
            else:
                return {
                    "id": "unknown",
                    "title": "Unknown Event",
                    "when": {
                        "start": None,
                        "end": None
                    }
                }
        except Exception as e:
            logger.warning(f"Failed to serialize event: {e}")
            return {
                "id": "unknown",
                "title": "Unknown Event",
                "when": {
                    "start": None,
                    "end": None
                }
            }
    
    def _extract_event_times_safe(self, event) -> tuple:
        """Safely extract start and end times from a Nylas event object."""
        try:
            # Try the standard format first (event.data.when)
            if hasattr(event, 'data') and hasattr(event.data, 'when'):
                when_data = event.data.when
                start_time = getattr(when_data, 'start_time', None)
                end_time = getattr(when_data, 'end_time', None)
                return start_time, end_time
            # Try direct access (event.when)
            elif hasattr(event, 'when'):
                when_data = event.when
                start_time = getattr(when_data, 'start_time', None)
                end_time = getattr(when_data, 'end_time', None)
                return start_time, end_time
            # Fallback - return None for both
            else:
                logger.warning("Could not extract event times - unknown format")
                return None, None
        except Exception as e:
            logger.warning(f"Failed to extract event times: {e}")
            return None, None
    
    def _success_response(self, provider: str, action: str, data: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Create a success response."""
        return {
            "success": True,
            "provider": provider,
            "action": action,
            "data": data,
            "message": message
        }
    
    def _error_response(self, provider: str, error: str, *args, **kwargs) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "success": False,
            "error": f"{error}",
            "provider": provider
        }