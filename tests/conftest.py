"""Test configuration and fixtures."""
import pytest
import sys
import os

# Add parent directory to path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, Mock
import json

# Check if we're running E2E tests by looking at the test path
is_e2e_test = any('e2e' in arg for arg in sys.argv) or 'E2E' in os.environ.get('PYTEST_CURRENT_TEST', '')

# Set dummy OpenAI API key for unit tests ONLY if not already set
# E2E tests need the real key from .env.test
if not os.environ.get("OPENAI_API_KEY") and not is_e2e_test:
    os.environ["OPENAI_API_KEY"] = "test-key-12345"

# Only patch OpenAI for unit tests, not E2E tests
if not is_e2e_test:
    # Create a mock OpenAI client that supports Responses API
    mock_openai_patcher = patch('openai.OpenAI')
    mock_openai = mock_openai_patcher.start()
    mock_openai_instance = Mock()
    mock_openai.return_value = mock_openai_instance

    # Mock responses.create to return a default tool_call output
    mock_responses = Mock()
    mock_openai_instance.responses = mock_responses
    mock_create = Mock()
    mock_responses.create = mock_create
    # Default: create-task shape matching GPT-5 function_call format
    default_output = {
        "output": [
            {
                "type": "function_call",
                "name": "analyze_intent",
                "arguments": json.dumps({
                    "intent": "create",
                    "task": {
                        "title": "Test Task",
                        "priority": "P3",
                        "duration_hours": 1.0
                    }
                })
            }
        ]
    }
    mock_response_obj = Mock()
    mock_response_obj.model_dump.return_value = default_output
    mock_create.return_value = mock_response_obj

from src.server import create_app


@pytest.fixture
def app():
    """Create and configure a test Flask app."""
    # Patch ReclaimClient in all the places it's imported
    with patch('reclaim_sdk.client.ReclaimClient') as mock_reclaim_sdk, \
         patch('src.tools.manage_tasks.ReclaimClient') as mock_reclaim_tool, \
         patch('src.tools.find_and_analyze_tasks.ReclaimClient') as mock_reclaim_find, \
         patch('src.tools.optimize_schedule.ReclaimClient') as mock_reclaim_schedule:
        
        # Set up mock ReclaimClient for all patches
        for mock_reclaim in [mock_reclaim_sdk, mock_reclaim_tool, mock_reclaim_find, mock_reclaim_schedule]:
            mock_client_instance = Mock()
            mock_reclaim.configure.return_value = mock_client_instance
            
            # Mock tasks attribute
            mock_tasks = Mock()
            mock_client_instance.tasks = mock_tasks
            
            # Mock task creation
            mock_task = Mock(
                id="test_task_123",
                title="Test Task",
                priority="P3",
                duration=1.0,
                due=None
            )
            mock_tasks.create.return_value = mock_task
            
            # Mock users attribute for setup tool
            mock_users = Mock()
            mock_client_instance.users = mock_users
            mock_current_user = Mock()
            mock_users.current.return_value = mock_current_user
        
        app = create_app()
        app.config.update({
            "TESTING": True,
        })
        yield app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def valid_credentials():
    """Valid test credentials."""
    return {
        "X-User-Credential-RECLAIM_API_KEY": "test_api_key_12345"
    }


@pytest.fixture
def context_headers():
    """Context injection headers."""
    return {
        "user_timezone": "America/New_York",
        "current_date": "2024-01-15",
        "current_time": "14:30:00"
    }