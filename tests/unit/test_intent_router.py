"""Tests for IntentRouter - AI-powered routing between providers."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import pytz


class TestIntentRouter:
    """Test the IntentRouter for intelligent routing decisions."""
    
    def test_intent_router_import(self):
        """Test that IntentRouter can be imported - RED phase."""
        try:
            from src.ai.intent_router import IntentRouter
            assert True
        except ImportError:
            pytest.fail("IntentRouter not found. Need to create src/ai/intent_router.py")
    
    @patch('src.ai.openai_utils.call_function_tool')
    @patch('src.ai.intent_router.OpenAI')
    def test_analyze_task_queries(self, mock_openai_class, mock_call_tool):
        """Test routing task-related queries to Reclaim."""
        try:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client

            # Mock Responses helper return for task queries
            mock_call_tool.return_value = {
                "provider": "reclaim",
                "intent_type": "task",
                "confidence": 0.85,
                "reasoning": "This is a task management request",
                "involves_others": False,
                "extracted_time": {"has_specific_time": False},
                "warning": None,
                "safety_mode": False,
                "approval_required": False,
            }
            
            from src.ai.intent_router import IntentRouter
            router = IntentRouter()
            
            task_queries = [
                "create a task to review the budget",
                "mark my presentation task as complete",
                "I need 2 hours for deep work on the proposal",
                "schedule time to work on the report",
                "add a todo for calling the client"
            ]
            
            for query in task_queries:
                result = router.analyze_intent(query)
                assert result['provider'] == 'reclaim'
                assert result['intent_type'] == 'task'
                assert 'confidence' in result
                assert result['confidence'] > 0.7
                
        except ImportError:
            pytest.skip("IntentRouter not implemented yet")
    
    @patch('src.ai.openai_utils.call_function_tool')
    @patch('src.ai.intent_router.OpenAI')
    def test_analyze_calendar_queries(self, mock_openai_class, mock_call_tool):
        """Test routing calendar event queries to Nylas."""
        try:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client

            # Mock Responses helper return for calendar queries
            mock_call_tool.return_value = {
                "provider": "nylas",
                "intent_type": "calendar",
                "confidence": 0.9,
                "reasoning": "This is a calendar event request",
                "involves_others": False,
                "extracted_time": {"has_specific_time": True},
                "warning": None,
                "safety_mode": False,
                "approval_required": False,
            }
            
            from src.ai.intent_router import IntentRouter
            router = IntentRouter()
            
            calendar_queries = [
                "am I free at 3pm tomorrow?",
                "schedule a meeting with John at 2pm",
                "add a doctor appointment on Friday at 10am",
                "what's on my calendar today?",
                "block my calendar from 1-2pm for lunch"
            ]
            
            for query in calendar_queries:
                result = router.analyze_intent(query)
                assert result['provider'] == 'nylas'
                assert result['intent_type'] == 'calendar'
                assert result['confidence'] > 0.7
                
        except ImportError:
            pytest.skip("IntentRouter not implemented yet")
    
    @patch('src.ai.openai_utils.call_function_tool')
    @patch('src.ai.intent_router.OpenAI')
    def test_analyze_mixed_queries(self, mock_openai_class, mock_call_tool):
        """Test handling ambiguous queries that could be either."""
        try:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client

            # Mock Responses helper return for ambiguous query
            mock_call_tool.return_value = {
                "provider": "reclaim",
                "intent_type": "task",
                "confidence": 0.7,
                "reasoning": "Schedule the client review appears to be about time-blocking for task work",
                "involves_others": False,
                "extracted_time": {"has_specific_time": False},
                "warning": None,
                "safety_mode": False,
                "approval_required": False,
            }
            
            from src.ai.intent_router import IntentRouter
            router = IntentRouter()
            
            # "Schedule" could mean task time-blocking OR calendar event
            result = router.analyze_intent("schedule the client review")
            assert result['provider'] in ['reclaim', 'nylas']
            assert 'reasoning' in result
            assert 'confidence' in result
            
        except ImportError:
            pytest.skip("IntentRouter not implemented yet")
    
    @patch('src.ai.openai_utils.call_function_tool')
    @patch('src.ai.intent_router.OpenAI')
    def test_extract_time_context(self, mock_openai_class, mock_call_tool):
        """Test extracting time-related information from queries."""
        try:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client

            # Two sequential mocked returns for two calls
            mock_call_tool.side_effect = [
                {
                    "provider": "nylas",
                    "intent_type": "calendar",
                    "confidence": 0.95,
                    "reasoning": "Specific time mentioned for a meeting",
                    "involves_others": False,
                    "extracted_time": {"has_specific_time": True, "duration_minutes": 60},
                    "warning": None,
                    "safety_mode": False,
                    "approval_required": False,
                },
                {
                    "provider": "reclaim",
                    "intent_type": "task",
                    "confidence": 0.9,
                    "reasoning": "Task with duration specified",
                    "involves_others": False,
                    "extracted_time": {"has_specific_time": False, "duration_minutes": 120},
                    "warning": None,
                    "safety_mode": False,
                    "approval_required": False,
                },
            ]
            
            from src.ai.intent_router import IntentRouter
            router = IntentRouter()
            
            user_context = {
                'timezone': 'America/New_York',
                'current_date': '2024-01-15',
                'current_time': '14:30:00',
                'now': datetime(2024, 1, 15, 14, 30, tzinfo=pytz.timezone('America/New_York'))
            }
            
            # Test specific time extraction
            result = router.analyze_intent("meeting at 3pm tomorrow", user_context)
            assert 'extracted_time' in result
            assert result['extracted_time']['has_specific_time'] is True
            
            # Test duration extraction
            result = router.analyze_intent("I need 2 hours for the report", user_context)
            assert 'extracted_time' in result
            assert result['extracted_time']['duration_minutes'] == 120
            
        except ImportError:
            pytest.skip("IntentRouter not implemented yet")
    
    @patch('src.ai.openai_utils.call_function_tool')
    @patch('src.ai.intent_router.OpenAI')
    def test_handle_people_mentions(self, mock_openai_class, mock_call_tool):
        """Test detecting when other people are involved."""
        try:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client

            mock_call_tool.side_effect = [
                {
                    "provider": "nylas",
                    "intent_type": "calendar",
                    "confidence": 0.95,
                    "reasoning": "Meeting with Sarah and Tom requires calendar coordination",
                    "involves_others": True,
                    "extracted_time": {"has_specific_time": False},
                    "warning": "This involves other people. Please be careful about rescheduling.",
                    "safety_mode": True,
                    "approval_required": True,
                },
                {
                    "provider": "reclaim",
                    "intent_type": "task",
                    "confidence": 0.9,
                    "reasoning": "Personal task for presentation work",
                    "involves_others": False,
                    "extracted_time": {"has_specific_time": False},
                    "warning": None,
                    "safety_mode": False,
                    "approval_required": False,
                },
            ]
            
            from src.ai.intent_router import IntentRouter
            router = IntentRouter()
            
            # Events with others should go to Nylas
            result = router.analyze_intent("schedule a meeting with Sarah and Tom")
            assert result['provider'] == 'nylas'
            assert result['involves_others'] is True
            assert 'warning' in result  # Should warn about coordinating with others
            
            # Solo tasks should go to Reclaim
            result = router.analyze_intent("schedule time to work on my presentation")
            assert result['provider'] == 'reclaim'
            assert result['involves_others'] is False
            
        except ImportError:
            pytest.skip("IntentRouter not implemented yet")
    
    @patch('src.ai.openai_utils.call_function_tool')
    @patch('src.ai.intent_router.OpenAI')
    def test_openai_integration(self, mock_openai_class, mock_call_tool):
        """Test that router uses OpenAI for complex intent analysis."""
        try:
            # Mock OpenAI client instance
            mock_client = Mock()
            mock_openai_class.return_value = mock_client

            # Mock Responses helper
            mock_call_tool.return_value = {
                "provider": "nylas",
                "intent_type": "calendar",
                "confidence": 0.9,
                "reasoning": "User wants to check availability, which is a calendar query",
                "involves_others": False,
                "extracted_time": {"has_specific_time": False},
                "warning": None,
                "safety_mode": False,
                "approval_required": False,
            }

            # Import and create router after mocking
            from src.ai.intent_router import IntentRouter
            router = IntentRouter()
            result = router.analyze_intent("am I free Thursday afternoon?")
            
            # Verify helper was called
            mock_call_tool.assert_called_once()
            
            # Verify result parsing
            assert result['provider'] == 'nylas'
            assert result['intent_type'] == 'calendar'
            assert result['confidence'] == 0.9
            
        except ImportError:
            pytest.skip("IntentRouter not implemented yet")
    
    @patch('src.ai.openai_utils.call_function_tool')
    @patch('src.ai.intent_router.OpenAI')
    def test_safe_mode_for_external_events(self, mock_openai_class, mock_call_tool):
        """Test that events with others trigger safety warnings."""
        try:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai_class.return_value = mock_client
            
            # Mock Responses helper for team meeting
            mock_call_tool.return_value = {
                "provider": "nylas",
                "intent_type": "calendar",
                "confidence": 0.95,
                "reasoning": "Team meeting involves multiple people and requires coordination",
                "involves_others": True,
                "extracted_time": {"has_specific_time": True, "specific_time": "4pm"},
                "warning": "Rescheduling a team meeting affects multiple people. Please ensure all attendees are notified.",
                "safety_mode": True,
                "approval_required": True
            }
            
            from src.ai.intent_router import IntentRouter
            router = IntentRouter()
            
            result = router.analyze_intent("reschedule the team meeting to 4pm")
            assert result['provider'] == 'nylas'
            assert result['involves_others'] is True
            assert 'safety_mode' in result
            assert result['safety_mode'] is True
            assert 'approval_required' in result
            
        except ImportError:
            pytest.skip("IntentRouter not implemented yet")