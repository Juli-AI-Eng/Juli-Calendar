#!/usr/bin/env python3
"""Debug script to test task retrieval and filtering"""

import asyncio
import json
import os
from datetime import datetime
import pytz
from reclaim_sdk.client import ReclaimClient
from reclaim_sdk.resources.task import Task, TaskStatus

# Load credentials
from dotenv import load_dotenv
load_dotenv('.env.test')

async def test_tasks():
    """Test task retrieval directly"""
    
    # Setup
    credentials = {
        "reclaim_api_key": os.getenv("RECLAIM_API_KEY"),
    }
    
    # User context
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    
    print(f"Current time: {now}")
    print(f"Current date: {now.strftime('%Y-%m-%d')}")
    
    # Test: Get all tasks from Reclaim
    print("\n=== TESTING RECLAIM TASK RETRIEVAL ===")
    
    client = ReclaimClient.configure(token=credentials["reclaim_api_key"])
    all_tasks = Task.list(client)
    
    print(f"Total tasks from Reclaim: {len(all_tasks)}")
    
    # Convert to standardized format and check filtering
    task_dicts = []
    for task in all_tasks:
        # Skip completed/archived tasks unless specifically requested
        include_completed = False
        if not include_completed:
            if task.status in [TaskStatus.COMPLETE, TaskStatus.CANCELLED, TaskStatus.ARCHIVED]:
                print(f"Skipping completed/cancelled/archived task: {task.title} (status: {task.status})")
                continue
        
        task_dict = {
            "id": task.id,
            "title": task.title,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "priority": str(task.priority),
            "due": task.due.isoformat() if task.due else None,
            "duration_hours": task.duration if task.duration else 0,
            "notes": task.notes,
            "provider": "reclaim",
            "type": "task"
        }
        task_dicts.append(task_dict)
        
        print(f"Task: {task.title}")
        print(f"  ID: {task.id}")
        print(f"  Status: {task.status}")
        print(f"  Due: {task.due}")
        print(f"  Due ISO: {task_dict['due']}")
        print()
    
    print(f"Non-completed tasks: {len(task_dicts)}")
    
    # Test time filtering
    print("\n=== TESTING TIME FILTERING ===")
    time_range = "today"
    
    filtered_tasks = []
    for task in task_dicts:
        if not task.get("due"):
            print(f"Skipping task without due date: {task['title']}")
            continue
        
        try:
            task_due = datetime.fromisoformat(task["due"].replace("Z", "+00:00"))
            print(f"Parsing due date for task '{task['title']}': {task['due']} -> {task_due}")
            
            # Ensure both datetimes have timezone info for comparison
            if task_due.tzinfo is None:
                task_due = task_due.replace(tzinfo=now.tzinfo)
                print(f"  Added timezone: {task_due}")
            
            if time_range == "today":
                # Check if task is due today (same date)
                print(f"  Comparing dates: {task_due.date()} == {now.date()}")
                if task_due.date() == now.date():
                    filtered_tasks.append(task)
                    print(f"  ✅ Task included (due today)")
                else:
                    print(f"  ❌ Task excluded (not due today)")
                    
        except Exception as e:
            print(f"Failed to parse due date for task {task['id']}: {e}")
            continue
    
    print(f"\nTasks due today: {len(filtered_tasks)}")
    for task in filtered_tasks:
        print(f"  - {task['title']} (due: {task['due']})")

if __name__ == "__main__":
    asyncio.run(test_tasks())