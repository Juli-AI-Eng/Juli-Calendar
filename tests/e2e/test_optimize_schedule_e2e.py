"""End-to-end tests for optimize_schedule tool."""
import pytest
from datetime import datetime, timedelta
import pytz
from tests.e2e.utils.test_helpers import assert_response_fulfills_expectation


@pytest.mark.e2e
class TestOptimizeScheduleE2E:
    """E2E tests for the optimize_schedule tool."""
    
    @pytest.fixture
    def class_test_data(self, juli_client, test_context, test_data_tracker):
        """Create a realistic schedule once for all optimization tests."""
        # Create several meetings clustered together
        meetings = [
            "Morning standup at 9am tomorrow",
            "Client call at 10am tomorrow", 
            "Team sync at 11am tomorrow",
            "Lunch meeting at 12pm tomorrow"
        ]
        
        event_ids = []
        for meeting in meetings:
            response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": meeting,
                    "context": "Test meeting for optimization"
                },
                test_context
            )
            
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
                    event_ids.append(event_id)
                    test_data_tracker.add_event(event_id)
            
        
        # Create some tasks with different priorities
        tasks = [
            "High priority: Complete project proposal",
            "Medium priority: Review code changes",
            "Low priority: Update documentation"
        ]
        
        task_ids = []
        for task in tasks:
            response = juli_client.execute_tool(
                "manage_productivity",
                {
                    "query": task,
                    "context": "Test task for optimization"
                },
                test_context
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "id" in data.get("data", {}):
                    task_id = data["data"]["id"]
                    task_ids.append(task_id)
                    test_data_tracker.add_task(task_id)
            
        
        # Give APIs time to process
        yield {"event_ids": event_ids, "task_ids": task_ids}
    
    @pytest.fixture(autouse=True)
    def use_class_data(self, class_test_data):
        """Make class data available to each test."""
        # This ensures class_test_data runs and is available
        pass
    
    def test_optimize_for_focus_time(self, juli_client, test_context):
        """Test optimizing schedule for focus time."""
        response = juli_client.execute_tool(
            "optimize_schedule",
            {
                "request": "Maximize my focus time this week",
                "preferences": "I work best in the mornings"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Optimize schedule to maximize focus time in the mornings. Should provide suggestions for creating focus blocks, batching meetings, require approval for major changes, OR indicate the schedule is already optimized (conservative approach is valid).",
            {"request": "Maximize my focus time this week", "preferences": "I work best in the mornings"}
        )
    
    def test_balance_workload_optimization(self, juli_client, test_context):
        """Test optimizing for balanced workload."""
        response = juli_client.execute_tool(
            "optimize_schedule",
            {
                "request": "Balance my workload better across the week",
                "preferences": "Avoid overloading any single day"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Optimize schedule to balance workload across the week. Should provide suggestions for distributing tasks evenly, show workload metrics, OR indicate the workload is already balanced.",
            {"request": "Balance my workload better across the week", "preferences": "Avoid overloading any single day"}
        )
    
    def test_meeting_reduction_optimization(self, juli_client, test_context):
        """Test optimizing to reduce meeting overload."""
        response = juli_client.execute_tool(
            "optimize_schedule",
            {
                "request": "Help me reduce meeting overload and batch them better",
                "preferences": "Prefer meeting-free mornings for deep work"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Optimize schedule to reduce meeting overload and batch meetings better. Should suggest meeting consolidation, meeting-free blocks, require approval for changes affecting others, OR indicate meetings are already well-organized.",
            {"request": "Help me reduce meeting overload and batch them better", "preferences": "Prefer meeting-free mornings for deep work"}
        )
    
    def test_priority_based_optimization(self, juli_client, test_context):
        """Test optimizing based on task priorities."""
        response = juli_client.execute_tool(
            "optimize_schedule",
            {
                "request": "Schedule my tasks based on priority, urgent items first",
                "preferences": "High-priority work in the morning when I'm fresh"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Optimize schedule based on task priorities. Should suggest scheduling high-priority items in optimal time slots (mornings), arrange tasks by importance, OR indicate priorities are already well-aligned.",
            {"request": "Schedule my tasks based on priority, urgent items first", "preferences": "High-priority work in the morning when I'm fresh"}
        )
    
    def test_energy_based_optimization(self, juli_client, test_context):
        """Test optimizing based on energy levels."""
        response = juli_client.execute_tool(
            "optimize_schedule",
            {
                "request": "Optimize my schedule based on my energy levels",
                "preferences": "I'm most productive 9-11am and 2-4pm, low energy after lunch"
            },
            test_context
        )
        
        assert_response_fulfills_expectation(
            response.json(),
            "Optimize schedule based on energy levels (high: 9-11am and 2-4pm, low: after lunch). Should suggest aligning demanding tasks with high-energy periods OR indicate the schedule already aligns with energy patterns.",
            {"request": "Optimize my schedule based on my energy levels", "preferences": "I'm most productive 9-11am and 2-4pm, low energy after lunch"}
        )
    
    def test_natural_language_optimization_requests(self, juli_client, test_context):
        """Test various natural language optimization requests."""
        requests = [
            "Make my schedule less chaotic",
            "I need more time for deep work",
            "Help me be more productive",
            "Reduce context switching"
        ]
        
        for request in requests:
            response = juli_client.execute_tool(
                "optimize_schedule",
                {
                    "request": request,
                    "preferences": ""
                },
                test_context
            )
            
            assert_response_fulfills_expectation(
                response.json(),
                f"Understand and optimize based on natural language request: '{request}'. Should either provide relevant suggestions OR indicate the schedule is already well-optimized (conservative optimization is acceptable).",
                {"request": request, "preferences": ""}
            )
            
            # Be nice to the API
