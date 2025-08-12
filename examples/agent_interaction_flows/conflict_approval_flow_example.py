#!/usr/bin/env python3
"""Test the conflict reschedule approval flow fix."""
import asyncio
import os
from dotenv import load_dotenv
from tests.e2e.utils.juli_client import JuliClient, create_test_context

# Load test environment
load_dotenv('.env.test')

async def test_conflict_approval():
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
    
    # Step 1: Create a meeting at 9 AM tomorrow
    print("\n1. Creating first event at 9 AM tomorrow...")
    response1 = client.execute_tool(
        "manage_productivity",
        {
            "query": "Schedule team meeting tomorrow at 9am",
            "context": "Test conflict approval"
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
        print(f"Created: {data1b.get('data', {}).get('title')} at 9 AM")
    
    # Step 2: Try to create another event at 9 AM - should suggest alternative
    print("\n2. Trying to schedule another event at 9 AM (conflict expected)...")
    response2 = client.execute_tool(
        "manage_productivity",
        {
            "query": "Schedule project review tomorrow at 9am",
            "context": "Test conflict approval"
        },
        context
    )
    
    data2 = response2.json()
    print(f"\nConflict Response: needs_approval={data2.get('needs_approval')}, action={data2.get('action_type')}")
    
    if data2.get("needs_approval") and data2.get("action_type") == "event_create_conflict_reschedule":
        print("\n✅ CONFLICT DETECTED!")
        preview = data2.get("preview", {})
        details = preview.get("details", {})
        print(f"Message: {details.get('message')}")
        print(f"Suggested time: {details.get('suggested_alternative', {}).get('start')}")
        
        # Step 3: APPROVE the conflict reschedule
        print("\n3. Approving the suggested alternative time...")
        response3 = client.execute_tool(
            "manage_productivity",
            {
                "approved": True,
                "action_data": data2["action_data"],
                "action_type": data2["action_type"]  # Include action_type
            },
            context
        )
        
        data3 = response3.json()
        print(f"\nApproval Response Status: {response3.status_code}")
        print(f"Response type: needs_approval={data3.get('needs_approval')}, success={data3.get('success')}")
        
        if data3.get("success"):
            print("\n✅ SUCCESS! Event created at alternative time")
            print(f"Event ID: {data3.get('data', {}).get('id')}")
            print(f"Event Title: {data3.get('data', {}).get('title')}")
            print(f"Event Time: {data3.get('data', {}).get('when')}")
        else:
            print(f"\n❌ FAILED! Response: {data3}")
    else:
        print(f"\n❌ Expected conflict resolution but got: {data2}")

if __name__ == "__main__":
    asyncio.run(test_conflict_approval())