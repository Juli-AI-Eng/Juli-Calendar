#!/usr/bin/env python3
"""
Nylas OAuth Flow Example

This script demonstrates how to initiate the Nylas OAuth flow for connecting
a calendar to the Juli Calendar Agent.

Usage:
    1. Ensure the server is running: python scripts/run_server.py
    2. Run this script: python examples/nylas_oauth_simple.py
    3. Complete the OAuth flow in your browser
    4. Save the returned grant_id for use in API calls

The OAuth flow:
    1. Request OAuth URL from the agent
    2. User authenticates with their calendar provider (Google/Microsoft/iCloud)
    3. Provider redirects back to the agent with an authorization code
    4. Agent exchanges the code for a grant_id
    5. Grant_id is used for all subsequent calendar operations
"""

import requests
import webbrowser
import sys

server_url = "http://localhost:5002"

# Check server
try:
    response = requests.get(f"{server_url}/health")
    if response.status_code != 200:
        print(f"❌ Server not healthy: {response.status_code}")
        sys.exit(1)
except:
    print("❌ Server not running on port 5002")
    print("Start it with: python3 scripts/run_server.py")
    sys.exit(1)

# Get OAuth URL WITHOUT specifying provider - let Nylas show provider selection
response = requests.get(f"{server_url}/setup/connect-url")
if response.status_code == 200:
    data = response.json()
    auth_url = data.get("url")
    if auth_url:
        print(f"Opening OAuth URL in browser...")
        webbrowser.open(auth_url)
        print("\n✅ Browser opened. Complete authentication there.")
        print("You'll be redirected to http://localhost:5002/api/nylas-calendar/callback")
        print("Save the grant_id from the callback response.")
    else:
        print(f"❌ No URL in response: {data}")
else:
    print(f"❌ Failed to get OAuth URL: {response.status_code}")
    print(response.text)