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
    
    @app.route("/auth/connect", methods=["GET"])
    def auth_connect():
        """
        Return Nylas Hosted Auth URL as JSON per A2A spec.
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
                
                # Redirect to Juli Brain with error status
                juli_brain_callback = os.getenv("JULI_BRAIN_CALLBACK_URI")
                if juli_brain_callback:
                    from urllib.parse import urlencode
                    from flask import redirect
                    params = {
                        'status': 'error',
                        'error': error_description or error or "Authorization failed",
                        'agent_id': 'juli-calendar',
                        'credential_key': 'NYLAS_GRANT_ID'
                    }
                    redirect_url = f"{juli_brain_callback}?{urlencode(params)}"
                    return redirect(redirect_url)
                
                # Fallback if JULI_BRAIN_CALLBACK_URI not set
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
                # Log only a hash of the client_id for debugging
                client_id_hash = hashlib.sha256(nylas_client_id.encode()).hexdigest()[:8] if nylas_client_id else "None"
                logger.info(f"Attempting code exchange with client_id hash: {client_id_hash}")
                logger.info(f"Using callback URL: {callback_url}")
                # Do not log any part of the API key
                
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
                
                # Redirect to Juli Brain callback with grant information
                # This follows the A2A three-step OAuth callback chain
                from urllib.parse import urlencode
                from flask import redirect
                
                juli_brain_callback = os.getenv("JULI_BRAIN_CALLBACK_URI")
                if not juli_brain_callback:
                    logger.error("JULI_BRAIN_CALLBACK_URI not configured")
                    return jsonify({"error": "Server misconfigured - missing JULI_BRAIN_CALLBACK_URI"}), 500
                
                # Build redirect URL with grant information
                params = {
                    'grant_id': grant_id,
                    'credential_key': 'NYLAS_GRANT_ID',  # Match the key in manifest
                    'agent_id': 'juli-calendar',  # Our agent ID, not inbox-mcp
                    'email': email,
                    'status': 'success'
                }
                redirect_url = f"{juli_brain_callback}?{urlencode(params)}"
                logger.info(f"Redirecting to Juli Brain: {redirect_url}")
                return redirect(redirect_url)
                
            except Exception as token_error:
                logger.error(f"Token exchange failed: {token_error}", exc_info=True)
                
                # Even on error, redirect to Juli Brain with error status
                juli_brain_callback = os.getenv("JULI_BRAIN_CALLBACK_URI")
                if juli_brain_callback:
                    from urllib.parse import urlencode
                    from flask import redirect
                    params = {
                        'status': 'error',
                        'error': f"Failed to exchange code: {str(token_error)}",
                        'agent_id': 'juli-calendar',
                        'credential_key': 'NYLAS_GRANT_ID'
                    }
                    redirect_url = f"{juli_brain_callback}?{urlencode(params)}"
                    return redirect(redirect_url)
                
                # Fallback if JULI_BRAIN_CALLBACK_URI not set
                return jsonify({
                    "error": f"Failed to exchange code: {str(token_error)}"
                }), 500
                
        except Exception as e:
            logger.error(f"OAuth callback error: {e}", exc_info=True)
            
            # Even on error, redirect to Juli Brain with error status
            juli_brain_callback = os.getenv("JULI_BRAIN_CALLBACK_URI")
            if juli_brain_callback:
                from urllib.parse import urlencode
                from flask import redirect
                params = {
                    'status': 'error',
                    'error': f"Callback processing failed: {str(e)}",
                    'agent_id': 'juli-calendar',
                    'credential_key': 'NYLAS_GRANT_ID'
                }
                redirect_url = f"{juli_brain_callback}?{urlencode(params)}"
                return redirect(redirect_url)
            
            # Fallback if JULI_BRAIN_CALLBACK_URI not set
            return jsonify({
                "error": f"Callback processing failed: {str(e)}"
            }), 500
    
    # Note: /setup/* endpoints have been removed per A2A spec
    # Only manifest-declared endpoints are allowed
    # Validation is now handled by /validate/{credential_key} endpoints
    
    @app.route("/validate/NYLAS_GRANT_ID", methods=["POST"])
    def validate_nylas_grant():
        """
        Validate Nylas grant ID per A2A spec.
        Called by Juli Brain, NOT by frontend.
        Agent does NOT store credentials - only validates them.
        """
        data = request.get_json()
        credential_value = data.get("credential_value")
        
        if not credential_value:
            return jsonify({"valid": False, "error": "Missing credential_value"}), 400
        
        try:
            # Test the grant with Nylas
            from nylas import Client as NylasClient
            
            nylas = NylasClient(
                api_key=os.getenv("NYLAS_API_KEY"),
                api_uri=os.getenv("NYLAS_API_URI", "https://api.us.nylas.com")
            )
            
            # Try to get grant information
            grant = nylas.grants.find(grant_id=credential_value)
            
            return jsonify({
                "valid": True,
                "metadata": {
                    "email": grant.email if hasattr(grant, 'email') else None,
                    "provider": grant.provider if hasattr(grant, 'provider') else None
                }
            })
        except Exception as e:
            logger.error(f"Nylas grant validation failed: {e}")
            return jsonify({
                "valid": False,
                "error": str(e)
            })
    
    @app.route("/validate/RECLAIM_API_KEY", methods=["POST"])
    def validate_reclaim_key():
        """
        Validate Reclaim API key per A2A spec.
        Agent does NOT store anything, only validates.
        """
        data = request.get_json()
        credential_value = data.get("credential_value")
        
        if not credential_value:
            return jsonify({"valid": False, "error": "Missing credential_value"}), 400
        
        try:
            # Import Reclaim SDK for validation
            from reclaim_sdk.client import ReclaimClient
            
            # Test API key with Reclaim
            client = ReclaimClient.configure(token=credential_value)
            user_info = client.get("/api/users/current")
            
            # Get the calendar email from Reclaim
            calendar_email = (
                user_info.get("calendar_email") or
                user_info.get("email") or
                user_info.get("primary_email")
            )
            
            return jsonify({
                "valid": True,
                "metadata": {
                    "email": calendar_email,
                    "user_id": user_info.get("id")
                }
            })
        except Exception as e:
            logger.error(f"Reclaim API key validation failed: {e}")
            return jsonify({
                "valid": False,
                "error": str(e)
            })
    
    return app




if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5002)