#!/usr/bin/env python3
"""Test the improved conflict resolution."""
import asyncio
import os
from dotenv import load_dotenv
from tests.e2e.utils.juli_client import JuliClient, create_test_context

# Load test environment
load_dotenv('.env.test')

async def test_conflict_resolution():
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
    
    # First, create a meeting at 10 AM tomorrow
    print("\n1. Creating Team Standup at 10 AM tomorrow...")
    response1 = client.execute_tool(
        "manage_productivity",
        {
            "query": "Schedule team standup tomorrow at 10am",
            "context": "Test conflict resolution"
        },
        context
    )
    
    data1 = response1.json()
    print(f"Response: needs_approval={data1.get('needs_approval')}, action={data1.get('action_type')}")
    
    if data1.get("needs_approval"):
        # Approve it
        response1b = client.execute_tool(
            "manage_productivity",
            {
                "approved": True,
                "action_data": data1["action_data"]
            },
            context
        )
        data1b = response1b.json()
        print(f"Created: {data1b.get('data', {}).get('title')} at 10 AM")
    
    # Now try to create Deep Work "tomorrow morning" - should suggest alternative
    print("\n2. Trying to schedule 2 hours tomorrow morning for deep work...")
    response2 = client.execute_tool(
        "manage_productivity",
        {
            "query": "Schedule 2 hours tomorrow morning for deep work session",
            "context": "Test conflict resolution"
        },
        context
    )
    
    data2 = response2.json()
    print(f"\nResponse: needs_approval={data2.get('needs_approval')}, action={data2.get('action_type')}")
    
    if data2.get("needs_approval") and data2.get("action_type") == "event_create_conflict_reschedule":
        print("\n✅ CONFLICT DETECTED AND ALTERNATIVE SUGGESTED!")
        preview = data2.get("preview", {})
        details = preview.get("details", {})
        print(f"Summary: {preview.get('summary')}")
        print(f"Message: {details.get('message')}")
        
        # Show the suggested alternative
        if details.get("suggested_alternative"):
            alt = details["suggested_alternative"]
            print(f"\nSuggested time: {alt.get('start')}")
            print(f"Duration: {alt.get('duration')}")
    else:
        print(f"\n❌ Expected conflict resolution but got: {data2}")

if __name__ == "__main__":
    asyncio.run(test_conflict_resolution())