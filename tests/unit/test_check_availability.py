"""Tests for the hybrid check_availability tool."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import pytz


class TestCheckAvailabilityTool:
    """Test the hybrid check_availability tool."""
    
    def test_tool_import(self):
        """Test that CheckAvailabilityTool can be imported - RED phase."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            assert True
        except ImportError:
            pytest.fail("CheckAvailabilityTool not found. Need to create src/tools/check_availability.py")
    
    def test_tool_properties(self):
        """Test tool has correct name and description."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            tool = CheckAvailabilityTool()
            
            assert tool.name == "check_availability"
            assert "availability" in tool.description.lower()
            assert "free" in tool.description.lower()
            assert "time" in tool.description.lower()
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    def test_get_schema(self):
        """Test tool schema includes all required fields."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            tool = CheckAvailabilityTool()
            
            schema = tool.get_schema()
            
            # Check structure
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema
            
            # Check required fields
            properties = schema["properties"]
            assert "query" in properties
            assert "duration_minutes" in properties
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
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_execute_requires_both_credentials(self):
        """Test that tool requires both Reclaim and Nylas credentials."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            tool = CheckAvailabilityTool()
            
            # Test with no credentials
            result = await tool.execute(
                {"query": "am I free tomorrow at 2pm?"}, 
                {}
            )
            assert result.get("needs_setup") is True
            assert "error" in result
            
            # Test with only Reclaim
            result = await tool.execute(
                {"query": "am I free tomorrow at 2pm?"}, 
                {"reclaim_api_key": "test_key"}
            )
            assert result.get("needs_setup") is True
            
            # Test with only Nylas
            result = await tool.execute(
                {"query": "am I free tomorrow at 2pm?"}, 
                {"nylas_api_key": "nyk_test", "nylas_grant_id": "grant_123"}
            )
            assert result.get("needs_setup") is True
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    @pytest.mark.asyncio
    @patch('src.tools.check_availability.AvailabilityChecker')
    @patch('src.tools.check_availability.ReclaimClient')
    @patch('src.tools.check_availability.NylasClient')
    async def test_check_specific_time(self, mock_nylas_class, mock_reclaim_class, mock_checker_class):
        """Test checking availability at a specific time."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            
            # Mock availability checker
            mock_checker = Mock()
            mock_checker_class.return_value = mock_checker
            mock_checker.analyze_availability_query.return_value = {
                "type": "specific_time",
                "datetime": datetime(2024, 1, 16, 14, 0, tzinfo=pytz.timezone("America/New_York")),
                "duration_minutes": 60
            }
            
            # Create tool after mocking
            tool = CheckAvailabilityTool()
            
            # Mock clients
            mock_reclaim = Mock()
            mock_reclaim_class.configure.return_value = mock_reclaim
            mock_reclaim.tasks.list.return_value = []  # No conflicting tasks
            
            mock_nylas = Mock()
            mock_nylas_class.return_value = mock_nylas
            mock_nylas.events.list.return_value = Mock(data=[])  # No conflicting events
            
            # Execute
            result = await tool.execute(
                {
                    "query": "am I free tomorrow at 2pm?",
                    "user_timezone": "America/New_York",
                    "current_date": "2024-01-15",
                    "current_time": "10:00:00"
                },
                {
                    "reclaim_api_key": "test_key",
                    "nylas_api_key": "nyk_test",
                    "nylas_grant_id": "grant_123"
                }
            )
            
            # Verify
            assert result["success"] is True
            assert result["available"] is True
            assert "conflicts" in result
            assert len(result["conflicts"]) == 0
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    @pytest.mark.asyncio
    @patch('src.tools.check_availability.AvailabilityChecker')
    @patch('src.tools.check_availability.ReclaimClient')
    @patch('src.tools.check_availability.NylasClient')
    async def test_find_time_slots(self, mock_nylas_class, mock_reclaim_class, mock_checker_class):
        """Test finding available time slots."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            
            # Mock availability checker
            mock_checker = Mock()
            mock_checker_class.return_value = mock_checker
            mock_checker.analyze_availability_query.return_value = {
                "type": "find_slots",
                "duration_minutes": 120,  # 2 hours
                "time_range": "this_week",
                "preferences": ["morning"]
            }
            
            # Create tool after mocking
            tool = CheckAvailabilityTool()
            
            # Mock clients (would return busy times)
            mock_reclaim = Mock()
            mock_reclaim_class.configure.return_value = mock_reclaim
            
            mock_nylas = Mock()
            mock_nylas_class.return_value = mock_nylas
            
            # Execute
            result = await tool.execute(
                {
                    "query": "find 2 hours for deep work this week, preferably mornings",
                    "user_timezone": "America/New_York",
                    "current_date": "2024-01-15",
                    "current_time": "10:00:00"
                },
                {
                    "reclaim_api_key": "test_key",
                    "nylas_api_key": "nyk_test",
                    "nylas_grant_id": "grant_123"
                }
            )
            
            # Verify
            assert result["success"] is True
            assert "slots" in result
            # Should return available time slots
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self):
        """Test detecting conflicts with existing items."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            tool = CheckAvailabilityTool()
            
            # Test scenario where there's a conflict
            # Would have a task/event at the requested time
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_natural_language_time_parsing(self):
        """Test parsing various natural language time expressions."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            tool = CheckAvailabilityTool()
            
            test_queries = [
                "am I free at 2pm?",
                "do I have time tomorrow morning?",
                "find 30 minutes this afternoon",
                "when can I schedule a 1-hour meeting?",
                "check my availability next Tuesday"
            ]
            
            # This would test that natural language is properly understood
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_working_hours_respect(self):
        """Test that availability respects working hours."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            tool = CheckAvailabilityTool()
            
            # Should not suggest times outside working hours
            # unless specifically requested
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test graceful error handling."""
        try:
            from src.tools.check_availability import CheckAvailabilityTool
            tool = CheckAvailabilityTool()
            
            # Test with invalid input
            result = await tool.execute(
                {},  # Missing required query
                {"reclaim_api_key": "test", "nylas_api_key": "test", "nylas_grant_id": "test"}
            )
            
            assert result["success"] is False
            assert "error" in result
            
        except ImportError:
            pytest.skip("CheckAvailabilityTool not implemented yet")