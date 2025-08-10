"""Integration tests for tools through HTTP endpoints."""
import pytest
import json
from unittest.mock import patch, Mock
import asyncio


class TestManageTasksIntegration:
    """Integration tests for manage_tasks tool through HTTP."""
    
    @pytest.fixture
    def valid_request_data(self):
        """Valid request data for manage_tasks."""
        return {
            "query": "create a task to review Q4 budget by Friday",
            "user_timezone": "America/New_York",
            "current_date": "2024-01-15",
            "current_time": "14:30:00"
        }
    
    def test_manage_tasks_no_credentials(self, client, valid_request_data):
        """Should return needs_setup when no credentials provided."""
        response = client.post(
            "/mcp/tools/manage_tasks",
            json=valid_request_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["needs_setup"] is True
    
    def test_manage_tasks_create_success(self, client, valid_credentials, valid_request_data):
        """Should successfully create a task with credentials."""
        # The ManageTasksTool is already mocked in conftest.py
        # Just test that the endpoint works with credentials
        response = client.post(
            "/mcp/tools/manage_tasks",
            headers=valid_credentials,
            json=valid_request_data
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # With the current conftest.py mocking, we should get a successful response
        # The exact structure will depend on the mocked TaskAI response
        assert "success" in data or "action" in data
    
    def test_manage_tasks_invalid_json(self, client, valid_credentials):
        """Should handle invalid JSON gracefully."""
        response = client.post(
            "/mcp/tools/manage_tasks",
            headers=valid_credentials,
            data="invalid json",
            content_type="application/json"
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
    
    def test_manage_tasks_missing_query(self, client, valid_credentials):
        """Should return error for missing query parameter."""
        response = client.post(
            "/mcp/tools/manage_tasks",
            headers=valid_credentials,
            json={"user_timezone": "UTC"}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "query" in data["error"].lower()
    


class TestFindAndAnalyzeTasksIntegration:
    """Integration tests for find_and_analyze_tasks tool."""
    
    @patch('src.tools.find_and_analyze_tasks.TaskAI')
    @patch('src.tools.find_and_analyze_tasks.ReclaimClient')
    def test_find_and_analyze_tasks_success(self, mock_reclaim, mock_task_ai, client, valid_credentials):
        """Should successfully find and analyze tasks."""
        # Mock AI understanding
        mock_ai_instance = Mock()
        mock_task_ai.return_value = mock_ai_instance
        mock_ai_instance.understand_query.return_value = {
            "type": "find",
            "time_filter": "today"
        }
        
        # Mock Reclaim client and tasks
        mock_client = Mock()
        mock_reclaim.configure.return_value = mock_client
        mock_client.list.return_value = []  # Empty task list for simplicity
        
        response = client.post(
            "/mcp/tools/find_and_analyze_tasks",
            headers=valid_credentials,
            json={"query": "show me today's tasks"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "tasks" in data


class TestOptimizeScheduleIntegration:
    """Integration tests for optimize_schedule tool."""
    
    @patch('src.tools.optimize_schedule.TaskAI')
    @patch('src.tools.optimize_schedule.ReclaimClient')
    def test_optimize_schedule_success(self, mock_reclaim, mock_task_ai, client, valid_credentials):
        """Should successfully optimize schedule."""
        # Mock AI understanding
        mock_ai_instance = Mock()
        mock_task_ai.return_value = mock_ai_instance
        mock_ai_instance.understand_scheduling_request.return_value = {
            "type": "find_time",
            "duration": 2.0,
            "time_frame": "tomorrow"
        }
        
        # Mock Reclaim client and tasks
        mock_client = Mock()
        mock_reclaim.configure.return_value = mock_client
        mock_client.list.return_value = []  # Empty task list for simplicity
        
        response = client.post(
            "/mcp/tools/optimize_schedule",
            headers=valid_credentials,
            json={"request": "find 2 hours for deep work tomorrow"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True


class TestToolDiscoveryIntegration:
    """Integration tests for tool discovery."""
    
    def test_list_tools_includes_all_consolidated_tools(self, client, valid_credentials):
        """Should include all 3 consolidated tools when authenticated."""
        response = client.get(
            "/mcp/tools",
            headers=valid_credentials
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should have exactly 3 tools
        assert len(data["tools"]) == 3
        tool_names = [tool["name"] for tool in data["tools"]]
        
        # Verify all consolidated tools are present
        assert "manage_tasks" in tool_names
        assert "find_and_analyze_tasks" in tool_names
        assert "optimize_schedule" in tool_names
        
        # Verify schemas
        for tool in data["tools"]:
            assert "inputSchema" in tool
            assert "properties" in tool["inputSchema"]
            assert "required" in tool["inputSchema"]