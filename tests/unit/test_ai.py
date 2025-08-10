"""Tests for AI task understanding and natural language processing."""
import pytest
import json
from datetime import datetime
from freezegun import freeze_time
from unittest.mock import Mock, patch, MagicMock
from src.ai.task_ai import TaskAI
from src.ai.date_parser import DateParser


class TestTaskAI:
    """Tests for natural language task understanding."""
    
    @pytest.fixture
    def task_ai(self):
        """Create a TaskAI instance with mocked OpenAI."""
        with patch('src.ai.task_ai.OpenAI') as mock_openai:
            # Mock the OpenAI client
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            # Create TaskAI with a dummy API key
            task_ai = TaskAI(openai_api_key="test-key")
            task_ai.client = mock_client
            
            return task_ai
    
    @pytest.fixture
    def user_context(self):
        """User context with timezone information."""
        return {
            "timezone": "America/New_York",
            "current_date": "2024-01-15",
            "current_time": "14:30:00",
            "now": datetime(2024, 1, 15, 14, 30, 0)
        }
    
    @patch('src.ai.openai_utils.call_function_tool')
    def test_understand_create_task_simple(self, mock_call_tool, task_ai, user_context):
        """Should understand simple task creation requests."""
        query = "create a task to review the Q4 budget"
        
        # Mock Responses helper return
        mock_call_tool.return_value = {
            "intent": "create",
            "task": {
                "title": "Review the Q4 budget",
                "priority": "P3"
            }
        }
        
        result = task_ai.understand_task_request(query, user_context)
        
        assert result["intent"] == "create"
        assert result["task"]["title"] == "Review the Q4 budget"
        assert result["task"]["priority"] is not None
        
    @patch('src.ai.openai_utils.call_function_tool')
    def test_understand_create_task_with_deadline(self, mock_call_tool, task_ai, user_context):
        """Should understand task creation with deadline."""
        query = "create a task to finish the report by Friday"
        
        # Mock Responses helper return
        mock_call_tool.return_value = {
            "intent": "create",
            "task": {
                "title": "Finish the report",
                "due_date": "2024-01-19T17:00:00",
                "priority": "P3"
            }
        }
        
        result = task_ai.understand_task_request(query, user_context)
        
        assert result["intent"] == "create"
        assert result["task"]["title"] == "Finish the report"
        assert result["task"]["due"] is not None
        # Friday should be Jan 19, 2024 (current date is Jan 15, 2024 Monday)
        assert result["task"]["due"].date() == datetime(2024, 1, 19).date()
        
    @patch('src.ai.openai_utils.call_function_tool')
    def test_understand_create_task_with_duration(self, mock_call_tool, task_ai, user_context):
        """Should understand task creation with duration."""
        query = "create a 2 hour task to review code"
        
        mock_call_tool.return_value = {
            "intent": "create",
            "task": {
                "title": "Review code",
                "duration_hours": 2.0,
                "priority": "P3"
            }
        }
        
        result = task_ai.understand_task_request(query, user_context)
        
        assert result["intent"] == "create"
        assert result["task"]["title"] == "Review code"
        assert result["task"]["duration"] == 2.0
        
    @patch('src.ai.openai_utils.call_function_tool')
    def test_understand_update_task(self, mock_call_tool, task_ai, user_context):
        """Should understand task update requests."""
        query = "push the client presentation to next week"
        
        mock_call_tool.return_value = {
            "intent": "update",
            "task_reference": "client presentation",
            "updates": {
                "due": "2024-01-22T09:00:00"
            }
        }
        
        result = task_ai.understand_task_request(query, user_context)
        
        assert result["intent"] == "update"
        assert result["task_reference"] == "client presentation"
        assert result["updates"]["due"] is not None
        
    @patch('src.ai.openai_utils.call_function_tool')
    def test_understand_complete_task(self, mock_call_tool, task_ai, user_context):
        """Should understand task completion requests."""
        query = "mark the budget review as complete"
        
        mock_call_tool.return_value = {
            "intent": "complete",
            "task_reference": "budget review"
        }
        
        result = task_ai.understand_task_request(query, user_context)
        
        assert result["intent"] == "complete"
        assert result["task_reference"] == "budget review"
        
    @patch('src.ai.openai_utils.call_function_tool')
    def test_understand_add_time_to_task(self, mock_call_tool, task_ai, user_context):
        """Should understand adding time to tasks."""
        query = "add 30 minutes to the design task"
        
        mock_call_tool.return_value = {
            "intent": "add_time",
            "task_reference": "design task",
            "time_to_add": 0.5
        }
        
        result = task_ai.understand_task_request(query, user_context)
        
        assert result["intent"] == "add_time"
        assert result["task_reference"] == "design task"
        assert result["time_to_add"] == 0.5  # 30 minutes = 0.5 hours
        
    @patch('src.ai.openai_utils.call_function_tool')
    def test_infer_priority_from_tone(self, mock_call_tool, task_ai, user_context):
        """Should infer priority from tone and keywords."""
        urgent_queries = [
            ("urgent: create task to fix the bug", "P1"),
            ("create a task to fix the critical issue ASAP", "P1"),
            ("need to review security patch immediately", "P2")
        ]
        
        for query, expected_priority in urgent_queries:
            mock_call_tool.return_value = {
                "intent": "create",
                "task": {
                    "title": query.replace("urgent: ", "").replace("create task to", "").strip(),
                    "priority": expected_priority
                }
            }
            
            result = task_ai.understand_task_request(query, user_context)
            assert result["task"]["priority"] in ["P1", "P2"], f"Failed for: {query}"
            
        normal_queries = [
            ("create a task to update documentation", "P3"),
            ("when you get a chance, review the proposal", "P4")
        ]
        
        for query, expected_priority in normal_queries:
            mock_call_tool.return_value = {
                "intent": "create",
                "task": {
                    "title": query.replace("create a task to", "").strip(),
                    "priority": expected_priority
                }
            }
            
            result = task_ai.understand_task_request(query, user_context)
            assert result["task"]["priority"] in ["P3", "P4"], f"Failed for: {query}"


class TestDateParser:
    """Tests for timezone-aware date parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create a DateParser instance."""
        return DateParser()
    
    @pytest.fixture
    def context(self):
        """User context for EST timezone on Monday, Jan 15, 2024, 2:30 PM."""
        return {
            "timezone": "America/New_York",
            "current_date": "2024-01-15",
            "current_time": "14:30:00",
            "now": datetime(2024, 1, 15, 14, 30, 0)
        }
    
    @freeze_time("2024-01-15 14:30:00")
    def test_parse_relative_days(self, parser, context):
        """Should parse relative day references correctly."""
        # Today
        result = parser.parse_date("today", context)
        assert result.date() == datetime(2024, 1, 15).date()
        
        # Tomorrow
        result = parser.parse_date("tomorrow", context)
        assert result.date() == datetime(2024, 1, 16).date()
        
        # Day after tomorrow
        result = parser.parse_date("day after tomorrow", context)
        assert result.date() == datetime(2024, 1, 17).date()
        
    @freeze_time("2024-01-15 14:30:00")  # Monday
    def test_parse_weekdays(self, parser, context):
        """Should parse weekday references correctly."""
        # This Friday (Jan 19)
        result = parser.parse_date("Friday", context)
        assert result.date() == datetime(2024, 1, 19).date()
        
        # Next Monday (Jan 22)
        result = parser.parse_date("next Monday", context)
        assert result.date() == datetime(2024, 1, 22).date()
        
        # Next week (defaults to Monday)
        result = parser.parse_date("next week", context)
        assert result.date() == datetime(2024, 1, 22).date()
        
    @freeze_time("2024-01-15 14:30:00")
    def test_parse_time_of_day(self, parser, context):
        """Should parse time of day references."""
        # Tomorrow morning (9 AM)
        result = parser.parse_date("tomorrow morning", context)
        assert result.date() == datetime(2024, 1, 16).date()
        assert result.hour == 9
        
        # Friday afternoon (2 PM)
        result = parser.parse_date("Friday afternoon", context)
        assert result.date() == datetime(2024, 1, 19).date()
        assert result.hour == 14
        
        # End of day today (5 PM)
        result = parser.parse_date("end of day", context)
        assert result.date() == datetime(2024, 1, 15).date()
        assert result.hour == 17
        
    @freeze_time("2024-01-15 14:30:00")
    def test_parse_relative_time_periods(self, parser, context):
        """Should parse relative time periods."""
        # In 2 hours
        result = parser.parse_date("in 2 hours", context)
        assert result.replace(tzinfo=None) == datetime(2024, 1, 15, 16, 30, 0)
        
        # In 30 minutes
        result = parser.parse_date("in 30 minutes", context)
        assert result.replace(tzinfo=None) == datetime(2024, 1, 15, 15, 0, 0)
        
    def test_parse_with_timezone_awareness(self, parser, context):
        """Should respect user's timezone for all operations."""
        # When user says "9 AM", it means 9 AM in their timezone
        result = parser.parse_date("tomorrow at 9 AM", context)
        assert result.hour == 9
        # Result should be timezone-aware
        assert result.strftime("%Z") != ""  # Has timezone info
        
    def test_handle_ambiguous_dates(self, parser, context):
        """Should handle ambiguous date references gracefully."""
        # "Soon" defaults to end of today
        result = parser.parse_date("soon", context)
        assert result is not None
        
        # Invalid date returns None
        result = parser.parse_date("someday maybe", context)
        assert result is None