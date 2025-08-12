"""Adapter to bridge A2A JSON-RPC requests to existing tool implementations."""

import os
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_credentials_from_context(user_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract and map credentials from A2A format to tool format.
    
    Args:
        user_context: User context from JSON-RPC params
        
    Returns:
        Mapped credentials for tools
    """
    credentials = user_context.get('credentials', {})
    
    # Map A2A credential keys to tool credential keys
    mapped = {
        'reclaim_api_key': credentials.get('RECLAIM_API_KEY'),
        'nylas_api_key': os.getenv('NYLAS_API_KEY'),  # Server-side key
        'nylas_grant_id': credentials.get('NYLAS_GRANT_ID') or credentials.get('EMAIL_ACCOUNT_GRANT')
    }
    
    # Filter out None values
    return {k: v for k, v in mapped.items() if v is not None}


def merge_context_with_arguments(arguments: Dict[str, Any], user_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge user context injections with tool arguments.
    
    Args:
        arguments: Tool arguments from JSON-RPC params
        user_context: User context containing timezone, date, etc.
        
    Returns:
        Merged parameters for tool execution
    """
    # Extract context values
    merged = dict(arguments)  # Start with tool arguments
    
    # Add context injections if not already present
    if 'user_timezone' not in merged:
        merged['user_timezone'] = user_context.get('timezone', 'UTC')
    
    if 'current_date' not in merged:
        merged['current_date'] = user_context.get('current_date', datetime.now().strftime('%Y-%m-%d'))
    
    if 'current_time' not in merged:
        merged['current_time'] = user_context.get('current_time', datetime.now().strftime('%H:%M:%S'))
    
    # Add optional context
    if 'user_name' not in merged and 'user_name' in user_context:
        merged['user_name'] = user_context['user_name']
    
    if 'user_email' not in merged and 'user_email' in user_context:
        merged['user_email'] = user_context['user_email']
    
    return merged


def execute_tool_rpc(params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Execute a tool via JSON-RPC parameters.
    
    Args:
        params: JSON-RPC params containing tool, arguments, user_context, request_id
        headers: HTTP headers
        
    Returns:
        Tool execution result
    """
    # Extract parameters
    tool_name = params.get('tool')
    arguments = params.get('arguments', {})
    user_context = params.get('user_context', {})
    request_id = params.get('request_id')
    
    if not tool_name:
        raise ValueError("Missing required parameter: tool")
    
    # Import tools here to avoid circular dependency
    from src.tools import get_tool_by_name
    
    # Get the tool instance
    tool = get_tool_by_name(tool_name)
    if not tool:
        raise ValueError(f"Tool not found: {tool_name}")
    
    # Extract and map credentials
    credentials = extract_credentials_from_context(user_context)
    
    # Check if credentials are needed
    if tool_name in ['manage_productivity', 'check_availability', 'find_and_analyze']:
        if not credentials.get('reclaim_api_key') and not credentials.get('nylas_grant_id'):
            return {
                "needs_setup": True,
                "message": "Please complete setup to use this tool",
                "setup_instructions": "You need to provide either a Reclaim API key or connect your calendar via Nylas",
                "connect_url": "/setup/connect-url"
            }
    
    # Merge context with arguments
    merged_params = merge_context_with_arguments(arguments, user_context)
    
    # Log the execution
    logger.info(f"Executing tool '{tool_name}' via A2A RPC (request_id: {request_id})")
    
    try:
        # Execute the tool
        result = tool.execute(merged_params, credentials)
        
        # Add request_id to result if it has approval flow
        if result.get('needs_approval') and request_id:
            result['request_id'] = request_id
        
        return result
        
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
        
        # Return user-friendly error
        return {
            "success": False,
            "error": str(e),
            "error_code": "TOOL_EXECUTION_ERROR",
            "tool": tool_name
        }


def approve_tool_rpc(params: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle tool approval via JSON-RPC.
    
    Args:
        params: JSON-RPC params containing tool, original_arguments, action_data, user_context
        headers: HTTP headers
        
    Returns:
        Approval execution result
    """
    # Extract parameters
    tool_name = params.get('tool')
    original_arguments = params.get('original_arguments', {})
    action_data = params.get('action_data', {})
    user_context = params.get('user_context', {})
    request_id = params.get('request_id')
    approved = params.get('approved', True)  # Default to approved
    
    if not tool_name:
        raise ValueError("Missing required parameter: tool")
    
    if not action_data:
        raise ValueError("Missing required parameter: action_data")
    
    # Import tools here to avoid circular dependency
    from src.tools import get_tool_by_name
    
    # Get the tool instance
    tool = get_tool_by_name(tool_name)
    if not tool:
        raise ValueError(f"Tool not found: {tool_name}")
    
    # Extract and map credentials
    credentials = extract_credentials_from_context(user_context)
    
    # Build approval request in the format expected by tools
    approval_params = {
        "approved": approved,
        "action_data": action_data,
        **original_arguments  # Include original arguments
    }
    
    # Merge context
    merged_params = merge_context_with_arguments(approval_params, user_context)
    
    # Log the approval
    logger.info(f"Processing approval for tool '{tool_name}' via A2A RPC (request_id: {request_id})")
    
    try:
        # Execute the approval
        result = tool.execute(merged_params, credentials)
        
        # Add request_id to result
        if request_id:
            result['request_id'] = request_id
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing approval for tool {tool_name}: {e}", exc_info=True)
        
        # Return user-friendly error
        return {
            "success": False,
            "error": str(e),
            "error_code": "APPROVAL_PROCESSING_ERROR",
            "tool": tool_name
        }