"""End-to-end tests for check_availability tool."""
import pytest
from datetime import datetime, timedelta
import pytz
from tests.e2e.utils.test_helpers import assert_response_fulfills_expectation


@pytest.mark.e2e
class TestCheckAvailabilityE2E:
    """E2E tests for the check_availability tool."""
    
    @pytest.fixture
    def class_test_data(self, juli_client, test_context, test_data_tracker):
        """Create calendar items once for all availability tests."""
        # Create a meeting for tomorrow at 2pm
        response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Team meeting tomorrow at 2pm for 1 hour",
                "context": "Blocking time for availability testing"
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
        
        # Create a task that needs 2 hours
        response = juli_client.execute_tool(
            "manage_productivity",
            {
                "query": "Deep work task - needs 2 hours of focus time",
                "context": "Task for availability testing"
            },
            test_context
        )
        
        task_id = None
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "id" in data.get("data", {}):
                task_id = data["data"]["id"]
                test_data_tracker.add_task(task_id)
        
        # Give APIs time to process
        yield {"event_id": event_id, "task_id": task_id}
    
    @pytest.fixture(autouse=True)
    def use_class_data(self, class_test_data):
        """Make class data available to each test."""
        # This ensures class_test_data runs and is available
        pass
    
    def test_check_specific_time_available(self, juli_client, test_context):
        """Test checking if a specific time is available."""
        # Check tomorrow at 10am (should be free based on our setup)
        response = juli_client.execute_tool(
            "check_availability",
            {
                "query": "Am I free tomorrow at 10am?",
                "duration_minutes": 60
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Check availability for tomorrow at 10am. Response should indicate availability status and not show conflicts at 10am.",
            {"query": "Am I free tomorrow at 10am?", "duration_minutes": 60}
        )
    
    def test_check_specific_time_busy(self, juli_client, test_context):
        """Test checking a time that should be busy."""
        # Check tomorrow at 2pm (when we have the test meeting)
        response = juli_client.execute_tool(
            "check_availability",
            {
                "query": "Am I free tomorrow at 2pm for 30 minutes?",
                "duration_minutes": 30
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Check availability for tomorrow at 2pm (when test meeting is scheduled). Should show as busy/unavailable or list the conflicting meeting.",
            {"query": "Am I free tomorrow at 2pm for 30 minutes?", "duration_minutes": 30}
        )
    
    def test_find_time_slots(self, juli_client, test_context):
        """Test finding available time slots."""
        response = juli_client.execute_tool(
            "check_availability",
            {
                "query": "Find 2 hours for deep work this week, preferably in the morning",
                "duration_minutes": 120
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Find available 2-hour time slots for deep work this week, preferably in the morning. Should return a list of available time slots.",
            {"query": "Find 2 hours for deep work this week, preferably in the morning", "duration_minutes": 120}
        )
    
    def test_check_various_durations(self, juli_client, test_context):
        """Test checking availability for different durations."""
        durations = [
            {"query": "Do I have 15 minutes free this afternoon?", "duration": 15},
            {"query": "Can I fit in a 1-hour meeting today?", "duration": 60},
            {"query": "Find 3 hours for a workshop this week", "duration": 180}
        ]
        
        for test_case in durations:
            response = juli_client.execute_tool(
                "check_availability",
                {
                    "query": test_case["query"],
                    "duration_minutes": test_case["duration"]
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                response.json(),
                f"Check availability for {test_case['duration']} minutes based on query: '{test_case['query']}'. Should return availability status or available slots.",
                {"query": test_case["query"], "duration_minutes": test_case["duration"]}
            )
            
            # Be nice to the API
    
    def test_natural_language_time_expressions(self, juli_client, test_context):
        """Test various natural language time expressions."""
        queries = [
            "Am I free right now?",
            "Do I have time this afternoon?",
            "Check my availability next Tuesday at 3pm",
            "When can I schedule a 45-minute call?"
        ]
        
        for query in queries:
            response = juli_client.execute_tool(
                "check_availability",
                {
                    "query": query,
                    "duration_minutes": 60  # Default duration
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                response.json(),
                f"Parse natural language time expression: '{query}' and check availability. Should understand the time reference and return availability information.",
                {"query": query, "duration_minutes": 60}
            )
            
            # Be nice to the API
    
