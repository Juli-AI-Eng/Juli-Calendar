"""Debug test for AI classification."""
import pytest
from tests.e2e.utils.test_helpers import assert_success_response


@pytest.mark.e2e
class TestDebugAIClassification:
    """Debug AI classification issues."""
    
    def test_task_classification(self, juli_client, test_context):
        """Test that queries with 'task' are classified correctly."""
        test_queries = [
            "Create a task to review the budget",
            "Task to delete without approval",
            "I need a new task for the project",
            "Add task: Complete documentation",
            "task task task task",  # Extreme case
        ]
        
        for query in test_queries:
            print(f"\n\nTesting query: {query}")
            response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": query,
                    "context": "Debug test"
                },
                test_context
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Print the full response for debugging
            import json
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Check if it's classified as task/reclaim
            if "error" in data and "nylas" in data.get("provider", ""):
                print(f"ERROR: Query '{query}' was incorrectly routed to Nylas!")
                assert False, f"Task query was routed to Nylas: {query}"
            
            # For successful responses or approval requests
            if data.get("provider"):
                assert data["provider"] == "reclaim", f"Expected reclaim, got {data['provider']}"
            elif data.get("preview", {}).get("details", {}).get("provider"):
                assert data["preview"]["details"]["provider"] == "reclaim"
    
    def test_event_classification(self, juli_client, test_context):
        """Test that event queries are classified correctly."""
        test_queries = [
            "Schedule a meeting tomorrow at 2pm",
            "Book an appointment with the dentist",
            "Set up a call at 3pm",
        ]
        
        for query in test_queries:
            print(f"\n\nTesting query: {query}")
            response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": query,
                    "context": "Debug test"
                },
                test_context
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Print for debugging
            import json
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Check if it's classified as event/nylas
            if data.get("provider"):
                assert data["provider"] == "nylas", f"Expected nylas, got {data['provider']}"
            elif data.get("preview", {}).get("details", {}).get("provider"):
                assert data["preview"]["details"]["provider"] == "nylas"