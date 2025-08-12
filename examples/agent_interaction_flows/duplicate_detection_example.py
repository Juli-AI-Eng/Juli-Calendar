#!/usr/bin/env python3
"""Test duplicate detection logic."""
import asyncio
import os
from dotenv import load_dotenv
from tests.e2e.utils.juli_client import JuliClient, create_test_context

# Load test environment
load_dotenv('.env.test')

async def test_duplicate_flow():
    # Create client
    client = JuliClient(
        "http://localhost:5002",
        {
            "reclaim_api_key": os.getenv("RECLAIM_API_KEY"),
            "nylas_api_key": os.getenv("NYLAS_API_KEY"),
            "nylas_grant_id": os.getenv("NYLAS_GRANT_ID")
        }
    )
    
    context = create_test_context("America/New_York")
    
    # First, create a Deep Work event
    print("\n1. Creating first Deep Work event...")
    response1 = client.execute_tool(
        "manage_productivity",
        {
            "query": "Block 2 hours tomorrow morning for deep work",
            "context": "Test duplicate detection"
        },
        context
    )
    
    data1 = response1.json()
    print(f"Response: {data1.get('needs_approval', False)}, {data1.get('action_type', '')}")
    
    if data1.get("needs_approval") and data1.get("action_type") == "event_create_duplicate":
        print("Already detected as duplicate! Approving...")
        # Approve the duplicate
        response1b = client.execute_tool(
            "manage_productivity",
            {
                "approved": True,
                "action_data": data1["action_data"],
                "action_type": data1["action_type"]
            },
            context
        )
        data1b = response1b.json()
        print(f"Approval response: success={data1b.get('success')}, action={data1b.get('action')}")
        if data1b.get('needs_approval'):
            print(f"ERROR: Still needs approval! action_type={data1b.get('action_type')}")
    
    # Now try to create it again
    print("\n2. Creating duplicate Deep Work event...")
    response2 = client.execute_tool(
        "manage_productivity",
        {
            "query": "Block 2 hours tomorrow morning for deep work",
            "context": "Test duplicate detection"
        },
        context
    )
    
    data2 = response2.json()
    print(f"Response: {data2.get('needs_approval', False)}, {data2.get('action_type', '')}")
    
    if data2.get("needs_approval") and data2.get("action_type") == "event_create_duplicate":
        print("Detected as duplicate (expected). Approving...")
        # Approve the duplicate
        response2b = client.execute_tool(
            "manage_productivity",
            {
                "approved": True,
                "action_data": data2["action_data"],
                "action_type": data2["action_type"]
            },
            context
        )
        data2b = response2b.json()
        print(f"Approval response: success={data2b.get('success')}, action={data2b.get('action')}")
        if data2b.get('needs_approval'):
            print(f"ERROR: Still needs approval! action_type={data2b.get('action_type')}")
            print(f"Full response: {data2b}")

if __name__ == "__main__":
    asyncio.run(test_duplicate_flow())