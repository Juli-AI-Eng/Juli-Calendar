"""E2E tests for A2A protocol implementation."""
import pytest
import requests
import json
import os
from datetime import datetime
from typing import Dict, Any

# Server URL for E2E tests
SERVER_URL = "http://localhost:5002"
A2A_DEV_SECRET = os.getenv("A2A_DEV_SECRET", "test-dev-secret")


class TestA2AProtocolE2E:
    """Test A2A protocol endpoints in E2E environment."""
    
    def test_a2a_discovery(self):
        """Test that A2A discovery endpoint returns valid agent card."""
        response = requests.get(f"{SERVER_URL}/.well-known/a2a.json")
        assert response.status_code == 200
        
        agent_card = response.json()
        assert agent_card["agent_id"] == "juli-calendar"
        assert agent_card["agent_name"] == "Juli Calendar Agent"
        assert agent_card["version"] == "2.0.0"
        
        # Check capabilities
        assert "capabilities" in agent_card
        tools = agent_card["capabilities"]["tools"]
        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]
        assert "manage_productivity" in tool_names
        assert "check_availability" in tool_names
        assert "find_and_analyze" in tool_names
        
        # Check auth schemes
        assert "auth" in agent_card
        schemes = agent_card["auth"]["schemes"]
        assert any(s["type"] == "oidc" for s in schemes)
        assert any(s["type"] == "dev_secret" for s in schemes)
        
        # Check RPC endpoint
        assert agent_card["rpc"]["endpoint"] == "/a2a/rpc"
        assert agent_card["rpc"]["version"] == "2.0"
    
    def test_a2a_credentials_manifest(self):
        """Test that credentials manifest endpoint returns expected credentials."""
        response = requests.get(f"{SERVER_URL}/.well-known/a2a-credentials.json")
        assert response.status_code == 200
        
        manifest = response.json()
        assert "credentials" in manifest
        
        # Check for required credentials
        creds = manifest["credentials"]
        cred_keys = [c["key"] for c in creds]
        assert "RECLAIM_API_KEY" in cred_keys
        assert "NYLAS_GRANT_ID" in cred_keys
    
    def test_a2a_authentication_required(self):
        """Test that A2A RPC endpoint requires authentication."""
        # Try without authentication
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "agent.handshake",
                "params": {}
            }
        )
        assert response.status_code == 401
        
        result = response.json()
        assert result["error"]["code"] == -32000
        assert "Unauthorized" in result["error"]["message"]
    
    def test_a2a_handshake(self):
        """Test successful A2A handshake with dev secret."""
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers={"X-A2A-Dev-Secret": A2A_DEV_SECRET},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "agent.handshake",
                "params": {}
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert "result" in result
        assert result["result"]["agent"] == "juli-calendar"
        assert "card" in result["result"]
        assert "server_time" in result["result"]
    
    def test_a2a_tool_list(self):
        """Test listing tools via A2A RPC."""
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers={"X-A2A-Dev-Secret": A2A_DEV_SECRET},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tool.list",
                "params": {}
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert "result" in result
        tools = result["result"]["tools"]
        assert len(tools) > 0
        
        tool_names = [t["name"] for t in tools]
        assert "manage_productivity" in tool_names
    
    def test_a2a_invalid_method(self):
        """Test that invalid JSON-RPC method returns proper error."""
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers={"X-A2A-Dev-Secret": A2A_DEV_SECRET},
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "invalid.method",
                "params": {}
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert "error" in result
        assert result["error"]["code"] == -32601
        assert "Method not found" in result["error"]["message"]
    
    def test_a2a_invalid_json_rpc_version(self):
        """Test that invalid JSON-RPC version returns error."""
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers={"X-A2A-Dev-Secret": A2A_DEV_SECRET},
            json={
                "jsonrpc": "1.0",  # Invalid version
                "id": 4,
                "method": "agent.handshake",
                "params": {}
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert "error" in result
        assert result["error"]["code"] == -32600
        assert "Invalid Request" in result["error"]["message"]
    
    def test_a2a_tool_execute_without_credentials(self):
        """Test that tool execution without credentials returns needs_setup."""
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers={"X-A2A-Dev-Secret": A2A_DEV_SECRET},
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tool.execute",
                "params": {
                    "tool": "find_and_analyze",
                    "arguments": {
                        "query": "show my tasks for today"
                    },
                    "user_context": {
                        "timezone": "America/Los_Angeles",
                        "current_date": datetime.now().strftime("%Y-%m-%d"),
                        "current_time": datetime.now().strftime("%H:%M:%S"),
                        "credentials": {}  # No credentials
                    }
                }
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert "result" in result
        assert result["result"]["needs_setup"] == True
        assert "message" in result["result"]
    
    @pytest.mark.skipif(
        not os.getenv("RECLAIM_API_KEY"),
        reason="Requires RECLAIM_API_KEY environment variable"
    )
    def test_a2a_tool_execute_with_credentials(self):
        """Test tool execution with valid credentials."""
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers={"X-A2A-Dev-Secret": A2A_DEV_SECRET},
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tool.execute",
                "params": {
                    "tool": "find_and_analyze",
                    "arguments": {
                        "query": "show my tasks for today"
                    },
                    "user_context": {
                        "timezone": "America/Los_Angeles",
                        "current_date": datetime.now().strftime("%Y-%m-%d"),
                        "current_time": datetime.now().strftime("%H:%M:%S"),
                        "credentials": {
                            "RECLAIM_API_KEY": os.getenv("RECLAIM_API_KEY")
                        }
                    },
                    "request_id": "test-req-123"
                }
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert "result" in result
        assert "success" in result["result"]
        
        # If it needs approval, check the structure
        if result["result"].get("needs_approval"):
            assert "action_type" in result["result"]
            assert "action_data" in result["result"]
            assert "preview" in result["result"]
            assert result["result"]["request_id"] == "test-req-123"
    
    def test_a2a_parse_error(self):
        """Test that invalid JSON returns parse error."""
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers={
                "X-A2A-Dev-Secret": A2A_DEV_SECRET,
                "Content-Type": "application/json"
            },
            data="not valid json"  # Invalid JSON
        )
        assert response.status_code == 400
        
        result = response.json()
        assert "error" in result
        assert result["error"]["code"] == -32700
        assert "Parse error" in result["error"]["message"]