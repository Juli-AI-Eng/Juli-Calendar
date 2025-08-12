"""A2A protocol handlers for Juli Calendar Agent."""

import os
import logging
import jwt
import requests
import time
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Request
import json

logger = logging.getLogger(__name__)


def validate_oidc_token(token: str) -> bool:
    """
    Validate OIDC JWT token according to A2A protocol.
    
    Args:
        token: The JWT token to validate
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    try:
        # Decode token without verification first to get header info
        unverified_header = jwt.get_unverified_header(token)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        
        # Extract issuer and audience
        issuer = unverified_payload.get('iss')
        audience = unverified_payload.get('aud')
        
        # Validate issuer against allowed issuers
        allowed_issuers = get_allowed_issuers()
        if issuer not in allowed_issuers:
            logger.warning(f"Invalid issuer: {issuer}")
            return False
        
        # Validate audience
        allowed_audiences = ["juli-calendar"]
        if audience not in allowed_audiences:
            logger.warning(f"Invalid audience: {audience}")
            return False
        
        # Get JWKS from issuer to validate signature
        try:
            jwks_url = f"{issuer}/.well-known/jwks.json"
            jwks_response = requests.get(jwks_url, timeout=10)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from {jwks_url}: {e}")
            # In production, we should fail here. For now, log and continue.
            return False
        
        # Find matching key
        kid = unverified_header.get('kid')
        public_key = None
        
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                try:
                    from jwt.algorithms import RSAAlgorithm
                    public_key = RSAAlgorithm.from_jwk(key)
                    break
                except Exception as e:
                    logger.error(f"Failed to parse JWK: {e}")
                    continue
        
        if not public_key:
            logger.warning(f"No matching key found for kid: {kid}")
            return False
        
        # Verify the token with the public key
        try:
            decoded_token = jwt.decode(
                token, 
                public_key, 
                algorithms=['RS256'],
                audience=audience,
                issuer=issuer,
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True
                }
            )
            
            logger.info(f"OIDC token validated successfully for subject: {decoded_token.get('sub')}")
            return True
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return False
        except jwt.InvalidAudienceError:
            logger.warning("Invalid audience in token")
            return False
        except jwt.InvalidIssuerError:
            logger.warning("Invalid issuer in token")
            return False
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return False
            
    except Exception as e:
        logger.error(f"OIDC token validation error: {e}")
        return False


def get_agent_card() -> Dict[str, Any]:
    """Get the A2A Agent Card for discovery."""
    return {
        "agent_id": "juli-calendar",
        "version": "2.0.0", 
        "description": "Calendar and task management agent that can create events, manage tasks, check availability, and optimize schedules. Supports approval-first execution and agent-to-agent auth.",
        "auth": [
            {
                "type": "oidc",
                "audience": "juli-calendar",
                "issuers": ["https://auth.juli-ai.com"]
            },
            {
                "type": "shared_secret",
                "header": "X-A2A-Dev-Secret"
            }
        ],
        "approvals": {
            "modes": ["stateless_preview_then_approve"]
        },
        "context_requirements": {
            "credentials": ["RECLAIM_API_KEY", "NYLAS_GRANT_ID"]
        },
        "capabilities": [
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
            },
            {
                "name": "optimize_schedule",
                "description": "AI-powered schedule optimization and time management"
            }
        ],
        "rpc": {
            "endpoint": "/a2a/rpc"
        },
        "extensions": {
            "x-juli": {
                "credentials_manifest": "/.well-known/a2a-credentials.json"
            }
        }
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
                        "type": "manual_with_validation",
                        "instructions": "Get your API key from Reclaim.ai:\n1. Go to https://app.reclaim.ai/settings/developer\n2. Click 'Generate New API Key'\n3. Name it 'Juli Integration'\n4. Copy the key (this is a long alphanumeric string)",
                        "validation_endpoint": "/setup/validate-reclaim",
                        "deep_link": "https://app.reclaim.ai/settings/developer",
                        "format_hint": "Long alphanumeric API key"
                    }
                ]
            },
            {
                "key": "NYLAS_GRANT_ID",
                "display_name": "Calendar Account",
                "description": "Connect your calendar (Google, Outlook, or iCloud)",
                "sensitive": True,
                "required": True,
                "flows": [
                    {
                        "type": "hosted_auth",
                        "connect_url": "/setup/connect-url",
                        "callback": "/api/nylas-calendar/callback",
                        "providers": ["google", "microsoft", "icloud"],
                        "provider_scopes": {
                            "google": [
                                "calendar",
                                "calendar.readonly",
                                "calendar.events", 
                                "calendar.events.readonly",
                                "admin.directory.resource.calendar.readonly",
                                "contacts",
                                "contacts.readonly",
                                "contacts.other.readonly"
                            ],
                            "microsoft": [
                                "Calendars.Read",
                                "Calendars.Read.Shared",
                                "Calendars.ReadWrite",
                                "Calendars.ReadWrite.Shared",
                                "Contacts.Read",
                                "Contacts.Read.Shared",
                                "Contacts.ReadWrite",
                                "Contacts.ReadWrite.Shared"
                            ],
                            "icloud": [
                                "calendar",
                                "contacts"
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
        
        # Implement OIDC token validation
        try:
            return validate_oidc_token(token)
        except Exception as e:
            logger.error(f"OIDC token validation failed: {e}")
            return False
    
    logger.warning("A2A agent authentication failed - no valid credentials")
    return False


def handle_rpc_request(request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
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
            result = execute_tool_rpc(params, headers)
            
        elif method == 'tool.approve':
            # Import here to avoid circular dependency
            from .tool_adapter import approve_tool_rpc
            result = approve_tool_rpc(params, headers)
            
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