"""Test AI routing specifically for task vs event classification."""
import pytest
from tests.e2e.utils.test_helpers import assert_response_fulfills_expectation


@pytest.mark.e2e 
class TestAIRouting:
    """Test that AI correctly routes queries containing 'task' to Reclaim."""
    
    def test_task_query_routes_to_reclaim(self, juli_client, test_context):
        """Test that queries containing 'task' are routed to Reclaim."""
        test_queries = [
            "Task to test deletion without approval",
            "Create a task to review budget",
            "Task to fix the bug",
            "Delete the task about testing",
            "Update my task for tomorrow"
        ]
        
        for query in test_queries:
            response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": query,
                    "context": "Testing AI routing"
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                response.json(),
                f"Route the query '{query}' to Reclaim.ai (tasks) not Nylas (events). The response should show provider='reclaim' or have task-related content/errors, not event-related errors.",
                {"query": query, "context": "Testing AI routing"}
            )
    
    def test_event_query_routes_to_nylas(self, juli_client, test_context):
        """Test that meeting/appointment queries are routed to Nylas."""
        test_queries = [
            "Schedule a meeting with John tomorrow at 2pm",
            "Personal appointment at 3pm",
            "Book a conference call for next week"
        ]
        
        for query in test_queries:
            response = juli_client.execute_tool(
                "manage_productivity", 
                {
                    "query": query,
                    "context": "Testing AI routing"
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                response.json(),
                f"Route the query '{query}' to Nylas (events) not Reclaim.ai (tasks). The response should show provider='nylas' or have event/calendar-related content/errors, not task-related errors.",
                {"query": query, "context": "Testing AI routing"}
            )