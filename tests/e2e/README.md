# End-to-End Tests

These tests use real Reclaim.ai and Nylas APIs to verify the hybrid MCP server works correctly with actual services.

## Setup

1. **Copy the environment file:**
   ```bash
   cp .env.test.example .env.test
   ```

2. **Add your real API credentials to `.env.test`:**
   - `RECLAIM_API_KEY`: Your Reclaim.ai API key
   - `NYLAS_API_KEY`: Your Nylas API key
   - `NYLAS_GRANT_ID`: Your Nylas grant ID
   - `TEST_USER_TIMEZONE`: Your timezone (default: America/New_York)

3. **Install dependencies:**
   ```bash
   pip install python-dotenv
   ```

## Running the Tests

### Run all E2E tests:
```bash
pytest tests/e2e -v -m e2e
```

### Run specific test file:
```bash
pytest tests/e2e/test_manage_productivity_e2e.py -v
```

### Run with HTTP logging enabled:
```bash
E2E_LOGGING_ENABLED=true pytest tests/e2e -v
```

### Run a single test:
```bash
pytest tests/e2e/test_manage_productivity_e2e.py::TestManageProductivityE2E::test_create_reclaim_task -v
```

## HTTP Logging

When `E2E_LOGGING_ENABLED=true`, the tests will log all HTTP requests and responses to `tests/e2e/e2e_http.log`.

The log format is minimal:
```
=== REQUEST ===
POST /mcp/tools/manage_productivity
Headers: {
  "X-User-Credential-RECLAIM_API_KEY": "***",
  "X-User-Credential-NYLAS_API_KEY": "***",
  "Content-Type": "application/json"
}
Body: {
  "query": "create a task to review Q4 budget",
  "user_timezone": "America/New_York"
}

=== RESPONSE ===
Status: 200
Body: {
  "success": true,
  "provider": "reclaim",
  "data": {...}
}
```

## Test Data Safety

- Tests track all created items for automatic cleanup
- Cleanup happens after each test automatically
- If tests fail, manual cleanup may be needed

## Test Coverage

### Individual Tool Tests:
- `test_manage_productivity_e2e.py` - Create, update, complete tasks/events
- `test_find_and_analyze_e2e.py` - Search and analyze across both systems
- `test_check_availability_e2e.py` - Check availability and find time slots
- `test_optimize_schedule_e2e.py` - Schedule optimization suggestions

### Hybrid Workflow Tests:
- `test_hybrid_workflows_e2e.py` - Multi-tool workflows that mirror real usage

## Troubleshooting

### Server not starting:
- Tests use port 5001 to avoid conflicts with macOS AirPlay Receiver (port 5000)
- Check if port 5001 is already in use
- Verify Flask is installed: `pip install flask`
- Check server logs for errors

### Authentication failures:
- Verify API keys in `.env.test` are correct
- Check that Nylas grant ID is valid
- Ensure API keys have necessary permissions

### Test data not cleaned up:
- Check your Reclaim/Nylas accounts for test items
- Delete them manually if needed
- Tests use best-effort cleanup

## Performance

Tests run efficiently without artificial delays:
- Fast execution using modern API limits
- No unnecessary waiting between operations  
- Tests complete quickly for rapid development