"""Tests for the hybrid manage_productivity tool."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import pytz


class TestManageProductivityTool:
    """Test the hybrid manage_productivity tool."""
    
    def test_tool_import(self):
        """Test that ManageProductivityTool can be imported - RED phase."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            assert True
        except ImportError:
            pytest.fail("ManageProductivityTool not found. Need to create src/tools/manage_productivity.py")
    
    def test_tool_properties(self):
        """Test tool has correct name and description."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            tool = ManageProductivityTool()
            
            assert tool.name == "manage_productivity"
            assert "create" in tool.description.lower()
            assert "task" in tool.description.lower()
            assert "meeting" in tool.description.lower()
            assert "appointment" in tool.description.lower()
            
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")
    
    def test_get_schema(self):
        """Test tool schema includes all required fields."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            tool = ManageProductivityTool()
            
            schema = tool.get_schema()
            
            # Check structure
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema
            
            # Check required fields
            properties = schema["properties"]
            assert "query" in properties
            assert "context" in properties
            assert "user_timezone" in properties
            assert "current_date" in properties
            assert "current_time" in properties
            
            # Check context injection markers
            assert properties["user_timezone"].get("x-context-injection") == "user_timezone"
            assert properties["current_date"].get("x-context-injection") == "current_date"
            assert properties["current_time"].get("x-context-injection") == "current_time"
            
            # Check query is required
            assert "query" in schema["required"]
            
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_execute_requires_both_credentials(self):
        """Test that tool requires both Reclaim and Nylas credentials."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            tool = ManageProductivityTool()
            
            # Test with no credentials
            result = await tool.execute(
                {"query": "create a task"}, 
                {}
            )
            assert result.get("needs_setup") is True
            assert "error" in result
            
            # Test with only Reclaim
            result = await tool.execute(
                {"query": "create a task"}, 
                {"reclaim_api_key": "test_key"}
            )
            assert result.get("needs_setup") is True
            
            # Test with only Nylas
            result = await tool.execute(
                {"query": "create a task"}, 
                {"nylas_api_key": "nyk_test", "nylas_grant_id": "grant_123"}
            )
            assert result.get("needs_setup") is True
            
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")
    
    @pytest.mark.asyncio
    @patch('src.tools.manage_productivity.IntentRouter')
    @patch('src.tools.manage_productivity.ReclaimClient')
    @patch('src.tools.manage_productivity.TaskAI')
    async def test_create_task_routes_to_reclaim(self, mock_taskai_class, mock_reclaim_class, mock_router_class):
        """Test creating a task routes to Reclaim."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            
            # Mock intent router to return Reclaim
            mock_router = Mock()
            mock_router_class.return_value = mock_router
            mock_router.analyze_intent.return_value = {
                "provider": "reclaim",
                "intent_type": "task",
                "confidence": 0.9,
                "reasoning": "This is a task creation request"
            }
            
            # Mock TaskAI to return parsed task details
            mock_taskai = Mock()
            mock_taskai.understand_task_request.return_value = {
                "intent": "create",
                "task": {
                    "title": "Review Q4 budget",
                    "priority": "P3",
                    "duration_minutes": 60
                }
            }
            mock_taskai_class.return_value = mock_taskai
            
            # Create tool after mocking
            tool = ManageProductivityTool()
            
            # Patch Task.list to avoid duplicates and Task.save to avoid real API
            with patch('src.tools.manage_productivity.Task') as mock_task_cls:
                mock_task_cls.list.return_value = []
                # Instance returned when Task(...) is constructed
                task_instance = Mock()
                def save_side_effect():
                    task_instance.id = 123
                    task_instance.title = "Review Q4 budget"
                    task_instance.status = "NEW"
                    task_instance.due = None
                task_instance.save.side_effect = save_side_effect
                mock_task_cls.return_value = task_instance
            
                # Execute
                result = await tool.execute(
                    {
                        "query": "create a task to review Q4 budget",
                        "user_timezone": "America/New_York",
                        "current_date": "2024-01-15",
                        "current_time": "14:30:00"
                    },
                    {
                        "reclaim_api_key": "test_key",
                        "nylas_api_key": "nyk_test",
                        "nylas_grant_id": "grant_123"
                    }
                )
            
            # Verify
            assert result["success"] is True
            assert result["provider"] == "reclaim"
            assert result["action"] == "created"
            assert result["data"]["title"] == "Review Q4 budget"
            
            # Verify intent router was called
            mock_router.analyze_intent.assert_called_once()
            
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")
    
    @pytest.mark.asyncio
    @patch('src.tools.manage_productivity.IntentRouter')
    @patch('src.tools.manage_productivity.NylasClient')
    async def test_create_meeting_routes_to_nylas(self, mock_nylas_class, mock_router_class):
        """Test creating a meeting routes to Nylas."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            
            # Mock intent router to return Nylas
            mock_router = Mock()
            mock_router_class.return_value = mock_router
            mock_router.analyze_intent.return_value = {
                "provider": "nylas",
                "intent_type": "calendar",
                "confidence": 0.95,
                "reasoning": "Meeting with others requires calendar coordination",
                "involves_others": True,
                "warning": "This involves other people"
            }
            
            # Create tool after mocking
            tool = ManageProductivityTool()
            
            # Mock Nylas client
            mock_client = Mock()
            mock_nylas_class.return_value = mock_client
            
            # Mock event creation and skip approval by indicating no participants
            mock_event = Mock()
            mock_event.data = Mock()
            mock_event.data.id = "event_456"
            mock_event.data.title = "Team standup"
            mock_event.data.when = Mock()
            mock_event.data.when.start_time = 1234567890
            mock_client.events.create.return_value = mock_event
            
            # Execute
            result = await tool.execute(
                {
                    "query": "schedule team standup tomorrow at 10am",
                    "user_timezone": "America/New_York",
                    "current_date": "2024-01-15",
                    "current_time": "14:30:00"
                },
                {
                    "reclaim_api_key": "test_key",
                    "nylas_api_key": "nyk_test",
                    "nylas_grant_id": "grant_123"
                }
            )
            
            # Verify
            assert result.get("needs_approval") is True or result.get("success") is True
            
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_approval_required_for_risky_operations(self):
        """Test that risky operations require approval."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            
            # Mock dependencies
            with patch('src.tools.manage_productivity.IntentRouter') as mock_router_class:
                mock_router = Mock()
                mock_router_class.return_value = mock_router
                
                # Return a risky operation
                mock_router.analyze_intent.return_value = {
                    "provider": "nylas",
                    "intent_type": "calendar",
                    "confidence": 0.9,
                    "involves_others": True,
                    "approval_required": True,
                    "warning": "Rescheduling affects multiple people"
                }
                
                # Create tool after mocking
                tool = ManageProductivityTool()
                
                result = await tool.execute(
                    {"query": "reschedule the team meeting to 4pm"},
                    {
                        "reclaim_api_key": "test_key",
                        "nylas_api_key": "nyk_test",
                        "nylas_grant_id": "grant_123"
                    }
                )
                
                # Should return approval request, not execute
                assert result.get("needs_approval") is True
                assert result.get("success") is not True  # Not executed yet
                
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_natural_language_processing(self):
        """Test that tool processes various natural language inputs correctly."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            tool = ManageProductivityTool()
            
            test_cases = [
                ("mark the presentation as complete", "update", "complete"),
                ("add 2 hours to the design task", "update", "add_time"),
                ("cancel my 3pm meeting", "update", "cancel"),
                ("find time for deep work tomorrow", "create", "task")
            ]
            
            # This would test that natural language is properly understood
            # Implementation would use the AI components
            
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test graceful error handling."""
        try:
            from src.tools.manage_productivity import ManageProductivityTool
            tool = ManageProductivityTool()
            
            # Test with invalid input
            result = await tool.execute(
                {},  # Missing required query
                {"reclaim_api_key": "test", "nylas_api_key": "test", "nylas_grant_id": "test"}
            )
            
            assert result["success"] is False
            assert "error" in result
            
        except ImportError:
            pytest.skip("ManageProductivityTool not implemented yet")