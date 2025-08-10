"""Common test helpers for E2E tests."""
import pytest
import inspect
from typing import Dict, Any, Optional
from .ai_grader import ai_grade_response


def get_current_test_name() -> str:
    """Get the name of the currently running test."""
    # Walk up the stack to find the test function
    for frame_info in inspect.stack():
        if frame_info.function.startswith("test_"):
            return frame_info.function
    return "unknown_test"


def assert_response_fulfills_expectation(
    data: Dict[str, Any],
    expected_behavior: str,
    request_data: Optional[Dict[str, Any]] = None
):
    """Use AI grader to validate response meets expected behavior."""
    # Check for setup first
    if data.get("needs_setup"):
        pytest.fail(f"Tool requires setup: {data.get('message', 'Missing credentials')}")
    
    # Don't auto-fail on errors - let the AI grader evaluate if the error is appropriate
    # Some errors (like ambiguity detection) are actually correct behavior
    
    # Use AI grader
    result = ai_grade_response(
        test_name=get_current_test_name(),
        expected_behavior=expected_behavior,
        request_data=request_data or {},
        response_data=data
    )
    
    if not result.passed:
        pytest.fail(f"AI Grading Failed:\n{result.reasoning}")


def assert_success_response(data):
    """Helper to assert a successful response with proper error handling.
    
    DEPRECATED: Use assert_response_fulfills_expectation instead for better flexibility.
    """
    # Check if setup is needed first
    if data.get("needs_setup"):
        pytest.fail(f"Tool requires setup: {data.get('message', 'Missing credentials')}")
    
    # Check for error
    if data.get("error"):
        pytest.fail(f"Tool returned error: {data['error']}")
    
    # Now we can safely check success
    assert data.get("success") is True, f"Expected success=True, got: {data}"


def assert_approval_needed(data):
    """Helper to assert that approval is needed."""
    assert data.get("needs_approval") is True, f"Expected needs_approval=True, got: {data}"
    assert "action_data" in data, "Missing action_data in approval response"
    assert "action_type" in data, "Missing action_type in approval response"