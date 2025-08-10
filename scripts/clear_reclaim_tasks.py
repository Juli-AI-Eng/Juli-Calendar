#!/usr/bin/env python3
"""Clear all tasks from Reclaim.ai"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from reclaim_sdk.client import ReclaimClient
from reclaim_sdk.resources.task import Task

def clear_test_tasks():
    """Clear all test tasks from Reclaim.ai"""
    # Load credentials from .env.test
    env_file = Path(__file__).parent.parent / ".env.test"
    if not env_file.exists():
        print("❌ No .env.test file found")
        print("   Please copy .env.test.example to .env.test and add your credentials")
        return
    
    load_dotenv(env_file)
    api_key = os.getenv('RECLAIM_API_KEY')
    
    if not api_key:
        print("❌ No RECLAIM_API_KEY found in .env.test")
        return
    
    print("🔄 Connecting to Reclaim.ai...")
    
    try:
        # Create client
        client = ReclaimClient.configure(token=api_key)
        
        # Get all tasks
        print("📋 Fetching tasks...")
        tasks = Task.list(client)
        
        # Ensure tasks is a list
        if not isinstance(tasks, list):
            print("⚠️  Unexpected response format from API")
            return
        
        if not tasks:
            print("✅ No tasks found - your Reclaim is already empty!")
            return
        
        print(f"\n🔍 Found {len(tasks)} tasks in total:")
        print("-" * 60)
        for i, task in enumerate(tasks, 1):
            print(f"{i:2d}. {task.title}")
            print(f"    ID: {task.id} | Status: {task.status}")
        print("-" * 60)
        
        # Confirm deletion
        print("\n⚠️  This will permanently delete ALL tasks from your Reclaim.ai account!")
        print("   (Since this is a test account, this should be fine)")
        response = input("Delete ALL tasks? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled - no tasks were deleted")
            return
        
        # Delete tasks
        print("\n🗑️  Deleting all tasks...")
        success_count = 0
        for task in tasks:
            try:
                task._client = client
                task.delete()
                print(f"✅ Deleted: {task.title}")
                success_count += 1
            except Exception as e:
                print(f"❌ Failed to delete {task.title}: {e}")
        
        print(f"\n✅ Cleanup complete! Deleted {success_count}/{len(tasks)} tasks")
        
    except Exception as e:
        print(f"❌ Error connecting to Reclaim.ai: {e}")
        print("   Please check your API key in .env.test")

if __name__ == "__main__":
    print("🧹 Reclaim.ai Complete Task Cleanup")
    print("===================================\n")
    clear_test_tasks()