"""Minimal HTTP request/response logger for E2E tests."""
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime


class HTTPLogger:
    """Logs HTTP requests and responses to a file."""
    
    def __init__(self, log_file: str = "e2e_http.log", enabled: bool = True):
        """Initialize the logger."""
        self.log_file = log_file
        self.enabled = enabled and os.getenv("E2E_LOGGING_ENABLED", "false").lower() == "true"
        
        # Create log file if it doesn't exist
        if self.enabled:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_file)), exist_ok=True)
            
            # Write session header with timestamp
            with open(self.log_file, "w") as f:
                f.write(f"=== E2E TEST SESSION STARTED: {datetime.now().isoformat()} ===\n\n")
    
    def log_request(self, method: str, url: str, headers: Dict[str, str], body: Optional[Dict[str, Any]] = None):
        """Log an HTTP request."""
        if not self.enabled:
            return
        
        # Print to console
        print(f"\n🔵 HTTP REQUEST:")
        print(f"  {method} {url}")
        
        # Mask sensitive headers
        masked_headers = self._mask_credentials(headers)
        print(f"  Headers: {json.dumps(masked_headers, indent=4)}")
        
        if body:
            print(f"  Body: {json.dumps(body, indent=4)}")
        
        # Also log to file
        with open(self.log_file, "a") as f:
            f.write("=== REQUEST ===\n")
            f.write(f"{method} {url}\n")
            f.write(f"Headers: {json.dumps(masked_headers, indent=2)}\n")
            
            if body:
                f.write(f"Body: {json.dumps(body, indent=2)}\n")
            
            f.write("\n")
    
    def log_response(self, status_code: int, body: Dict[str, Any]):
        """Log an HTTP response."""
        if not self.enabled:
            return
        
        # Print to console
        print(f"\n🟢 HTTP RESPONSE:")
        print(f"  Status: {status_code}")
        print(f"  Body: {json.dumps(body, indent=4)}")
        
        # Also log to file
        with open(self.log_file, "a") as f:
            f.write("=== RESPONSE ===\n")
            f.write(f"Status: {status_code}\n")
            f.write(f"Body: {json.dumps(body, indent=2)}\n")
            f.write("\n")
    
    def _mask_credentials(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Mask sensitive credential headers."""
        masked = headers.copy()
        credential_keys = [
            "X-User-Credential-RECLAIM-API-KEY",
            "X-User-Credential-NYLAS-API-KEY", 
            "X-User-Credential-NYLAS-GRANT-ID",
            "x-user-credential-reclaim-api-key",
            "x-user-credential-nylas-api-key",
            "x-user-credential-nylas-grant-id"
        ]
        
        for key in credential_keys:
            if key in masked:
                masked[key] = "***"
        
        return masked