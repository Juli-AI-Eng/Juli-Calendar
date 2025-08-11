"""Main Flask server for Juli Calendar Agent with A2A protocol."""
from flask import Flask, jsonify, request
from typing import Dict, Any
import logging
from src.tools.manage_productivity import ManageProductivityTool
from src.tools.find_and_analyze import FindAndAnalyzeTool
from src.tools.check_availability import CheckAvailabilityTool
from src.tools.optimize_schedule import OptimizeScheduleTool
from src.tools.base import BaseTool

# Import A2A handlers
from src.a2a import (
    get_agent_card,
    get_credentials_manifest,
    handle_rpc_request,
    authenticate_agent
)

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
        return jsonify({
            "headers": headers_dict,
            "a2a_auth_present": bool(
                headers_dict.get("X-A2A-Dev-Secret") or 
                headers_dict.get("Authorization")
            )
        })
    
    # ===== A2A (Agent-to-Agent) Endpoints =====
    
    @app.route("/.well-known/a2a.json", methods=["GET"])
    def a2a_discovery():
        """A2A discovery endpoint returning the Agent Card."""
        return jsonify(get_agent_card())
    
    @app.route("/.well-known/a2a-credentials.json", methods=["GET"])
    def a2a_credentials():
        """A2A credentials manifest for credential acquisition."""
        return jsonify(get_credentials_manifest())
    
    @app.route("/a2a/rpc", methods=["POST"])
    async def a2a_rpc():
        """Handle A2A JSON-RPC 2.0 requests."""
        # Authenticate the agent
        if not authenticate_agent(request):
            return jsonify({
                "jsonrpc": "2.0",
                "id": request.json.get('id') if request.is_json else None,
                "error": {
                    "code": -32000,
                    "message": "Unauthorized agent",
                    "data": "Authentication failed - provide valid OIDC token or dev secret"
                }
            }), 401
        
        # Validate JSON request
        if not request.is_json:
            return jsonify({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error - invalid JSON"
                }
            }), 400
        
        try:
            request_data = request.get_json()
            headers = dict(request.headers)
            
            # Handle the RPC request
            result = await handle_rpc_request(request_data, headers)
            
            # Return the response
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"A2A RPC error: {e}", exc_info=True)
            return jsonify({
                "jsonrpc": "2.0",
                "id": request.json.get('id') if request.is_json else None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e) if app.config.get("DEBUG") else None
                }
            }), 500
    
    
    return app




if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=3000)