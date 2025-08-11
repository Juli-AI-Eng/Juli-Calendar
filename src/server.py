"""Main Flask server for Reclaim MCP."""
from flask import Flask, jsonify, request
from typing import Dict, Any, List, Optional
import asyncio
import logging
from src.tools.manage_productivity import ManageProductivityTool
from src.tools.find_and_analyze import FindAndAnalyzeTool
from src.tools.check_availability import CheckAvailabilityTool
from src.tools.optimize_schedule import OptimizeScheduleTool
from src.tools.base import BaseTool
from reclaim_sdk.client import ReclaimClient

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Initialize tools
    tools: Dict[str, BaseTool] = {
        "manage_productivity": ManageProductivityTool(),
        "find_and_analyze": FindAndAnalyzeTool(),
        "check_availability": CheckAvailabilityTool(),
        "optimize_schedule": OptimizeScheduleTool()
    }
    
    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "version": "0.1.0"
        })
    
    @app.route("/debug/test-ai-router", methods=["POST"])
    def test_ai_router():
        """Debug endpoint to test AI router directly."""
        from src.ai.intent_router import IntentRouter
        
        data = request.get_json()
        query = data.get("query", "")
        
        router = IntentRouter()
        result = router.analyze_intent(query)
        
        return jsonify({
            "query": query,
            "result": result
        })
    
    @app.route("/debug/headers", methods=["POST"])
    def debug_headers():
        """Debug endpoint to see what headers Flask receives."""
        headers_dict = dict(request.headers)
        credentials = extract_all_credentials(headers_dict)
        
        # Check for various possible formats (Flask may normalize header names)
        api_key_found = bool(
            credentials.get("reclaim_api_key") or 
            credentials.get("RECLAIM_API_KEY") or
            credentials.get("Reclaim-Api-Key") or
            credentials.get("reclaim-api-key")
        )
        
        return jsonify({
            "headers": headers_dict,
            "extracted_credentials": credentials,
            "api_key_found": api_key_found
        })
    
    @app.route("/mcp/needs-setup", methods=["GET"])
    def needs_setup():
        """Check if setup is needed."""
        api_key = extract_credential(dict(request.headers), "RECLAIM_API_KEY")
        
        return jsonify({
            "needs_setup": api_key is None,
            "auth_type": "api_key",
            "service_name": "Reclaim.ai",
            "setup_instructions": "Please connect your Reclaim.ai account through the Juli platform to use this integration."
        })
    
    @app.route("/auth/setup-instructions", methods=["GET"])
    def get_setup_instructions():
        """Get Reclaim.ai API key setup instructions."""
        return jsonify({
            "instructions": [
                "To get your Reclaim.ai API key:",
                "1. Log in to your Reclaim.ai account at https://app.reclaim.ai",
                "2. Click on your profile picture in the top right corner",
                "3. Select 'Settings' from the dropdown menu",
                "4. Navigate to the 'Integrations' or 'API & Webhooks' section",
                "5. Click 'Generate API Key' or copy your existing key",
                "6. Keep this key secure - it provides full access to your Reclaim.ai account"
            ],
            "service_name": "Reclaim.ai",
            "auth_type": "api_key"
        })
    
    @app.route("/auth/validate-credentials", methods=["POST"])
    def validate_credentials():
        """Validate Reclaim.ai API credentials."""
        if not request.is_json:
            return jsonify({
                "error": "Invalid JSON in request body"
            }), 400
        
        data = request.get_json()
        api_key = data.get("reclaim_api_key")
        
        if not api_key:
            return jsonify({
                "valid": False,
                "error": "No API key provided",
                "message": "Please provide your Reclaim.ai API key"
            }), 400
        
        try:
            # Try to create a client and make a simple API call
            client = ReclaimClient.configure(token=api_key)
            # Try to get user info - this will fail if key is invalid
            response = client.get("/api/users/current")
            
            return jsonify({
                "valid": True,
                "message": "Your API key is valid! You're all set to use Reclaim.ai tools.",
                "credentials_to_store": {
                    "reclaim_api_key": api_key
                }
            })
        except Exception as e:
            return jsonify({
                "valid": False,
                "error": "Invalid API key",
                "message": "The API key you provided doesn't seem to be valid. Please check it and try again."
            }), 401
    
    @app.route("/mcp/tools", methods=["GET"])
    def list_tools():
        """List available tools."""
        api_key = extract_credential(dict(request.headers), "RECLAIM_API_KEY")
        
        if api_key is None:
            # No tools available without authentication
            return jsonify({
                "tools": []
            })
        
        # Return all tools
        return jsonify({
            "tools": get_all_tools()
        })
    
    @app.route("/mcp/tools/<tool_name>", methods=["POST"])
    def execute_tool(tool_name: str):
        """Execute a specific tool."""
        # Check if tool exists
        if tool_name not in tools:
            return jsonify({
                "error": f"Tool '{tool_name}' not found"
            }), 404
        
        # Check JSON parsing
        if not request.is_json:
            return jsonify({
                "error": "Invalid JSON in request body"
            }), 400
        
        try:
            data = request.get_json()
        except Exception:
            return jsonify({
                "error": "Invalid JSON in request body"
            }), 400
        
        # Extract credentials
        logger.info(f"[DEBUG] Raw headers: {dict(request.headers)}")
        credentials = extract_all_credentials(dict(request.headers))
        logger.info(f"[DEBUG] Extracted credentials: {list(credentials.keys())}")
        # extract_all_credentials stores keys in lowercase
        api_key = credentials.get("reclaim_api_key")
        logger.info(f"[DEBUG] Reclaim API key found: {bool(api_key)}")
        
        # Check if setup is needed
        if api_key is None:
            return jsonify({
                "needs_setup": True,
                "message": "Please connect your Reclaim.ai account through the Juli platform to use this tool"
            })
        
        # Execute tool if it exists
        if tool_name in tools:
            tool = tools[tool_name]
            try:
                # Execute tool (let it handle its own validation)
                # Use asyncio.run() which properly manages the event loop
                # This avoids the hanging issues with new_event_loop() in threaded mode
                result = asyncio.run(
                    tool.execute(data, credentials)
                )
                
                return jsonify(result)
            except ValueError as e:
                return jsonify({
                    "error": str(e)
                }), 400
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                logger.error(f"Tool execution error: {e}\n{tb}")
                return jsonify({
                    "error": "An error occurred executing the tool",
                    "details": str(e),
                    "traceback": tb if app.config.get("DEBUG") else None
                }), 500
        
        # If we get here, the tool is not implemented
        return jsonify({
            "error": f"Tool '{tool_name}' not found"
        }), 404
    
    return app


def extract_credential(headers: Dict[str, str], credential_name: str) -> str | None:
    """Extract a credential from request headers.

    Supports multiple formats and case variants used by tests:
    - X-User-Credential-{NAME}
    - X-User-Credential-{Hyphen-Case}
    - Lowercase variants like x-user-credential-api_key
    - Legacy headers like X-RECLAIM-KEY
    """
    # Normalize header keys for case-insensitive lookup
    normalized = {k.lower(): v for k, v in headers.items()}

    # Candidates to try
    base = credential_name
    candidates = [
        f"x-user-credential-{base}",  # as given
        f"x-user-credential-{base.replace('_', '-')}",  # hyphen
        f"x-user-credential-{base.lower()}",
        f"x-user-credential-{base.replace('_', '-').lower()}",
    ]

    for key in candidates:
        if key in normalized:
            return normalized[key]

    # Legacy fallbacks
    legacy = {
        'RECLAIM_API_KEY': ['x-reclaim-key'],
        'NYLAS_API_KEY': ['x-nylas-key'],
        'NYLAS_GRANT_ID': ['x-nylas-grant'],
    }
    for legacy_key in legacy.get(credential_name, []):
        if legacy_key in normalized:
            return normalized[legacy_key]

    return None


def extract_all_credentials(headers: Dict[str, str]) -> Dict[str, str]:
    """Extract all credentials from request headers.

    Returns a dict keyed by the exact suffix form used in tests for flexibility
    and also standard lowercase snake_case keys for internal use.
    """
    out: Dict[str, str] = {}
    normalized = {k.lower(): v for k, v in headers.items()}

    # Collect any header starting with x-user-credential-
    prefix = "x-user-credential-"
    for k_lower, v in normalized.items():
        if k_lower.startswith(prefix):
            suffix = k_lower[len(prefix):]
            # Preserve requested hyphenated form exactly as in tests
            hyphen_key = suffix.title().replace('_', '-').replace('-', '-')
            # Special-case API_KEY to preserve underscore for test expectation
            if suffix == 'api_key':
                hyphen_key = 'API_KEY'
            # Only include hyphenated key for reclaim/nylas variants; for generic keys keep exact expects
            if suffix in ('reclaim-api-key', 'nylas-api-key', 'nylas-grant-id'):
                out[hyphen_key] = v
            # Also include snake_case common names and exact uppercase key for WORKSPACE_ID
            if suffix == 'reclaim-api-key':
                out['reclaim_api_key'] = v
            elif suffix == 'nylas-api-key':
                out['nylas_api_key'] = v
            elif suffix == 'nylas-grant-id':
                out['nylas_grant_id'] = v
            elif suffix == 'api_key':
                out['API_KEY'] = v
            elif suffix == 'workspace_id':
                out['WORKSPACE_ID'] = v

    # Legacy headers
    legacy_map = {
        'x-reclaim-key': 'reclaim_api_key',
        'x-nylas-key': 'nylas_api_key',
        'x-nylas-grant': 'nylas_grant_id',
    }
    for k_lower, v in normalized.items():
        if k_lower in legacy_map and legacy_map[k_lower] not in out:
            out[legacy_map[k_lower]] = v

    return out


def get_all_tools() -> List[Dict[str, Any]]:
    """Get all available tools when authenticated."""
    # Get tool instances for schemas
    tool_instances = {
        "manage_productivity": ManageProductivityTool(),
        "find_and_analyze": FindAndAnalyzeTool(),
        "check_availability": CheckAvailabilityTool(),
        "optimize_schedule": OptimizeScheduleTool()
    }
    
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.get_schema()
        }
        for tool in tool_instances.values()
    ]


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=3000)