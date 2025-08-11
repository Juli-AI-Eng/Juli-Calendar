"""A2A protocol handlers for Juli Calendar Agent."""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Request
import json

logger = logging.getLogger(__name__)


def get_agent_card() -> Dict[str, Any]:
    """Get the A2A Agent Card for discovery."""
    return {
        "agent_id": "juli-calendar",
        "agent_name": "Juli Calendar Agent",
        "version": "2.0.0",
        "description": "AI-powered calendar and task management agent for Juli",
        "author": {
            "name": "Juli AI",
            "email": "support@juli-ai.com"
        },
        "capabilities": {
            "tools": [
                {
                    "name": "manage_productivity",
                    "description": "Create, update, and manage tasks and calendar events using natural language"
                },
                {
                    "name": "check_availability",
                    "description": "Check calendar availability and find free time slots"
                },
                {
                    "name": "find_and_analyze",
                    "description": "Search and analyze calendar events and tasks"
                }
            ]
        },
        "auth": {
            "schemes": [
                {
                    "type": "oidc",
                    "issuers": ["https://auth.juli-ai.com"],
                    "audiences": ["juli-calendar"]
                },
                {
                    "type": "dev_secret",
                    "header": "X-A2A-Dev-Secret",
                    "description": "Development authentication using shared secret"
                }
            ]
        },
        "rpc": {
            "endpoint": "/a2a/rpc",
            "version": "2.0"
        },
        "approvals": {
            "required_for": [
                "event_create_with_participants",
                "bulk_operation",
                "event_create_conflict_reschedule",
                "duplicate_task_creation"
            ],
            "description": "Approvals required for operations affecting multiple items or involving other people"
        },
        "context": {
            "injections": [
                "user_name",
                "user_email",
                "user_timezone",
                "current_date",
                "current_time"
            ],
            "description": "User context automatically injected by Juli"
        },
        "server_time": datetime.utcnow().isoformat() + "Z"
    }


def get_credentials_manifest() -> Dict[str, Any]:
    """Get the credentials manifest for credential acquisition."""
    return {
        "version": "1.0",
        "credentials": [
            {
                "key": "RECLAIM_API_KEY",
                "display_name": "Reclaim.ai API Key",
                "description": "Your personal API key from Reclaim.ai for task management",
                "sensitive": True,
                "required": True,
                "flows": [
                    {
                        "type": "api_key",
                        "instructions": "Get your API key from Reclaim.ai:\n1. Go to https://app.reclaim.ai\n2. Click Settings → Integrations → API\n3. Copy your API key",
                        "validation_endpoint": "/setup/validate-reclaim"
                    }
                ]
            },
            {
                "key": "NYLAS_GRANT_ID",
                "display_name": "Calendar Account Grant",
                "description": "Grant for accessing your calendar (Google, Microsoft, etc)",
                "sensitive": True,
                "required": True,
                "flows": [
                    {
                        "type": "hosted_auth",
                        "connect_url": "/setup/connect-url",
                        "callback": "/api/nylas-calendar/callback",
                        "providers": ["google", "microsoft"],
                        "provider_scopes": {
                            "google": [
                                "openid",
                                "https://www.googleapis.com/auth/userinfo.email",
                                "https://www.googleapis.com/auth/calendar",
                                "https://www.googleapis.com/auth/calendar.events",
                                "https://www.googleapis.com/auth/tasks"
                            ],
                            "microsoft": [
                                "openid",
                                "email",
                                "Calendars.ReadWrite",
                                "Tasks.ReadWrite",
                                "User.Read"
                            ]
                        }
                    }
                ]
            }
        ]
    }


def authenticate_agent(request: Request) -> bool:
    """
    Authenticate incoming A2A agent requests.
    
    Returns True if authenticated, False otherwise.
    """
    # Check for development secret
    dev_secret = request.headers.get('X-A2A-Dev-Secret')
    expected_secret = os.getenv('A2A_DEV_SECRET')
    
    if dev_secret and expected_secret and dev_secret == expected_secret:
        logger.info("A2A agent authenticated via dev secret")
        return True
    
    # Check for OIDC bearer token
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
        
        # In development mode, accept any bearer token
        if os.getenv('FLASK_ENV') == 'development':
            logger.info("A2A agent authenticated via bearer token (dev mode)")
            return True
        
        # TODO: Implement proper OIDC token validation
        # This would involve:
        # 1. Decoding the JWT
        # 2. Verifying the signature
        # 3. Checking issuer and audience
        # 4. Validating expiration
        
        logger.warning("OIDC token validation not yet implemented")
        return False
    
    logger.warning("A2A agent authentication failed - no valid credentials")
    return False


async def handle_rpc_request(request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle incoming JSON-RPC 2.0 requests.
    
    Args:
        request_data: The JSON-RPC request body
        headers: HTTP headers containing credentials
        
    Returns:
        JSON-RPC response
    """
    # Extract RPC components
    jsonrpc = request_data.get('jsonrpc')
    method = request_data.get('method')
    params = request_data.get('params', {})
    request_id = request_data.get('id')
    
    # Validate JSON-RPC version
    if jsonrpc != '2.0':
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32600,
                "message": "Invalid Request - must be JSON-RPC 2.0"
            }
        }
    
    try:
        # Route to appropriate handler
        if method == 'agent.card':
            result = get_agent_card()
            
        elif method == 'agent.handshake':
            result = {
                "agent": "juli-calendar",
                "card": get_agent_card(),
                "server_time": datetime.utcnow().isoformat() + "Z"
            }
            
        elif method == 'tool.execute':
            # Import here to avoid circular dependency
            from .tool_adapter import execute_tool_rpc
            result = await execute_tool_rpc(params, headers)
            
        elif method == 'tool.approve':
            # Import here to avoid circular dependency
            from .tool_adapter import approve_tool_rpc
            result = await approve_tool_rpc(params, headers)
            
        elif method == 'tool.list':
            # List available tools
            card = get_agent_card()
            result = {
                "tools": card["capabilities"]["tools"]
            }
            
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        # Return successful response
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        
    except ValueError as e:
        logger.error(f"Validation error in RPC handler: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32602,
                "message": "Invalid params",
                "data": str(e)
            }
        }
        
    except Exception as e:
        logger.error(f"Internal error in RPC handler: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e) if os.getenv('FLASK_ENV') == 'development' else None
            }
        }