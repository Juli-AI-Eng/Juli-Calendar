#!/usr/bin/env python3
"""Test script for A2A (Agent-to-Agent) implementation."""

import requests
import json
import sys
import os
from datetime import datetime

# Server URL - assume running locally on port 3002
SERVER_URL = "http://localhost:3002"

# Dev secret for authentication
A2A_DEV_SECRET = os.getenv("A2A_DEV_SECRET", "test-dev-secret")


def test_discovery():
    """Test the A2A discovery endpoint."""
    print("\n=== Testing A2A Discovery ===")
    
    try:
        response = requests.get(f"{SERVER_URL}/.well-known/a2a.json")
        response.raise_for_status()
        
        agent_card = response.json()
        print(f"✅ Agent Card retrieved successfully")
        print(f"   Agent ID: {agent_card.get('agent_id')}")
        print(f"   Agent Name: {agent_card.get('agent_name')}")
        print(f"   Version: {agent_card.get('version')}")
        print(f"   RPC Endpoint: {agent_card.get('rpc', {}).get('endpoint')}")
        
        # Check tools
        tools = agent_card.get('capabilities', {}).get('tools', [])
        print(f"   Available tools: {len(tools)}")
        for tool in tools:
            print(f"      - {tool['name']}: {tool['description']}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Discovery test failed: {e}")
        return False


def test_credentials_manifest():
    """Test the credentials manifest endpoint."""
    print("\n=== Testing Credentials Manifest ===")
    
    try:
        response = requests.get(f"{SERVER_URL}/.well-known/a2a-credentials.json")
        response.raise_for_status()
        
        manifest = response.json()
        print(f"✅ Credentials manifest retrieved successfully")
        
        credentials = manifest.get('credentials', [])
        print(f"   Required credentials: {len(credentials)}")
        for cred in credentials:
            print(f"      - {cred['key']}: {cred['display_name']}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Credentials manifest test failed: {e}")
        return False


def test_rpc_handshake():
    """Test the JSON-RPC handshake method."""
    print("\n=== Testing RPC Handshake ===")
    
    headers = {
        "Content-Type": "application/json",
        "X-A2A-Dev-Secret": A2A_DEV_SECRET
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "agent.handshake",
        "params": {}
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        
        if "error" in result:
            print(f"❌ RPC handshake returned error: {result['error']}")
            return False
        
        print(f"✅ RPC handshake successful")
        print(f"   Agent: {result.get('result', {}).get('agent')}")
        print(f"   Server time: {result.get('result', {}).get('server_time')}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ RPC handshake test failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return False


def test_rpc_tool_list():
    """Test listing available tools via JSON-RPC."""
    print("\n=== Testing RPC Tool List ===")
    
    headers = {
        "Content-Type": "application/json",
        "X-A2A-Dev-Secret": A2A_DEV_SECRET
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tool.list",
        "params": {}
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        
        if "error" in result:
            print(f"❌ Tool list returned error: {result['error']}")
            return False
        
        tools = result.get('result', {}).get('tools', [])
        print(f"✅ Tool list retrieved successfully")
        print(f"   Available tools: {len(tools)}")
        for tool in tools:
            print(f"      - {tool['name']}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Tool list test failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return False


def test_rpc_tool_execute():
    """Test executing a tool via JSON-RPC."""
    print("\n=== Testing RPC Tool Execute ===")
    
    headers = {
        "Content-Type": "application/json",
        "X-A2A-Dev-Secret": A2A_DEV_SECRET
    }
    
    # Test with find_and_analyze (doesn't create anything)
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tool.execute",
        "params": {
            "tool": "find_and_analyze",
            "arguments": {
                "query": "find tasks for today"
            },
            "user_context": {
                "timezone": "America/Los_Angeles",
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "current_time": datetime.now().strftime("%H:%M:%S"),
                "credentials": {
                    # Note: This will fail without real credentials, but tests the flow
                    "RECLAIM_API_KEY": os.getenv("RECLAIM_API_KEY", "test-key")
                }
            },
            "request_id": "test-request-123"
        }
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        
        if "error" in result:
            # Check if it's an authentication error (expected without real creds)
            error_msg = result['error'].get('message', '')
            if 'unauthorized' in error_msg.lower():
                print(f"⚠️  Tool execution requires authentication (expected without real credentials)")
                return True
            else:
                print(f"❌ Tool execution returned error: {result['error']}")
                return False
        
        # If we get a result, check it
        tool_result = result.get('result', {})
        
        if tool_result.get('needs_setup'):
            print(f"⚠️  Tool execution requires setup (expected without credentials)")
            print(f"   Message: {tool_result.get('message')}")
            return True
        
        print(f"✅ Tool execution successful")
        print(f"   Success: {tool_result.get('success', False)}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Tool execution test failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return False


def test_rpc_authentication():
    """Test that authentication is required."""
    print("\n=== Testing RPC Authentication ===")
    
    # Test without auth header
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "agent.handshake",
        "params": {}
    }
    
    try:
        response = requests.post(
            f"{SERVER_URL}/a2a/rpc",
            headers=headers,
            json=payload
        )
        
        # We expect a 401 error
        if response.status_code == 401:
            print(f"✅ Authentication correctly required")
            result = response.json()
            print(f"   Error: {result.get('error', {}).get('message')}")
            return True
        else:
            print(f"❌ Expected 401 but got {response.status_code}")
            return False
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Authentication test failed: {e}")
        return False


def main():
    """Run all A2A tests."""
    print("=" * 50)
    print("A2A Implementation Test Suite")
    print(f"Testing server at: {SERVER_URL}")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(f"{SERVER_URL}/health")
        response.raise_for_status()
        print(f"✅ Server is running at {SERVER_URL}")
    except:
        print(f"❌ Server is not running at {SERVER_URL}")
        print("   Please start the server with: python scripts/run_server.py --port 3002")
        sys.exit(1)
    
    # Run tests
    tests = [
        test_discovery,
        test_credentials_manifest,
        test_rpc_authentication,
        test_rpc_handshake,
        test_rpc_tool_list,
        test_rpc_tool_execute
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()