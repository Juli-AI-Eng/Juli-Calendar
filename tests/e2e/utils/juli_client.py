"""Juli client simulator for E2E tests."""
import requests
from typing import Dict, Any, Optional
from datetime import datetime
import pytz
import time

from .http_logger import HTTPLogger


class JuliClient:
    """Simulates how Juli would call the MCP server."""
    
    def __init__(
        self, 
        base_url: str, 
        credentials: Dict[str, str],
        logger: Optional[HTTPLogger] = None,
        timer: Optional['TestTimer'] = None
    ):
        """
        Initialize the Juli client.
        
        Args:
            base_url: Base URL of the MCP server
            credentials: Dict with reclaim_api_key, nylas_api_key, nylas_grant_id
            logger: Optional HTTP logger
            timer: Optional TestTimer for tracking operation timings
        """
        self.base_url = base_url.rstrip('/')
        self.credentials = credentials
        self.logger = logger or HTTPLogger()
        self.timer = timer
    
    def execute_tool(
        self, 
        tool_name: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        Execute a tool, mimicking how Juli would call it.
        
        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters
            context: Optional context with timezone, current_date, current_time
            
        Returns:
            HTTP response object
        """
        # Start timing if timer available
        if self.timer:
            self.timer.start(f"execute_tool_{tool_name}")
        
        # Add context injection
        if context:
            params['user_timezone'] = context.get('timezone', 'UTC')
            params['current_date'] = context.get('current_date', datetime.now().strftime('%Y-%m-%d'))
            params['current_time'] = context.get('current_time', datetime.now().strftime('%H:%M:%S'))
        else:
            # Default context
            now = datetime.now(pytz.timezone('UTC'))
            params['user_timezone'] = 'UTC'
            params['current_date'] = now.strftime('%Y-%m-%d')
            params['current_time'] = now.strftime('%H:%M:%S')
        
        # Build headers with credential injection using Juli format
        reclaim_key = self.credentials.get('reclaim_api_key', '')
        nylas_key = self.credentials.get('nylas_api_key', '')
        nylas_grant = self.credentials.get('nylas_grant_id', '')
        
        print(f"[DEBUG] JuliClient credentials: reclaim={bool(reclaim_key)}, nylas={bool(nylas_key)}, grant={bool(nylas_grant)}")
        print(f"[DEBUG] Reclaim key value: {reclaim_key[:10]}..." if reclaim_key else "[DEBUG] No Reclaim key!")
        
        headers = {
            'Content-Type': 'application/json',
            'X-User-Credential-RECLAIM-API-KEY': reclaim_key,
            'X-User-Credential-NYLAS-API-KEY': nylas_key,
            'X-User-Credential-NYLAS-GRANT-ID': nylas_grant
        }
        
        print(f"[DEBUG] Headers being sent: {list(headers.keys())}")
        
        # Build URL
        url = f"{self.base_url}/mcp/tools/{tool_name}"
        
        # Log request
        self.logger.log_request("POST", url, headers, params)
        
        # Time the HTTP request
        if self.timer:
            self.timer.start(f"http_request_{tool_name}")
        
        # Make request
        response = requests.post(url, json=params, headers=headers)
        
        # End HTTP timing
        if self.timer:
            self.timer.end(f"http_request_{tool_name}")
        
        # Log response
        try:
            response_body = response.json()
        except:
            response_body = {"error": "Could not parse response body"}
        
        self.logger.log_response(response.status_code, response_body)
        
        # End tool timing
        if self.timer:
            self.timer.end(f"execute_tool_{tool_name}")
        
        return response
    
    def check_needs_setup(self) -> requests.Response:
        """Check if setup is needed."""
        url = f"{self.base_url}/mcp/needs-setup"
        
        headers = {
            'X-User-Credential-RECLAIM-API-KEY': self.credentials.get('reclaim_api_key', ''),
            'X-User-Credential-NYLAS-API-KEY': self.credentials.get('nylas_api_key', ''),
            'X-User-Credential-NYLAS-GRANT-ID': self.credentials.get('nylas_grant_id', '')
        }
        
        self.logger.log_request("GET", url, headers)
        response = requests.get(url, headers=headers)
        
        try:
            response_body = response.json()
        except:
            response_body = {"error": "Could not parse response body"}
        
        self.logger.log_response(response.status_code, response_body)
        
        return response
    
    def list_tools(self) -> requests.Response:
        """List available tools."""
        url = f"{self.base_url}/mcp/tools"
        
        headers = {
            'X-User-Credential-RECLAIM-API-KEY': self.credentials.get('reclaim_api_key', ''),
            'X-User-Credential-NYLAS-API-KEY': self.credentials.get('nylas_api_key', ''),
            'X-User-Credential-NYLAS-GRANT-ID': self.credentials.get('nylas_grant_id', '')
        }
        
        self.logger.log_request("GET", url, headers)
        response = requests.get(url, headers=headers)
        
        try:
            response_body = response.json()
        except:
            response_body = {"error": "Could not parse response body"}
        
        self.logger.log_response(response.status_code, response_body)
        
        return response


def create_test_context(timezone: str = "America/New_York") -> Dict[str, Any]:
    """Create a test context with current date/time in specified timezone."""
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    
    return {
        "timezone": timezone,
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S")
    }