"""Unit tests for manage_tasks tool."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
import pytz


class TestManageTasksTool:
    """Unit tests for ManageTasksTool."""
    
    @pytest.fixture
    def tool(self):
        """Create a ManageTasksTool instance with mocked dependencies."""
        with patch('src.tools.manage_tasks.TaskAI') as mock_task_ai:
            # Mock the TaskAI instance
            mock_ai_instance = Mock()
            mock_task_ai.return_value = mock_ai_instance
            
            # Import after patching TaskAI
            from src.tools.manage_tasks import ManageTasksTool
            
            # Now patch ReclaimClient at the module level
            with patch('src.tools.manage_tasks.ReclaimClient') as mock_reclaim_client:
                tool = ManageTasksTool()
                # Set the mocked TaskAI instance
                tool.task_ai = mock_ai_instance
                # Store the mock for tests to use
                tool.mock_reclaim_client = mock_reclaim_client
                
                yield tool
    
    @pytest.fixture
    def valid_input(self):
        """Valid input data."""
        return {
            "query": "create a task to review the budget",
            "user_timezone": "America/New_York",
            "current_date": "2024-01-15",
            "current_time": "14:30:00"
        }
    
    @pytest.fixture
    def credentials(self):
        """Valid credentials."""
        return {
            "RECLAIM_API_KEY": "test_api_key"
        }
    
    def test_get_schema(self, tool):
        """Should return proper tool schema."""
        schema = tool.get_schema()
        
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["properties"]["query"]["type"] == "string"
        assert "user_timezone" in schema["properties"]
    
    def test_validate_input_valid(self, tool, valid_input):
        """Should validate valid input."""
        result = tool.validate_input(valid_input)
        
        assert result["query"] == valid_input["query"]
        assert result["user_timezone"] == valid_input["user_timezone"]
        assert result["task_context"] == ""  # Default value
    
    def test_validate_input_missing_query(self, tool):
        """Should raise error for missing query."""
        with pytest.raises(ValueError, match="Query is required"):
            tool.validate_input({})
    
    def test_validate_input_defaults(self, tool):
        """Should provide defaults for missing context fields."""
        result = tool.validate_input({"query": "test"})
        
        assert result["query"] == "test"
        assert result["user_timezone"] == "UTC"
        assert result["task_context"] == ""
        # Date and time should be today's date/time
        assert result["current_date"] is not None
        assert result["current_time"] is not None
    
    def test_parse_user_datetime(self, tool, valid_input):
        """Should parse user datetime correctly."""
        dt = tool._parse_user_datetime(valid_input)
        
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.tzinfo.zone == "America/New_York"
    
    def test_parse_user_datetime_invalid(self, tool):
        """Should return UTC now for invalid datetime."""
        dt = tool._parse_user_datetime({
            "user_timezone": "invalid/timezone",
            "current_date": "invalid",
            "current_time": "invalid"
        })
        
        # Should return a datetime (UTC now)
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None
    
    @pytest.mark.asyncio
    async def test_execute_no_api_key(self, tool, valid_input):
        """Should return error when no API key provided."""
        result = await tool.execute(valid_input, {})
        
        assert result["error"] == "Reclaim API key not found"
        assert result["needs_setup"] is True
    
    @pytest.mark.asyncio
    async def test_execute_create_task(self, tool, valid_input, credentials):
        """Should execute create task intent."""
        # Validate input to add defaults
        validated_input = tool.validate_input(valid_input)
        
        # Setup the mocked TaskAI on the existing tool
        tool.task_ai.understand_task_request.return_value = {
            "intent": "create",
            "task": {
                "title": "Review the budget",
                "priority": "P3",
                "duration": 2.0
            }
        }
        
        # Mock the _create_task method directly
        expected_result = {
            "success": True,
            "action": "created",
            "task": {
                "id": "task_123",
                "title": "Review the budget",
                "due": None,
                "priority": "P3",
                "duration": 2.0
            },
            "message": "Created task: Review the budget"
        }
        
        with patch.object(tool, '_create_task', return_value=expected_result) as mock_create:
            # Execute with validated input
            result = await tool.execute(validated_input, credentials)
        
        # Verify
        assert result["success"] is True
        assert result["action"] == "created"
        assert result["task"]["title"] == "Review the budget"
        assert result["message"] == "Created task: Review the budget"
        
        # Verify _create_task was called with correct arguments
        mock_create.assert_called_once()
        call_args = mock_create.call_args[0]
        assert call_args[0]["intent"] == "create"
        assert call_args[0]["task"]["title"] == "Review the budget"
    
    @pytest.mark.asyncio
    async def test_execute_unknown_intent(self, tool, valid_input, credentials):
        """Should handle unknown intent."""
        # Setup the mocked TaskAI on the existing tool
        tool.task_ai.understand_task_request.return_value = {
            "intent": "unknown_intent"
        }
        
        result = await tool.execute(valid_input, credentials)
        
        assert result["error"] == "Unknown intent: unknown_intent"
        assert "understanding" in result
    
    @pytest.mark.asyncio
    @patch('src.tools.manage_tasks.Task')
    @patch('src.tools.manage_tasks.ReclaimClient')
    async def test_execute_update_task(self, mock_reclaim_class, mock_task_class, tool, valid_input, credentials):
        """Should execute update task intent."""
        # Setup the mocked TaskAI on the existing tool
        tool.task_ai.understand_task_request.return_value = {
            "intent": "update",
            "task_reference": "budget review",
            "updates": {"due": "2024-01-20"}
        }
        
        # Mock Reclaim client
        mock_client = Mock()
        mock_reclaim_class.configure.return_value = mock_client
        
        # Mock task - make sure title contains "budget review"
        mock_task = Mock()
        mock_task.id = 123
        mock_task.title = "Budget review for Q4"  # Contains "budget review"
        mock_task.status = "NEW"
        mock_task.priority = "P2"
        mock_task.duration = 2.0
        mock_task.due = None
        mock_task.save = Mock()
        
        # Mock Task.list to return our mock task
        mock_task_class.list.return_value = [mock_task]
        
        result = await tool.execute(valid_input, credentials)
        
        assert result["success"] is True
        assert result["action"] == "updated"
        assert result["task"]["title"] == "Budget review for Q4"
        mock_task.save.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.tools.manage_tasks.Task')
    @patch('src.tools.manage_tasks.ReclaimClient')
    async def test_execute_complete_task(self, mock_reclaim_class, mock_task_class, tool, valid_input, credentials):
        """Should execute complete task intent."""
        # Setup the mocked TaskAI on the existing tool
        tool.task_ai.understand_task_request.return_value = {
            "intent": "complete",
            "task_reference": "budget review"
        }
        
        # Mock Reclaim client
        mock_client = Mock()
        mock_reclaim_class.configure.return_value = mock_client
        
        # Mock task - make sure title contains "budget review"
        mock_task = Mock()
        mock_task.id = 123
        mock_task.title = "Budget review for Q4"  # Contains "budget review"
        mock_task.status = "NEW"
        mock_task.finished = None
        mock_task.mark_complete = Mock()
        
        # Mock Task.list to return our mock task
        mock_task_class.list.return_value = [mock_task]
        
        valid_input["query"] = "mark the budget review as complete"
        result = await tool.execute(valid_input, credentials)
        
        assert result["success"] is True
        assert result["action"] == "completed"
        assert result["task"]["title"] == "Budget review for Q4"
        mock_task.mark_complete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_handles_exceptions(self, tool, valid_input, credentials):
        """Should handle exceptions gracefully."""
        # Setup the mocked TaskAI to raise exception
        tool.task_ai.understand_task_request.side_effect = Exception("AI error")
        
        result = await tool.execute(valid_input, credentials)
        
        assert result["success"] is False
        assert "AI error" in result["error"]