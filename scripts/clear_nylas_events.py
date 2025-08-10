#!/usr/bin/env python3
"""Clear all events from Nylas calendar"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nylas import Client as NylasClient

def clear_test_events():
    """Clear all test events from Nylas calendar"""
    # Load credentials from .env.test
    env_file = Path(__file__).parent.parent / ".env.test"
    if not env_file.exists():
        print("❌ No .env.test file found")
        print("   Please copy .env.test.example to .env.test and add your credentials")
        return
    
    load_dotenv(env_file)
    api_key = os.getenv('NYLAS_API_KEY')
    grant_id = os.getenv('NYLAS_GRANT_ID')
    
    if not api_key or not grant_id:
        print("❌ Missing NYLAS_API_KEY or NYLAS_GRANT_ID in .env.test")
        return
    
    print("🔄 Connecting to Nylas...")
    
    try:
        # Create client
        client = NylasClient(
            api_key=api_key,
            api_uri="https://api.us.nylas.com"
        )
        
        # Get events from past week to next month
        now = datetime.now(pytz.UTC)
        start = now - timedelta(days=7)
        end = now + timedelta(days=30)
        
        print("📅 Fetching calendar events...")
        print(f"   Time range: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
        
        try:
            response = client.events.list(
                identifier=grant_id,
                query_params={
                    "calendar_id": "primary",
                    "start": int(start.timestamp()),
                    "end": int(end.timestamp()),
                    "limit": 100
                }
            )
            
            # Handle response format
            if hasattr(response, 'data'):
                events = response.data
            else:
                events = response
                
        except Exception as e:
            print(f"❌ Failed to fetch events: {e}")
            return
        
        # Convert to list for easier handling
        all_events = list(events)
        
        if not all_events:
            print("✅ No events found - your calendar is already empty!")
            return
        
        print(f"\n🔍 Found {len(all_events)} events in total:")
        print("-" * 60)
        for i, event in enumerate(all_events, 1):
            title = getattr(event, 'title', 'Untitled')
            event_id = getattr(event, 'id', 'Unknown')
            
            # Get event time
            when = getattr(event, 'when', None)
            if when and hasattr(when, 'start_time'):
                start_time = datetime.fromtimestamp(when.start_time, tz=pytz.UTC)
                time_str = start_time.strftime('%Y-%m-%d %H:%M %Z')
            else:
                time_str = 'Unknown time'
                
            print(f"{i:2d}. {title}")
            print(f"    ID: {event_id}")
            print(f"    Time: {time_str}")
        print("-" * 60)
        
        # Confirm deletion
        print("\n⚠️  This will permanently delete ALL events from your calendar!")
        print("   (Since this is a test calendar account, this should be fine)")
        response = input("Delete ALL events? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled - no events were deleted")
            return
        
        # Delete events
        print("\n🗑️  Deleting all events...")
        success_count = 0
        for event in all_events:
            try:
                event_id = getattr(event, 'id', None)
                if event_id:
                    client.events.destroy(
                        grant_id, 
                        event_id,
                        query_params={"calendar_id": "primary"}
                    )
                    print(f"✅ Deleted: {getattr(event, 'title', 'Untitled')}")
                    success_count += 1
                else:
                    print(f"⚠️  Skipped event with no ID: {getattr(event, 'title', 'Untitled')}")
            except Exception as e:
                print(f"❌ Failed to delete {getattr(event, 'title', 'Untitled')}: {e}")
        
        print(f"\n✅ Cleanup complete! Deleted {success_count}/{len(all_events)} events")
        
    except Exception as e:
        print(f"❌ Error connecting to Nylas: {e}")
        print("   Please check your API key and grant ID in .env.test")

if __name__ == "__main__":
    print("🧹 Nylas Calendar Complete Cleanup")
    print("==================================\n")
    clear_test_events()