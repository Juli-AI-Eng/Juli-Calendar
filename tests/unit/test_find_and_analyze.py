"""Tests for the hybrid find_and_analyze tool."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import pytz


class TestFindAndAnalyzeTool:
    """Test the hybrid find_and_analyze tool."""
    
    def test_tool_import(self):
        """Test that FindAndAnalyzeTool can be imported - RED phase."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            assert True
        except ImportError:
            pytest.fail("FindAndAnalyzeTool not found. Need to create src/tools/find_and_analyze.py")
    
    def test_tool_properties(self):
        """Test tool has correct name and description."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            tool = FindAndAnalyzeTool()
            
            assert tool.name == "find_and_analyze"
            assert "find" in tool.description.lower()
            assert "search" in tool.description.lower()
            assert "analyze" in tool.description.lower()
            assert "task" in tool.description.lower()
            assert "event" in tool.description.lower()
            
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    def test_get_schema(self):
        """Test tool schema includes all required fields."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            tool = FindAndAnalyzeTool()
            
            schema = tool.get_schema()
            
            # Check structure
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema
            
            # Check required fields
            properties = schema["properties"]
            assert "query" in properties
            assert "scope" in properties
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
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_execute_requires_both_credentials(self):
        """Test that tool requires both Reclaim and Nylas credentials."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            tool = FindAndAnalyzeTool()
            
            # Test with no credentials
            result = await tool.execute(
                {"query": "what's on my calendar today"}, 
                {}
            )
            assert result.get("needs_setup") is True
            assert "error" in result
            
            # Test with only Reclaim
            result = await tool.execute(
                {"query": "what's on my calendar today"}, 
                {"reclaim_api_key": "test_key"}
            )
            assert result.get("needs_setup") is True
            
            # Test with only Nylas
            result = await tool.execute(
                {"query": "what's on my calendar today"}, 
                {"nylas_api_key": "nyk_test", "nylas_grant_id": "grant_123"}
            )
            assert result.get("needs_setup") is True
            
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    @pytest.mark.asyncio
    @patch('src.tools.find_and_analyze.SearchAnalyzer')
    @patch('src.tools.find_and_analyze.ReclaimClient')
    @patch('src.tools.find_and_analyze.NylasClient')
    async def test_search_today_items(self, mock_nylas_class, mock_reclaim_class, mock_analyzer_class):
        """Test searching for today's items from both systems."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            
            # Mock search analyzer
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.analyze_search_query.return_value = {
                "intent": "view_schedule",
                "time_range": "today",
                "filters": {"date": "2024-01-15"},
                "search_both": True
            }
            
            # Create tool after mocking
            tool = FindAndAnalyzeTool()
            
            # Mock Reclaim client and Task.list
            mock_reclaim = Mock()
            mock_reclaim_class.configure.return_value = mock_reclaim
            with patch('reclaim_sdk.resources.task.Task') as mock_task_cls:
                mock_task = Mock()
                mock_task.id = 123
                mock_task.title = "Review Q4 budget"
                mock_task.due = datetime(2024, 1, 15, 14, 0, tzinfo=pytz.UTC)
                mock_task.status = Mock(value="NEW")
                mock_task.priority = "P3"
                mock_task.notes = ""
                mock_task_cls.list.return_value = [mock_task]

                # Mock Nylas client and events
                mock_nylas = Mock()
                mock_nylas_class.return_value = mock_nylas
                mock_event = Mock()
                # Shape expected by code: response.data -> list of event objects with .id/.title/.when
                mock_event.id = "event_456"
                mock_event.title = "Team standup"
                mock_event.when = Mock()
                mock_event.when.start_time = 1705334400  # 2024-01-15 10:00 UTC
                mock_event.when.end_time = 1705338000
                mock_event.participants = []
                mock_response = Mock()
                mock_response.data = [mock_event]
                mock_nylas.events.list.return_value = mock_response
            
            # Execute
                result = await tool.execute(
                    {
                        "query": "what's on my calendar today?",
                        "user_timezone": "America/New_York",
                        "current_date": "2024-01-15",
                        "current_time": "09:00:00"
                    },
                    {
                        "reclaim_api_key": "test_key",
                        "nylas_api_key": "nyk_test",
                        "nylas_grant_id": "grant_123"
                    }
                )
            
                # Verify
                assert result["success"] is True
                assert "tasks" in result["data"]
                assert "events" in result["data"]
                assert len(result["data"]["tasks"]) == 1
                assert len(result["data"]["events"]) == 1
                assert result["data"]["tasks"][0]["title"] == "Review Q4 budget"
                assert result["data"]["events"][0]["title"] == "Team standup"
            
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_workload_analysis(self):
        """Test workload analysis across both systems."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            
            with patch('src.tools.find_and_analyze.SearchAnalyzer') as mock_analyzer_class:
                # Mock search analyzer
                mock_analyzer = Mock()
                mock_analyzer_class.return_value = mock_analyzer
                mock_analyzer.analyze_search_query.return_value = {
                    "intent": "workload_analysis",
                    "time_range": "this_week",
                    "analysis_type": "workload"
                }
                
                # Create tool after mocking
                tool = FindAndAnalyzeTool()
                
                # Execute
                result = await tool.execute(
                    {"query": "how's my workload looking this week?"},
                    {
                        "reclaim_api_key": "test_key",
                        "nylas_api_key": "nyk_test",
                        "nylas_grant_id": "grant_123"
                    }
                )
                
                # Verify workload analysis was triggered
                assert result["success"] is True
                # Expect metrics and summary keys in analysis output
                assert "metrics" in result["data"]
                assert "summary" in result["data"]
                
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_natural_language_queries(self):
        """Test various natural language search queries."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            tool = FindAndAnalyzeTool()
            
            test_queries = [
                "what do I need to do today?",
                "show me overdue tasks",
                "find all meetings with Sarah",
                "what's high priority this week?",
                "am I free tomorrow at 2pm?",
                "how many hours of meetings do I have?"
            ]
            
            # This would test that natural language is properly understood
            # Implementation would use the AI components
            
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_cross_system_deduplication(self):
        """Test that duplicate items across systems are properly handled."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            tool = FindAndAnalyzeTool()
            
            # If a task in Reclaim has a corresponding event in Nylas,
            # they should be linked or deduplicated intelligently
            
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_empty_results_handling(self):
        """Test graceful handling of empty search results."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            tool = FindAndAnalyzeTool()
            
            with patch('src.tools.find_and_analyze.SearchAnalyzer') as mock_analyzer_class:
                with patch('src.tools.find_and_analyze.ReclaimClient') as mock_reclaim_class:
                    with patch('src.tools.find_and_analyze.NylasClient') as mock_nylas_class:
                        # Mock empty results
                        mock_reclaim = Mock()
                        mock_reclaim_class.configure.return_value = mock_reclaim
                        mock_reclaim.tasks.list.return_value = []
                        
                        mock_nylas = Mock()
                        mock_nylas_class.return_value = mock_nylas
                        mock_nylas.events.list.return_value = Mock(data=[])
                        
                        result = await tool.execute(
                            {"query": "show me tasks for next year"},
                            {
                                "reclaim_api_key": "test_key",
                                "nylas_api_key": "nyk_test",
                                "nylas_grant_id": "grant_123"
                            }
                        )
                        
                        assert result["success"] is True
                        assert result["data"]["tasks"] == []
                        assert result["data"]["events"] == []
                        assert "message" in result
                        assert "no items found" in result["message"].lower()
                        
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test graceful error handling."""
        try:
            from src.tools.find_and_analyze import FindAndAnalyzeTool
            tool = FindAndAnalyzeTool()
            
            # Test with invalid input
            result = await tool.execute(
                {},  # Missing required query
                {"reclaim_api_key": "test", "nylas_api_key": "test", "nylas_grant_id": "test"}
            )
            
            assert result["success"] is False
            assert "error" in result
            
        except ImportError:
            pytest.skip("FindAndAnalyzeTool not implemented yet")