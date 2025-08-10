"""Tests for the hybrid optimize_schedule tool."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import pytz


class TestOptimizeScheduleTool:
    """Test the hybrid optimize_schedule tool."""
    
    def test_tool_import(self):
        """Test that OptimizeScheduleTool can be imported - RED phase."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            assert True
        except ImportError:
            pytest.fail("OptimizeScheduleTool not found. Need to create src/tools/optimize_schedule.py")
    
    def test_tool_properties(self):
        """Test tool has correct name and description."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            assert tool.name == "optimize_schedule"
            assert "optimize" in tool.description.lower()
            assert "schedule" in tool.description.lower()
            assert "balance" in tool.description.lower() or "productivity" in tool.description.lower()
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    def test_get_schema(self):
        """Test tool schema includes all required fields."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            schema = tool.get_schema()
            
            # Check structure
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema
            
            # Check required fields
            properties = schema["properties"]
            assert "request" in properties
            assert "preferences" in properties
            assert "user_timezone" in properties
            assert "current_date" in properties
            assert "current_time" in properties
            
            # Check context injection markers
            assert properties["user_timezone"].get("x-context-injection") == "user_timezone"
            assert properties["current_date"].get("x-context-injection") == "current_date"
            assert properties["current_time"].get("x-context-injection") == "current_time"
            
            # Check request is required
            assert "request" in schema["required"]
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_execute_requires_both_credentials(self):
        """Test that tool requires both Reclaim and Nylas credentials."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            # Test with no credentials
            result = await tool.execute(
                {"request": "optimize my schedule for better focus time"}, 
                {}
            )
            assert result.get("needs_setup") is True
            assert "error" in result
            
            # Test with only Reclaim
            result = await tool.execute(
                {"request": "optimize my schedule for better focus time"}, 
                {"reclaim_api_key": "test_key"}
            )
            assert result.get("needs_setup") is True
            
            # Test with only Nylas
            result = await tool.execute(
                {"request": "optimize my schedule for better focus time"}, 
                {"nylas_api_key": "nyk_test", "nylas_grant_id": "grant_123"}
            )
            assert result.get("needs_setup") is True
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    @patch('src.tools.optimize_schedule.ScheduleOptimizer')
    @patch('src.tools.optimize_schedule.ReclaimClient')
    @patch('src.tools.optimize_schedule.NylasClient')
    async def test_optimize_for_focus_time(self, mock_nylas_class, mock_reclaim_class, mock_optimizer_class):
        """Test optimizing schedule for focus time."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            
            # Mock schedule optimizer
            mock_optimizer = Mock()
            mock_optimizer_class.return_value = mock_optimizer
            mock_optimizer.analyze_optimization_request.return_value = {
                "optimization_type": "focus_time",
                "goals": ["maximize_deep_work", "minimize_context_switching"],
                "time_range": "this_week"
            }
            
            # Create tool after mocking
            tool = OptimizeScheduleTool()
            
            # Mock optimization suggestions
            mock_optimizer.generate_optimization_plan.return_value = {
                "suggestions": [
                    {
                        "type": "block_time",
                        "action": "Create 2-hour deep work blocks in mornings",
                        "impact": "high",
                        "reasoning": "Your most productive hours are 9-11am"
                    },
                    {
                        "type": "batch_meetings",
                        "action": "Group meetings on Tuesday/Thursday afternoons",
                        "impact": "medium",
                        "reasoning": "Reduces context switching"
                    }
                ],
                "metrics": {
                    "current_focus_hours": 8,
                    "potential_focus_hours": 16,
                    "improvement": "100%"
                }
            }
            
            # Execute
            result = await tool.execute(
                {
                    "request": "optimize my schedule for better focus time",
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
            assert "suggestions" in result
            assert len(result["suggestions"]) == 2
            assert "metrics" in result
            assert result["metrics"]["improvement"] == "100%"
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_balance_workload_optimization(self):
        """Test optimizing for balanced workload."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            # Test scenario where workload is unbalanced
            # Should suggest redistribution of tasks
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_energy_based_optimization(self):
        """Test optimizing based on energy levels."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            # Test optimizing schedule based on energy patterns
            # High-energy tasks in morning, low-energy in afternoon
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_priority_based_optimization(self):
        """Test optimizing to prioritize important tasks."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            # Test ensuring high-priority items get best time slots
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_approval_for_major_changes(self):
        """Test that major schedule changes require approval."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            with patch('src.tools.optimize_schedule.ScheduleOptimizer') as mock_optimizer_class:
                mock_optimizer = Mock()
                mock_optimizer_class.return_value = mock_optimizer
                
                # Return suggestions that would significantly change schedule
                mock_optimizer.generate_optimization_plan.return_value = {
                    "suggestions": [
                        {
                            "type": "reschedule_meetings",
                            "action": "Move 5 meetings to different days",
                            "impact": "high",
                            "affects_others": True
                        }
                    ],
                    "requires_approval": True
                }
                
                # Create tool after mocking
                tool = OptimizeScheduleTool()
                
                result = await tool.execute(
                    {"request": "completely reorganize my schedule"},
                    {
                        "reclaim_api_key": "test_key",
                        "nylas_api_key": "nyk_test",
                        "nylas_grant_id": "grant_123"
                    }
                )
                
                assert result.get("needs_approval") is True
                assert "preview" in result
                
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_natural_language_optimization_requests(self):
        """Test various natural language optimization requests."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            test_requests = [
                "make my schedule less chaotic",
                "I need more time for deep work",
                "balance my workload better",
                "optimize for my energy levels",
                "prioritize urgent tasks first",
                "reduce meeting overload"
            ]
            
            # This would test that natural language is properly understood
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test graceful error handling."""
        try:
            from src.tools.optimize_schedule import OptimizeScheduleTool
            tool = OptimizeScheduleTool()
            
            # Test with invalid input
            result = await tool.execute(
                {},  # Missing required request
                {"reclaim_api_key": "test", "nylas_api_key": "test", "nylas_grant_id": "test"}
            )
            
            assert result["success"] is False
            assert "error" in result
            
        except ImportError:
            pytest.skip("OptimizeScheduleTool not implemented yet")