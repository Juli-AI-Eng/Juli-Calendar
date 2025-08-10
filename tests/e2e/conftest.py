"""Configuration for E2E tests."""
import pytest
import os
from typing import Dict, Any, List
import subprocess
import time
import requests
from dotenv import load_dotenv

from tests.e2e.utils.juli_client import JuliClient, create_test_context
from tests.e2e.utils.http_logger import HTTPLogger
from tests.e2e.utils.timing import TestTimer, TimingContext


# Load test environment variables
load_dotenv(".env.test")


def find_python_executable():
    """Find the available Python executable (python3 or python)."""
    import shutil
    
    # Try python3 first (preferred)
    if shutil.which("python3"):
        return "python3"
    
    # Fall back to python
    if shutil.which("python"):
        return "python"
    
    # If neither found, default to python3 and let it fail with a clear error
    return "python3"


@pytest.fixture(scope="session")
def test_credentials() -> Dict[str, str]:
    """Get test credentials from environment."""
    openai_key = os.getenv("OPENAI_API_KEY")
    reclaim_key = os.getenv("RECLAIM_API_KEY")
    nylas_key = os.getenv("NYLAS_API_KEY")
    nylas_grant = os.getenv("NYLAS_GRANT_ID")
    
    missing_keys = []
    if not openai_key:
        missing_keys.append("OPENAI_API_KEY")
    if not reclaim_key:
        missing_keys.append("RECLAIM_API_KEY")
    if not nylas_key:
        missing_keys.append("NYLAS_API_KEY")
    if not nylas_grant:
        missing_keys.append("NYLAS_GRANT_ID")
    
    if missing_keys:
        pytest.skip(f"E2E tests require these keys in .env.test: {', '.join(missing_keys)}")
    
    credentials = {
        "openai_api_key": openai_key,
        "reclaim_api_key": reclaim_key,
        "nylas_api_key": nylas_key,
        "nylas_grant_id": nylas_grant
    }
    
    print(f"[DEBUG] Loaded credentials from .env.test: {list(credentials.keys())}")
    print(f"[DEBUG] Reclaim key loaded: {bool(reclaim_key)} - {reclaim_key[:10] if reclaim_key else 'NONE'}...")
    
    return credentials


@pytest.fixture(scope="function")  # Changed from "session" to fix caching issues
def server_url() -> str:
    """Get the server URL for testing."""
    # Use Docker container URL if specified
    return os.getenv("TEST_SERVER_URL", "http://localhost:5001")


@pytest.fixture(scope="session")
def http_logger() -> HTTPLogger:
    """Create HTTP logger for the test session."""
    # Create timestamped log file for this session
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/e2e_session_{timestamp}.log"
    return HTTPLogger(log_file=log_file)


@pytest.fixture(scope="function")  # Changed from "session" to fix caching issues
def server_process(server_url: str):
    """Start the Flask server for testing."""
    # Skip if using Docker container
    if "mcp-server" in server_url or os.getenv("USE_DOCKER"):
        # Using Docker, no need to start local process
        # Wait for Docker container to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{server_url}/health", timeout=1)
                if response.status_code == 200:
                    yield None
                    return
            except:
                pass
            time.sleep(1)
        pytest.fail("Docker container failed to become healthy")
    
    # Extract port from server_url
    import urllib.parse
    parsed_url = urllib.parse.urlparse(server_url)
    port = parsed_url.port or 5001
    
    # Kill any existing server to ensure fresh start
    subprocess.run(["pkill", "-f", f"flask.*{port}"], capture_output=True)
    time.sleep(1)
    
    # Start server
    env = os.environ.copy()
    env["FLASK_APP"] = "src.server:create_app"
    env["FLASK_ENV"] = "testing"
    
    # Ensure OpenAI API key is available for server startup
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        env["OPENAI_API_KEY"] = openai_key
    
    # Use the detected Python executable
    python_cmd = find_python_executable()
    
    # Use separate entry point for E2E to avoid any mocking
    process = subprocess.Popen(
        [python_cmd, "scripts/run_server.py", "--mode", "e2e", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{server_url}/health", timeout=1)
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(1)
    else:
        # Get server error output for debugging
        stdout, stderr = process.communicate(timeout=5)
        process.terminate()
        error_msg = f"Server failed to start within 30 seconds.\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
        pytest.fail(error_msg)
    
    yield process
    
    # Cleanup
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture
def test_logger(request) -> HTTPLogger:
    """Create a per-test HTTP logger."""
    # Get test name and clean it for filename
    test_name = request.node.name.replace("[", "_").replace("]", "_").replace("::", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # Create logs directory structure
    log_dir = "logs/e2e"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = f"{log_dir}/{test_name}_{timestamp}.log"
    return HTTPLogger(log_file=log_file)


@pytest.fixture
def test_timer(request) -> TestTimer:
    """Create a per-test timer."""
    # Get test name
    test_name = request.node.name.replace("[", "_").replace("]", "_").replace("::", "_")
    timer = TestTimer(test_name)
    
    # Start timing the entire test
    timer.start("test_total")
    
    yield timer
    
    # End timing and save report
    timer.end("test_total")
    timer.save()
    
    # Print summary to console
    print(f"\n[TIMING SUMMARY] {test_name}:")
    for operation, duration in sorted(timer.timings.items(), key=lambda x: x[1], reverse=True):
        print(f"  {operation}: {duration:.2f}s")


@pytest.fixture
def juli_client(
    server_url: str, 
    test_credentials: Dict[str, str], 
    test_logger: HTTPLogger,
    test_timer: TestTimer,
    server_process
) -> JuliClient:
    """Create a Juli client for testing."""
    return JuliClient(
        base_url=server_url,
        credentials=test_credentials,
        logger=test_logger,
        timer=test_timer
    )


@pytest.fixture
def test_context() -> Dict[str, Any]:
    """Create a test context with user timezone."""
    timezone = os.getenv("TEST_USER_TIMEZONE", "America/New_York")
    return create_test_context(timezone)


# Track created items for cleanup
class TestDataTracker:
    """Track test data for cleanup."""
    
    def __init__(self):
        self.reclaim_tasks: List[int] = []
        self.nylas_events: List[str] = []
    
    def add_task(self, task_id: int):
        """Track a Reclaim task for cleanup."""
        self.reclaim_tasks.append(task_id)
    
    def add_event(self, event_id: str):
        """Track a Nylas event for cleanup."""
        self.nylas_events.append(event_id)
    
    def cleanup(self, juli_client: JuliClient, context: Dict[str, Any]):
        """Clean up all tracked test data."""
        # Clean up Reclaim tasks
        for task_id in self.reclaim_tasks:
            try:
                # Try to delete the task
                response = juli_client.execute_tool(
                    "manage_productivity",
                    {
                        "query": f"delete task with id {task_id}",
                        "context": f"Task ID: {task_id}"
                    },
                    context
                )
                
                # If approval is required, send the approved action
                if response.status_code == 200:
                    data = response.json()
                    if data.get("needs_approval") and data.get("action_data"):
                        juli_client.execute_tool(
                            "manage_productivity",
                            {
                                "approved": True,
                                "action_data": data["action_data"]
                            },
                            context
                        )
            except:
                pass  # Best effort cleanup
        
        # Clean up Nylas events
        for event_id in self.nylas_events:
            try:
                # Try to cancel the event
                response = juli_client.execute_tool(
                    "manage_productivity",
                    {
                        "query": f"cancel event with id {event_id}",
                        "context": f"Event ID: {event_id}"
                    },
                    context
                )
                
                # If approval is required, send the approved action
                if response.status_code == 200:
                    data = response.json()
                    if data.get("needs_approval") and data.get("action_data"):
                        juli_client.execute_tool(
                            "manage_productivity",
                            {
                                "approved": True,
                                "action_data": data["action_data"]
                            },
                            context
                        )
            except:
                pass  # Best effort cleanup
        
        # Clear lists
        self.reclaim_tasks.clear()
        self.nylas_events.clear()


@pytest.fixture(scope="session")
def test_data_tracker():
    """Create a test data tracker for cleanup."""
    return TestDataTracker()


@pytest.fixture(scope="class", autouse=True)
def cleanup_before_class():
    """Automatically clean up test data before each test class."""
    # Run cleanup scripts before each test class to ensure clean state
    python_cmd = find_python_executable()
    
    print("\n🧹 Running pre-test cleanup...")
    
    # Clean up Nylas events
    try:
        result = subprocess.run(
            [python_cmd, "scripts/clear_nylas_events.py"],
            input="yes\n",
            text=True,
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            print("   ✅ Nylas events cleaned")
        else:
            print(f"   ⚠️  Nylas cleanup failed: {result.stderr}")
    except Exception as e:
        print(f"   ⚠️  Nylas cleanup error: {e}")
    
    # Clean up Reclaim tasks
    try:
        result = subprocess.run(
            [python_cmd, "scripts/clear_reclaim_tasks.py"],
            input="yes\n",
            text=True,
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            print("   ✅ Reclaim tasks cleaned")
        else:
            print(f"   ⚠️  Reclaim cleanup failed: {result.stderr}")
    except Exception as e:
        print(f"   ⚠️  Reclaim cleanup error: {e}")
    
    yield


@pytest.fixture(autouse=True)
def cleanup_test_data(test_data_tracker: TestDataTracker, juli_client: JuliClient, test_context: Dict[str, Any], test_logger: HTTPLogger):
    """Automatically clean up test data after each test."""
    yield
    
    # Check if cleanup should be skipped
    skip_cleanup = os.getenv("E2E_SKIP_CLEANUP", "false").lower() == "true"
    
    if skip_cleanup:
        print("\n⚠️  CLEANUP SKIPPED - Test data was NOT deleted")
        if test_data_tracker.reclaim_tasks:
            print(f"   - Reclaim tasks created: {test_data_tracker.reclaim_tasks}")
        if test_data_tracker.nylas_events:
            print(f"   - Nylas events created: {test_data_tracker.nylas_events}")
        print("   To clean up manually, run: python3 scripts/run_e2e_tests.py and choose 'clean'")
        return
    
    # Log cleanup actions
    if test_data_tracker.reclaim_tasks or test_data_tracker.nylas_events:
        test_logger.log_request("CLEANUP", "Test Data Cleanup", {}, {
            "reclaim_tasks": test_data_tracker.reclaim_tasks,
            "nylas_events": test_data_tracker.nylas_events
        })
    test_data_tracker.cleanup(juli_client, test_context)


# Pytest markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )