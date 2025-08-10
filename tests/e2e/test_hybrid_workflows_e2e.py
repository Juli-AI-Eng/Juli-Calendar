"""End-to-end tests for hybrid workflows combining multiple tools."""
import pytest
from datetime import datetime, timedelta
import pytz
from tests.e2e.utils.test_helpers import assert_response_fulfills_expectation


@pytest.mark.e2e
class TestHybridWorkflowsE2E:
    """E2E tests for workflows that combine multiple tools."""
    
    def test_check_availability_then_schedule(self, juli_client, test_context, test_data_tracker):
        """Test checking availability before scheduling a meeting."""
        # Step 1: Check availability
        check_response = juli_client.execute_tool(
            "check_availability",
            {
                "query": "Find 1 hour for a meeting tomorrow afternoon",
                "duration_minutes": 60
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            check_response.json(),
            "Check availability for 1 hour meeting tomorrow afternoon. Should return available time slots.",
            {"query": "Find 1 hour for a meeting tomorrow afternoon", "duration_minutes": 60}
        )
        check_data = check_response.json()
        
        # Step 2: If slots available, schedule a meeting
        if "slots" in check_data and check_data["slots"]:
            # Use the first available slot
            slot = check_data["slots"][0]
            
            # Schedule the meeting
            schedule_response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": f"Schedule project review meeting at the available time",
                    "context": f"Using available slot: {slot}"
                },
                test_context
            )
            
            assert schedule_response.status_code == 200
            schedule_data = schedule_response.json()
            
            # Handle approval if needed for meetings with participants
            if schedule_data.get("needs_approval"):
                approved_response = juli_client.execute_tool(
                    "manage_productivity",
                    {
                        "approved": True,
                        "action_data": schedule_data["action_data"]
                    },
                    test_context
                )
                schedule_data = approved_response.json()
            
            if schedule_data.get("success"):
                # Track for cleanup
                if "id" in schedule_data.get("data", {}):
                    test_data_tracker.add_event(schedule_data["data"]["id"])
    
    def test_find_tasks_and_complete(self, juli_client, test_context, test_data_tracker):
        """Test finding tasks and marking them complete."""
        import os
        interactive = os.getenv("E2E_INTERACTIVE", "false").lower() == "true"
        
        print("\n" + "="*60)
        print(">>> STEP 1: Creating test task")
        print("="*60)
        
        # Step 1: Create a test task
        create_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Quick task to complete in workflow test",
                "context": "Will be found and completed"
            },
            test_context
        )
        
        assert create_response.status_code == 200
        create_data = create_response.json()
        
        if create_data.get("success"):
            task_id = create_data["data"].get("id")
            task_title = create_data["data"].get("title", "")
            if task_id:
                test_data_tracker.add_task(task_id)
                print(f"\n✅ Task created: '{task_title}' (ID: {task_id})")
        
        if interactive:
            print("\n📋 CHECK RECLAIM: Task should be created")
            input("Press Enter to search for it...")
        
        print("\n" + "="*60)
        print(">>> STEP 2: Finding the task")
        print("="*60)
        
        # Step 2: Find the task
        find_response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "Find tasks with 'workflow test' in the title",
                "scope": "tasks"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            find_response.json(),
            "Find tasks containing 'workflow test' in the title. Should return at least the test task we just created.",
            {"query": "Find tasks with 'workflow test' in the title", "scope": "tasks"}
        )
        find_data = find_response.json()
        print(f"\n✅ Found {len(find_data['data'].get('tasks', []))} task(s)")
        
        if interactive and find_data["data"].get("tasks"):
            input("Press Enter to mark it complete...")
        
        print("\n" + "="*60)
        print(">>> STEP 3: Marking task complete")
        print("="*60)
        
        # Step 3: Complete the found task
        if find_data["data"].get("tasks"):
            found_task = find_data["data"]["tasks"][0]
            
            complete_response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": f"Mark task '{found_task['title']}' as complete",
                    "context": "Completing the task found from analysis"
                },
                test_context
            )
            
            assert complete_response.status_code == 200
            print(f"\n✅ Task marked as complete!")
    
    def test_analyze_workload_then_optimize(self, juli_client, test_context):
        """Test analyzing workload before optimizing schedule."""
        # Step 1: Analyze current workload
        analyze_response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "How's my workload looking this week?",
                "scope": "both"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            analyze_response.json(),
            "Analyze workload for this week. Should return workload analysis with tasks and events summary.",
            {"query": "How's my workload looking this week?", "scope": "both"}
        )
        analyze_data = analyze_response.json()
        
        # Step 2: Based on analysis, optimize
        optimize_response = juli_client.execute_tool(
            "optimize_schedule",
            {
                "request": "Based on my current workload, help me balance things better",
                "preferences": f"Current analysis: {analyze_data.get('message', 'Heavy workload')}"
            },
            test_context
        )
        
        assert optimize_response.status_code == 200
        optimize_data = optimize_response.json()
        
        # Should provide optimization suggestions
        assert optimize_data.get("needs_approval") or optimize_data.get("success")
    
    def test_task_to_calendar_event_conversion(self, juli_client, test_context, test_data_tracker):
        """Test converting a task into a calendar event."""
        # Step 1: Create a task
        task_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Important presentation prep - needs dedicated time",
                "context": "This task needs calendar time blocked"
            },
            test_context
        )
        
        assert task_response.status_code == 200
        task_data = task_response.json()
        
        if task_data.get("success") and task_data["provider"] == "reclaim":
            task_id = task_data["data"].get("id")
            if task_id:
                test_data_tracker.add_task(task_id)
            
            
            # Step 2: Check availability for the task
            avail_response = juli_client.execute_tool(
                "check_availability",
                {
                    "query": "Find 2 hours tomorrow for presentation prep",
                    "duration_minutes": 120
                },
                test_context
            )
            
            assert avail_response.status_code == 200
            avail_data = avail_response.json()
            
            # Step 3: Create calendar block for the task
            if avail_data.get("success") and (avail_data.get("available") or avail_data.get("slots")):
                event_response = juli_client.execute_tool(
                    "manage_productivity",
                    {
                        "query": "Block time tomorrow for presentation prep",
                        "context": "Converting task to calendar event"
                    },
                    test_context
                )
                
                assert event_response.status_code == 200
                event_data = event_response.json()
                
                if event_data.get("success") and "id" in event_data.get("data", {}):
                    test_data_tracker.add_event(event_data["data"]["id"])
    
    def test_full_productivity_workflow(self, juli_client, test_context, test_data_tracker):
        """Test a complete productivity workflow."""
        # Step 1: Check what's on the schedule
        find_response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "What do I have coming up this week?",
                "scope": "both"
            },
            test_context
        )
        
        assert find_response.status_code == 200
        
        # Step 2: Check availability for new work
        avail_response = juli_client.execute_tool(
            "check_availability",
            {
                "query": "Do I have 3 hours free this week for a new project?",
                "duration_minutes": 180
            },
            test_context
        )
        
        assert avail_response.status_code == 200
        
        # Step 3: Create a task for the new project
        task_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "New project research and planning",
                "context": "Needs 3 hours total"
            },
            test_context
        )
        
        assert task_response.status_code == 200
        task_data = task_response.json()
        
        if task_data.get("success") and "id" in task_data.get("data", {}):
            if task_data["provider"] == "reclaim":
                test_data_tracker.add_task(task_data["data"]["id"])
            else:
                test_data_tracker.add_event(task_data["data"]["id"])
        
        # Step 4: Optimize schedule to fit everything
        optimize_response = juli_client.execute_tool(
            "optimize_schedule",
            {
                "request": "Help me fit in the new project work efficiently",
                "preferences": "Prefer longer focus blocks"
            },
            test_context
        )
        
        assert optimize_response.status_code == 200
        
        # The workflow should complete successfully
        # Each step builds on the previous one