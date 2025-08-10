"""Approval configuration for operations that require user confirmation."""
import os
from typing import Dict, Any


def get_approval_config() -> Dict[str, bool]:
    """
    Get the approval configuration for different operations.
    
    Returns a dictionary mapping operation types to whether they require approval.
    """
    # Always use the same configuration for both production and tests
    return {
        # Operations affecting others (always require approval)
        "event_create_with_participants": True,
        "event_update_with_participants": True,
        "event_cancel_with_participants": True,
        
        # Bulk operations (large changes require approval)
        "bulk_delete": True,
        "bulk_update": True,
        "bulk_complete": True,
        "bulk_reschedule": True,
        "bulk_cancel": True,
        
        # Major changes
        "recurring_create": True,
        "working_hours_update": True,
        
        # Duplicate detection approvals
        "task_create_duplicate": True,
        "event_create_duplicate": True,
        
        # Conflict resolution approvals
        "event_create_conflict_reschedule": True,
        
        # Single operations that don't need approval
        "task_create": False,
        "task_update": False,
        "task_complete": False,
        "task_cancel": False,  # Single task deletion - no approval needed
        "task_delete": False,  # Single task deletion - no approval needed
        "event_create": False,  # Solo events - no approval needed
        "event_update": False,  # Solo events - no approval needed
        "event_cancel": False,  # Solo events - no approval needed
        "event_delete": False,  # Solo events - no approval needed
    }


def requires_approval(operation_type: str, context: Dict[str, Any] = None) -> bool:
    """
    Check if a specific operation requires approval.
    
    Args:
        operation_type: The type of operation (e.g., "task_cancel", "event_create")
        context: Optional context with additional details (e.g., has_participants)
    
    Returns:
        bool: True if approval is required, False otherwise
    """
    approval_config = get_approval_config()
    
    # Handle special cases based on context
    if context:
        # Check if event has participants (handle both "event_" and "calendar_" prefixes)
        if operation_type in ["event_create", "calendar_create"] and context.get("has_participants"):
            return approval_config.get("event_create_with_participants", True)
        elif operation_type in ["event_update", "calendar_update"] and context.get("has_participants"):
            return approval_config.get("event_update_with_participants", True)
        elif operation_type in ["event_cancel", "calendar_cancel"] and context.get("has_participants"):
            return approval_config.get("event_cancel_with_participants", True)
        
        # Check if operation is bulk
        if context.get("is_bulk"):
            bulk_operation = f"bulk_{operation_type.split('_')[1]}"
            return approval_config.get(bulk_operation, True)
    
    # Default lookup
    return approval_config.get(operation_type, False)