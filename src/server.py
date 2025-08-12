"""Main Flask server for Juli Calendar Agent with A2A protocol."""
from flask import Flask, jsonify, request, redirect
from typing import Dict, Any, Optional, List
import logging
import os
import secrets
import time
import requests
from urllib.parse import quote
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


def get_base_url():
    """
    Get the public base URL for the agent.
    Production: https://juli-ai.com
    Local: http://localhost:5002 (or configured port)
    """
    return os.getenv("A2A_PUBLIC_BASE_URL", "http://localhost:5002")


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
    def a2a_rpc():
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
            result = handle_rpc_request(request_data, headers)
            
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
    
    # ===== OAuth Setup Endpoints (Nylas) =====
    
    @app.route("/setup/connect-url", methods=["GET"])
    def setup_connect_url():
        """
        Return Nylas Hosted Auth URL as JSON (following Juli-Email pattern).
        This endpoint returns the URL that Juli Brain will redirect the user to.
        """
        try:
            nylas_client_id = os.getenv("NYLAS_CLIENT_ID")
            nylas_api_key = os.getenv("NYLAS_API_KEY")
            
            missing_vars = []
            if not nylas_client_id:
                missing_vars.append("NYLAS_CLIENT_ID")
            if not nylas_api_key:
                missing_vars.append("NYLAS_API_KEY")
            if missing_vars:
                logger.error(f"Missing environment variables for Nylas OAuth: {', '.join(missing_vars)}")
                return jsonify({
                    "error": f"Server not configured for Nylas OAuth. Missing environment variable(s): {', '.join(missing_vars)}."
                }), 500
            
            # Get the callback URL - in production this is https://juli-ai.com/api/nylas-calendar/callback
            callback_url = os.getenv("NYLAS_CALLBACK_URI", f"{get_base_url()}/api/nylas-calendar/callback")
            
            # Get optional parameters from query string
            provider = request.args.get("provider")  # optional, let Nylas show selection if not provided
            login_hint = request.args.get("login_hint")  # optional email hint
            
            # Import Nylas client
            from nylas import Client as NylasClient
            
            # Create Nylas client with API key
            nylas = NylasClient(
                api_key=nylas_api_key,
                api_uri=os.getenv("NYLAS_API_URI", "https://api.us.nylas.com")
            )
            
            # Build the OAuth URL using Nylas SDK (following Juli-Email pattern)
            # The Python SDK expects a config dictionary as a single parameter
            auth_config = {
                "client_id": nylas_client_id,
                "redirect_uri": callback_url,
            }
            # Only add provider if explicitly specified
            if provider:
                auth_config["provider"] = provider
            if login_hint:
                auth_config["login_hint"] = login_hint
                
            # Pass the config dictionary to url_for_oauth2
            auth_url = nylas.auth.url_for_oauth2(config=auth_config)
            
            logger.info(f"Generated Nylas auth URL for provider {provider}")
            
            # Return the URL as JSON (Juli Brain will handle the redirect)
            return jsonify({"url": auth_url})
            
        except Exception as e:
            logger.error(f"Error generating Nylas auth URL: {e}", exc_info=True)
            return jsonify({
                "error": f"Failed to generate auth URL: {str(e)}"
            }), 500
    
    @app.route("/api/nylas-calendar/callback", methods=["GET"])
    def nylas_calendar_callback():
        """
        OAuth callback endpoint to exchange authorization code for grant_id.
        This matches the production callback URL: https://juli-ai.com/api/nylas-calendar/callback
        """
        try:
            nylas_client_id = os.getenv("NYLAS_CLIENT_ID")
            nylas_api_key = os.getenv("NYLAS_API_KEY")  # This is actually the client secret
            
            if not nylas_client_id or not nylas_api_key:
                logger.error("Missing NYLAS_CLIENT_ID or NYLAS_API_KEY for callback")
                return jsonify({
                    "error": "Server not configured for OAuth callback"
                }), 500
            
            # Get the authorization code from query params
            code = request.args.get("code")
            if not code:
                error = request.args.get("error")
                error_description = request.args.get("error_description")
                logger.error(f"OAuth callback error: {error} - {error_description}")
                return jsonify({
                    "error": error_description or error or "Authorization failed"
                }), 400
            
            # Get the callback URL that was used
            callback_url = os.getenv("NYLAS_CALLBACK_URI", f"{get_base_url()}/api/nylas-calendar/callback")
            
            # Import Nylas client and models
            from nylas import Client as NylasClient
            from nylas.models.auth import CodeExchangeRequest
            
            # Create Nylas client with the API key
            nylas = NylasClient(
                api_key=nylas_api_key,
                api_uri=os.getenv("NYLAS_API_URI", "https://api.us.nylas.com")
            )
            
            # Exchange the code for an access token and grant_id
            # In Nylas V3, the API key is used instead of client secret
            try:
                logger.info(f"Attempting code exchange with client_id: {nylas_client_id}")
                logger.info(f"Using callback URL: {callback_url}")
                logger.info(f"API key starts with: {nylas_api_key[:10] if nylas_api_key else 'None'}")
                
                # Create the exchange request object
                # Explicitly pass the API key as client_secret for V3
                exchange_request = CodeExchangeRequest(
                    code=code,
                    client_id=nylas_client_id,
                    client_secret=nylas_api_key,  # V3 uses API key as client secret
                    redirect_uri=callback_url
                )
                response = nylas.auth.exchange_code_for_token(exchange_request)
                
                # Extract grant_id and email from response
                # The response is a CodeExchangeResponse object with attributes
                logger.info(f"Token exchange successful!")
                
                # Access the attributes directly from the response object
                grant_id = response.grant_id
                email = response.email
                provider = response.provider if hasattr(response, 'provider') else None
                
                if not grant_id:
                    logger.error(f"No grant_id in token response")
                    return jsonify({
                        "error": "Failed to obtain grant_id from Nylas"
                    }), 500
                
                logger.info(f"Successfully obtained grant_id: {grant_id} for email: {email}")
                
                # Return the grant_id and email for Juli Brain to store
                # The email is the calendar account email which can be used for validation
                return jsonify({
                    "success": True,
                    "grant_id": grant_id,
                    "email": email,
                    "calendar_email": email,  # Explicitly mark this as the calendar email
                    "message": "Calendar connected successfully!",
                    "next_step": "Connect Reclaim.ai using the SAME calendar account"
                })
                
            except Exception as token_error:
                logger.error(f"Token exchange failed: {token_error}", exc_info=True)
                return jsonify({
                    "error": f"Failed to exchange code: {str(token_error)}"
                }), 500
                
        except Exception as e:
            logger.error(f"OAuth callback error: {e}", exc_info=True)
            return jsonify({
                "error": f"Callback processing failed: {str(e)}"
            }), 500
    
    @app.route("/setup/validate-complete", methods=["POST"])
    def setup_validate_complete():
        """Validate both Reclaim and Nylas are connected to the same calendar."""
        try:
            from src.setup.setup_manager import SetupManager
            
            data = request.get_json()
            credentials = {
                "reclaim_api_key": data.get("reclaim_api_key"),
                "nylas_api_key": data.get("nylas_api_key"),
                "nylas_grant_id": data.get("nylas_grant_id")
            }
            
            # Use SetupManager for comprehensive validation
            setup_manager = SetupManager()
            result = setup_manager.validate_complete_setup(credentials)
            
            # Return appropriate status code based on validation result
            if result.get("validation_error"):
                if result.get("calendar_mismatch"):
                    return jsonify(result), 409  # Conflict
                else:
                    return jsonify(result), 400  # Bad Request
            
            return jsonify(result), 200
            
        except Exception as e:
            logger.error(f"Complete validation error: {e}", exc_info=True)
            return jsonify({
                "validation_error": True,
                "error": f"Validation failed: {str(e)}"
            }), 500
    
    @app.route("/setup/validate-reclaim", methods=["POST"])
    def setup_validate_reclaim():
        """Validate Reclaim.ai API key in real-time."""
        try:
            data = request.get_json()
            if not data or not data.get("reclaim_api_key"):
                return jsonify({
                    "valid": False,
                    "error": "Missing reclaim_api_key in request"
                }), 400
            
            api_key = data["reclaim_api_key"]
            
            # Basic format validation
            if not api_key or len(api_key) < 10:
                return jsonify({
                    "valid": False,
                    "error": "Invalid key format. Reclaim API key appears to be too short."
                }), 400
            
            # Test the API key by making a simple API call
            from reclaim_sdk.client import ReclaimClient
            
            try:
                client = ReclaimClient.configure(token=api_key)
                # Try to get current user info as a validation test
                user_info = client.get("/api/users/current")
                
                # Get the calendar email - Reclaim uses 'email' field as primary
                calendar_email = (
                    user_info.get("calendar_email") or  # Try this first if it exists
                    user_info.get("email") or  # This is the primary field per research
                    user_info.get("primary_email")  # Fallback
                )
                
                # Check if user provided a Nylas email to validate against
                nylas_email = data.get("nylas_calendar_email")
                calendar_match = None
                
                if nylas_email and calendar_email:
                    calendar_match = calendar_email.lower() == nylas_email.lower()
                    if not calendar_match:
                        logger.warning(f"Calendar mismatch: Reclaim={calendar_email}, Nylas={nylas_email}")
                
                response_data = {
                    "valid": True,
                    "user_email": user_info.get("email"),
                    "calendar_email": calendar_email,
                    "message": "Successfully connected to Reclaim.ai!"
                }
                
                # Add calendar matching info if we have Nylas email to compare
                if nylas_email:
                    response_data["calendar_match"] = calendar_match
                    if not calendar_match:
                        response_data["warning"] = f"⚠️ Calendar mismatch! Reclaim is using {calendar_email} but Nylas is using {nylas_email}"
                        response_data["fix"] = "Both services must use the same calendar account"
                
                return jsonify(response_data)
                
            except Exception as api_error:
                logger.error(f"Reclaim API validation failed: {api_error}")
                return jsonify({
                    "valid": False,
                    "error": "Could not connect to Reclaim.ai. Please check your API key."
                }), 400
                
        except Exception as e:
            logger.error(f"Reclaim validation error: {e}", exc_info=True)
            return jsonify({
                "valid": False,
                "error": f"Validation failed: {str(e)}"
            }), 500
    
    return app




if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5002)