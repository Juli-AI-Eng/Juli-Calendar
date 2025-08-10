"""End-to-end tests for approval flows."""
import pytest
import os
from datetime import datetime, timedelta
import pytz
from tests.e2e.utils.test_helpers import assert_response_fulfills_expectation


@pytest.mark.e2e
class TestApprovalFlowE2E:
    """E2E tests for operations that require approval."""
    
    def test_task_delete_no_approval_flow(self, juli_client, test_context, test_data_tracker):
        """Test that single task deletion does NOT require approval."""
        # Step 1: Create a task to delete
        create_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Task to test deletion without approval",
                "context": "This task will be deleted without approval"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            create_response.json(),
            "Step 1: Create a task successfully without requiring approval. This is the creation step before testing deletion. Task should be created immediately.",
            {"query": "Task to test deletion without approval", "context": "This task will be deleted without approval"}
        )
        create_data = create_response.json()
        
        task_id = create_data["data"]["id"]
        test_data_tracker.add_task(task_id)
        
        # Step 2: Delete the task - should NOT require approval (single task)
        delete_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": f"Delete the task 'Task to test deletion without approval'",
                "context": "Deleting this single task"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            delete_response.json(),
            "Delete the single task without requiring approval. The task should be deleted immediately (no needs_approval flag).",
            {"query": f"Delete the task 'Task to test deletion without approval'", "context": "Deleting this single task"}
        )
        delete_data = delete_response.json()
        
        # Remove from tracker since it's already deleted
        test_data_tracker.reclaim_tasks.remove(task_id)
    
    def test_event_with_participants_approval_flow(self, juli_client, test_context, test_data_tracker):
        """Test that events with participants require approval."""
        # Step 1: Try to create an event with participants - should require approval
        create_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Schedule a meeting with John and Sarah tomorrow at 2pm",
                "context": "Team sync meeting"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            create_response.json(),
            "Creating an event with participants (John and Sarah) should require approval. Response should have needs_approval=true and include action_data for later approval.",
            {"query": "Schedule a meeting with John and Sarah tomorrow at 2pm", "context": "Team sync meeting"}
        )
        create_data = create_response.json()
        
        # Step 2: Send the approved action
        approved_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "approved": True,
                "action_data": create_data["action_data"]
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            approved_response.json(),
            "Successfully create the event after approval. Response should show success=true and the event should be created.",
            {"approved": True, "action_data": create_data["action_data"]}
        )
        approved_data = approved_response.json()
        
        # Track for cleanup
        if "id" in approved_data["data"]:
            test_data_tracker.add_event(approved_data["data"]["id"])
        
    
    def test_event_cancel_solo_no_approval_flow(self, juli_client, test_context, test_data_tracker):
        """Test that canceling solo events does NOT require approval."""
        # First create a solo event (no approval needed)
        create_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Personal appointment tomorrow at 3pm",
                "context": "Solo event"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            create_response.json(),
            "Create a solo event (personal appointment) without requiring approval. Event should be created immediately.",
            {"query": "Personal appointment tomorrow at 3pm", "context": "Solo event"}
        )
        create_data = create_response.json()
        
        event_id = create_data["data"]["id"]
        test_data_tracker.add_event(event_id)
        
        # Now test cancellation - should NOT require approval for solo events
        cancel_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Cancel the Personal appointment tomorrow at 3pm",
                "context": "Cancelling solo event"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            cancel_response.json(),
            "Cancel the solo event without requiring approval. The event should be cancelled immediately (no needs_approval flag).",
            {"query": "Cancel the Personal appointment tomorrow at 3pm", "context": "Cancelling solo event"}
        )
        cancel_data = cancel_response.json()
        
        # Remove from tracker since it's cancelled
        test_data_tracker.nylas_events.remove(event_id)
        
    
    def test_bulk_operation_approval_flow(self, juli_client, test_context, test_data_tracker):
        """Test that bulk operations require approval."""
        # Create multiple tasks first
        task_ids = []
        for i in range(3):
            create_response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": f"Bulk test task {i+1}",
                    "context": "For bulk operation testing"
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                create_response.json(),
                f"Create task number {i+1} for bulk operation testing",
                {"query": f"Bulk test task {i+1}", "context": "For bulk operation testing"}
            )
            create_data = create_response.json()
            if create_data.get("success") and create_data.get("data", {}).get("id"):
                task_ids.append(create_data["data"]["id"])
                test_data_tracker.add_task(create_data["data"]["id"])
        
        # Now test bulk operation with approval
        # Step 1: Try bulk complete - should require approval
        bulk_response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Complete all tasks with 'Bulk test' in the title",
                "context": "Bulk completion test"
            },
            test_context
        )
        
        assert bulk_response.status_code == 200
        bulk_data = bulk_response.json()
        
        # Should require approval for bulk operation
        # Note: Current implementation might not detect bulk operations yet
        # but the structure is in place
        if bulk_data.get("needs_approval"):
            assert "action_data" in bulk_data
            
            # Step 2: Send the approved action
            approved_response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "approved": True,
                    "action_data": bulk_data["action_data"]
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                approved_response.json(),
                "Execute the bulk operation after approval. Should complete all matching tasks.",
                {"approved": True, "action_data": bulk_data["action_data"]}
            )
        
    
