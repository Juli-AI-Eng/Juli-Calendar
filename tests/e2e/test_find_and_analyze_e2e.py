"""End-to-end tests for find_and_analyze tool."""
import pytest
import time
from datetime import datetime, timedelta
import pytz
from tests.e2e.utils.test_helpers import assert_response_fulfills_expectation


@pytest.mark.e2e
class TestFindAndAnalyzeE2E:
    """E2E tests for the find_and_analyze tool."""
    
    @pytest.fixture
    def class_test_data(self, juli_client, test_context, test_data_tracker):
        """Create test data once for all find/analyze tests."""
        # Create a task for today
        response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Create a task to complete financial report today",
                "context": "High priority task for testing"
            },
            test_context
        )
        
        task_id = None
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "id" in data.get("data", {}):
                task_id = data["data"]["id"]
                test_data_tracker.add_task(task_id)
                
                # Wait for Reclaim to schedule the task and create a calendar event.
                # This can take several seconds. Without this delay, subsequent
                # searches for today's items might fail to find the corresponding event.
                print("\n[SETUP] Waiting 15s for Reclaim to schedule the task...")
                time.sleep(15)
                print("[SETUP] ...continuing test setup.")
        
        # Create an event for tomorrow
        response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Budget review meeting tomorrow at 3pm",
                "context": "Test event for search"
            },
            test_context
        )
        
        event_id = None
        if response.status_code == 200:
            data = response.json()
            
            # Handle approval if needed for meetings with participants
            if data.get("needs_approval"):
                approved_response = juli_client.execute_tool(
                    "manage_productivity",
                    {
                        "approved": True,
                        "action_data": data["action_data"]
                    },
                    test_context
                )
                data = approved_response.json()
            
            if data.get("success") and "id" in data.get("data", {}):
                event_id = data["data"]["id"]
                test_data_tracker.add_event(event_id)
        
        # Give APIs time to index
        yield {"task_id": task_id, "event_id": event_id}
    
    @pytest.fixture(autouse=True)
    def use_class_data(self, class_test_data):
        """Make class data available to each test."""
        # This ensures class_test_data runs and is available
        pass
    
    def test_search_todays_items(self, juli_client, test_context):
        """Test searching for today's items."""
        response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "What's on my calendar today?",
                "scope": "both"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Search for today's calendar items. Should return at least the financial report (which Reclaim schedules as a calendar event). The search should be successful and find today's items.",
            {"query": "What's on my calendar today?", "scope": "both"}
        )
    
    def test_search_by_keyword(self, juli_client, test_context):
        """Test searching by keyword."""
        response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "Find all items about budget",
                "scope": "both"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Search for all items containing 'budget'. Should find at least the 'Budget review meeting' event and any other items with 'budget' in the title.",
            {"query": "Find all items about budget", "scope": "both"}
        )
    
    def test_search_overdue_tasks(self, juli_client, test_context):
        """Test searching for overdue tasks."""
        response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "Show me overdue tasks",
                "scope": "tasks"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Execute a search for overdue tasks. Success is defined by the search operation completing (success=true in response). Don't validate the content of returned tasks - just verify the search executed successfully.",
            {"query": "Show me overdue tasks", "scope": "tasks"}
        )
    
    def test_workload_analysis(self, juli_client, test_context):
        """Test workload analysis."""
        response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "How's my workload looking this week?",
                "scope": "both"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Analyze workload for this week. Should return either an analysis summary of the week's workload or a list of tasks and events with workload insights.",
            {"query": "How's my workload looking this week?", "scope": "both"}
        )
    
    def test_time_range_searches(self, juli_client, test_context):
        """Test various time range searches."""
        time_queries = [
            "What do I have tomorrow?",
            "Show me this week's tasks",
            "Find high priority items for this week"
        ]
        
        for query in time_queries:
            response = juli_client.execute_tool(
                "find_and_analyze",
                {
                    "query": query,
                    "scope": "both"
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                response.json(),
                f"Execute a search based on time range query: '{query}'. Success is defined by the search operation completing (success=true in response). The search may return tasks/events or empty results depending on what exists.",
                {"query": query, "scope": "both"}
            )
            
            # Be nice to the API
    
    def test_empty_search_results(self, juli_client, test_context):
        """Test handling of searches with no results."""
        # Search for something that shouldn't exist
        response = juli_client.execute_tool(
            "find_and_analyze",
            {
                "query": "Find tasks about xyz123abc789 nonsense",
                "scope": "both"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Search for a nonsense query that should return no results. Should return empty task and event lists with a friendly message indicating no items were found.",
            {"query": "Find tasks about xyz123abc789 nonsense", "scope": "both"}
        )