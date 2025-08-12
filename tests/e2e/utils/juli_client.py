"""Juli client simulator for E2E tests."""
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime
import pytz
import time
import os

from .http_logger import HTTPLogger


class JuliClient:
    """Simulates how Juli Brain would call the A2A agent."""
    
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
            base_url: Base URL of the A2A agent
            credentials: Dict with reclaim_api_key, nylas_api_key, nylas_grant_id
            logger: Optional HTTP logger
            timer: Optional TestTimer for tracking operation timings
        """
        self.base_url = base_url.rstrip('/')
        self.credentials = credentials
        self.logger = logger or HTTPLogger()
        self.timer = timer
        self._request_counter = 0  # For generating request IDs
    
    def execute_tool(
        self, 
        tool_name: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        Execute a tool via A2A JSON-RPC, mimicking how Juli Brain would call it.
        
        Args:
            tool_name: Name of the tool to execute
            params: Tool parameters
            context: Optional context with timezone, current_date, current_time
            
        Returns:
            HTTP response object with the RPC result
        """
        # Start timing if timer available
        if self.timer:
            self.timer.start(f"execute_tool_{tool_name}")
        
        # Build user context for A2A
        user_context = {}
        if context:
            user_context['timezone'] = context.get('timezone', 'UTC')
            user_context['current_date'] = context.get('current_date', datetime.now().strftime('%Y-%m-%d'))
            user_context['current_time'] = context.get('current_time', datetime.now().strftime('%H:%M:%S'))
        else:
            # Default context
            now = datetime.now(pytz.timezone('UTC'))
            user_context['timezone'] = 'UTC'
            user_context['current_date'] = now.strftime('%Y-%m-%d')
            user_context['current_time'] = now.strftime('%H:%M:%S')
        
        # Add credentials to user context
        user_context['credentials'] = {
            'RECLAIM_API_KEY': self.credentials.get('reclaim_api_key', ''),
            'NYLAS_GRANT_ID': self.credentials.get('nylas_grant_id', '')
        }
        
        # Build JSON-RPC request
        self._request_counter += 1
        rpc_request = {
            "jsonrpc": "2.0",
            "id": self._request_counter,
            "method": "tool.execute",
            "params": {
                "tool": tool_name,
                "arguments": params,
                "user_context": user_context,
                "request_id": f"test-{self._request_counter}"
            }
        }
        
        # Build headers (use dev secret for testing)
        headers = {
            'Content-Type': 'application/json',
            'X-A2A-Dev-Secret': os.getenv('A2A_DEV_SECRET', 'test-secret')
        }
        
        print(f"[DEBUG] A2A RPC request for tool: {tool_name}")
        print(f"[DEBUG] Has credentials: reclaim={bool(user_context['credentials'].get('RECLAIM_API_KEY'))}, grant={bool(user_context['credentials'].get('NYLAS_GRANT_ID'))}")
        
        # Build URL
        url = f"{self.base_url}/a2a/rpc"
        
        # Log request
        self.logger.log_request("POST", url, headers, rpc_request)
        
        # Time the HTTP request
        if self.timer:
            self.timer.start(f"http_request_{tool_name}")
        
        # Make request
        response = requests.post(url, json=rpc_request, headers=headers)
        
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
        
        # For backward compatibility with tests, extract the result from RPC response
        if response.status_code == 200 and 'result' in response_body:
            # Create a mock response object with just the result data
            class MockResponse:
                def __init__(self, data, status_code=200):
                    self._data = data
                    self.status_code = status_code
                    
                def json(self):
                    return self._data
            
            return MockResponse(response_body['result'])
        
        return response
    
    def check_needs_setup(self) -> requests.Response:
        """Check if setup is needed via A2A agent card."""
        url = f"{self.base_url}/.well-known/a2a.json"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        self.logger.log_request("GET", url, headers)
        response = requests.get(url, headers=headers)
        
        try:
            response_body = response.json()
        except:
            response_body = {"error": "Could not parse response body"}
        
        self.logger.log_response(response.status_code, response_body)
        
        # For backward compatibility, check if credentials are required
        if response.status_code == 200 and 'requires_credentials' in response_body:
            # Create a mock response that matches expected behavior
            class MockResponse:
                def __init__(self, needs_setup):
                    self.status_code = 200
                    self._data = {"needs_setup": needs_setup}
                    
                def json(self):
                    return self._data
            
            return MockResponse(response_body['requires_credentials'])
        
        return response
    
    def list_tools(self) -> requests.Response:
        """List available tools via A2A JSON-RPC."""
        # Build JSON-RPC request
        self._request_counter += 1
        rpc_request = {
            "jsonrpc": "2.0",
            "id": self._request_counter,
            "method": "tool.list",
            "params": {}
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-A2A-Dev-Secret': os.getenv('A2A_DEV_SECRET', 'test-secret')
        }
        
        url = f"{self.base_url}/a2a/rpc"
        
        self.logger.log_request("POST", url, headers, rpc_request)
        response = requests.post(url, json=rpc_request, headers=headers)
        
        try:
            response_body = response.json()
        except:
            response_body = {"error": "Could not parse response body"}
        
        self.logger.log_response(response.status_code, response_body)
        
        # For backward compatibility, extract tools from RPC result
        if response.status_code == 200 and 'result' in response_body:
            class MockResponse:
                def __init__(self, tools):
                    self.status_code = 200
                    self._data = {"tools": tools}
                    
                def json(self):
                    return self._data
            
            return MockResponse(response_body['result'].get('tools', []))
        
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