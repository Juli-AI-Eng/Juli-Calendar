"""Tests for core server endpoints - A2A protocol."""
import json
import pytest


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check_returns_200(self, client):
        """Health check should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        
    def test_health_check_returns_json(self, client):
        """Health check should return JSON with status."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert "version" in data


class TestA2ADiscovery:
    """Tests for A2A discovery endpoints."""
    
    def test_agent_card_endpoint(self, client):
        """Agent card should be available at well-known URL."""
        response = client.get("/.well-known/a2a.json")
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data["agent_id"] == "juli-calendar"
        assert data["agent_name"] == "Juli Calendar Agent"
        assert "capabilities" in data
        assert "rpc" in data
        assert data["rpc"]["endpoint"] == "/a2a/rpc"
    
    def test_credentials_manifest(self, client):
        """Credentials manifest should list required credentials."""
        response = client.get("/.well-known/a2a-credentials.json")
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert "credentials" in data
        assert len(data["credentials"]) > 0


class TestA2ARPC:
    """Tests for A2A JSON-RPC endpoint."""
    
    def test_rpc_requires_authentication(self, client):
        """RPC endpoint should require authentication."""
        response = client.post("/a2a/rpc", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "agent.handshake",
            "params": {}
        })
        assert response.status_code == 401
    
    def test_rpc_handshake_with_dev_secret(self, client):
        """RPC handshake should work with dev secret."""
        import os
        os.environ["A2A_DEV_SECRET"] = "test-secret"
        
        response = client.post("/a2a/rpc", 
            headers={"X-A2A-Dev-Secret": "test-secret"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "agent.handshake",
                "params": {}
            }
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert "result" in data
        assert data["result"]["agent"] == "juli-calendar"
    
    def test_rpc_invalid_method(self, client):
        """RPC should return error for invalid method."""
        import os
        os.environ["A2A_DEV_SECRET"] = "test-secret"
        
        response = client.post("/a2a/rpc",
            headers={"X-A2A-Dev-Secret": "test-secret"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "invalid.method",
                "params": {}
            }
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert "error" in data
        assert data["error"]["code"] == -32601