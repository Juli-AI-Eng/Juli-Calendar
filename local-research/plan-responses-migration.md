Executing plan command with query: Migrate AI calls to OpenAI Responses API using GPT-5, replace any Chat Completions usage, maintain tool/function calling and JSON outputs, and ensure all e2e tests pass by updating mocks, settings, and retry policies. Outline concrete file edits, dependency changes, env vars, and test steps.Using file provider: gemini
Using file model: gemini-2.5-flash
Using thinking provider: gemini
Using thinking model: gemini-2.5-pro
Finding relevant files...
Running repomix to get file listing...
Found 112 files, approx 310982 tokens.
Asking gemini to identify relevant files using model: gemini-2.5-flash with max tokens: 64000...
Found 47 relevant files:
src/ai/availability_checker.py
src/ai/calendar_intelligence.py
src/ai/intent_router.py
src/ai/openai_utils.py
src/ai/schedule_optimizer.py
src/ai/search_analyzer.py
src/ai/semantic_search.py
src/ai/task_ai.py
src/server.py
src/tools/check_availability.py
src/tools/find_and_analyze.py
src/tools/find_and_analyze_tasks.py
src/tools/manage_productivity.py
src/tools/manage_tasks.py
src/tools/optimize_schedule.py
.claude/settings.local.json
docs/CLAUDE.md
docs/DEPLOYMENT.md
docs/FUNCTION_CALLING_OPENAI.md
juli-toolkit-config.json
requirements.txt
scripts/debug/test_ai_direct.py
scripts/debug/test_conflict_approval.py
scripts/debug/test_conflict_resolution.py
scripts/debug/test_duplicate.py
scripts/debug/test_semantic_search_debug.py
scripts/debug/test_simple_debug.py
scripts/run_server.py
tests/e2e/conftest.py
tests/e2e/test_ai_routing.py
tests/e2e/test_approval_flow_e2e.py
tests/e2e/test_check_availability_e2e.py
tests/e2e/test_conflict_resolution_e2e.py
tests/e2e/test_debug_ai_classification.py
tests/e2e/test_duplicate_detection_e2e.py
tests/e2e/test_find_and_analyze_e2e.py
tests/e2e/test_hybrid_workflows_e2e.py
tests/e2e/test_manage_productivity_e2e.py
tests/e2e/test_optimize_schedule_e2e.py
tests/e2e/utils/ai_grader.py
tests/unit/test_ai.py
tests/unit/test_check_availability.py
tests/unit/test_find_and_analyze.py
tests/unit/test_intent_router.py
tests/unit/test_manage_productivity.py
tests/unit/test_manage_tasks_tool.py
tests/unit/test_optimize_schedule.py

Extracting content from relevant files...
Generating plan using gemini with max tokens: 64000...

--- Implementation Plan ---
This plan outlines the migration of all OpenAI calls from the Chat Completions API to the new Responses API, using the `gpt-5` model. The migration will ensure that existing functionalities, especially tool calling and structured JSON outputs, are preserved.

## Phase 1: Core API Migration and Dependency Update

This phase focuses on updating the core AI utility functions to use the new `responses.create` endpoint and upgrading the OpenAI library.

**Relevant Files:**
*   `requirements.txt`
*   `src/ai/openai_utils.py`
*   `src/ai/availability_checker.py`
*   `src/ai/intent_router.py`
*   `src/ai/schedule_optimizer.py`
*   `src/ai/search_analyzer.py`
*   `src/ai/semantic_search.py`
*   `src/ai/task_ai.py`
*   `docs/DEPLOYMENT.md`

### Step 1.1: Update OpenAI Dependency

To ensure support for the `gpt-5` model and the Responses API, update the `openai` library version.

```diff:requirements.txt
- openai>=1.0.0
+ openai>=1.35.0 # Or latest version
```

### Step 1.2: Solidify the Responses API Helper

The `src/ai/openai_utils.py` module is the central point for AI interactions. We will enhance `call_function_tool` to be the sole interface for making tool calls with `gpt-5`, ensuring it correctly formats requests and parses responses from the `responses.create` endpoint.

The existing implementation in `src/ai/openai_utils.py` is a strong starting point. We will confirm its logic and add more robust logging. The key is to ensure it correctly handles the various output shapes from the Responses API. No major code changes are needed to the existing logic as it is already targeting the Responses API, but we will ensure it is used consistently.

### Step 1.3: Update AI Modules to Use `gpt-5`

Go through all AI modules and update the `model` parameter in every call to `call_function_tool` to use `"gpt-5"`.

**Example update in `src/ai/intent_router.py`:**

```python:src/ai/intent_router.py
            result = call_function_tool(
                client=self.client,
-               model="gpt-5", # Already gpt-5 in some files, ensure all are updated
+               model="gpt-5",
                system_text=system_text,
                user_text=user_text,
                tool_def=analyze_intent_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
```

Apply this change to the following files, ensuring any other model specified is replaced with `gpt-5`:
*   `src/ai/availability_checker.py`
*   `src/ai/schedule_optimizer.py`
*   `src/ai/search_analyzer.py`
*   `src/ai/semantic_search.py`
*   `src/ai/task_ai.py` (all calls)

### Step 1.4: Add New Environment Variables

The `openai_utils.py` helper supports new reasoning parameters. We should document these for developers and operators.

Update `docs/DEPLOYMENT.md` to include information on new optional environment variables. You should also add these to `.env.example` file.

```markdown:docs/DEPLOYMENT.md
...
#### Production `.env`:
```bash
# Server-level configuration
OPENAI_API_KEY=your_openai_api_key_here
PORT=5000
HOST=0.0.0.0
FLASK_ENV=production
DEBUG=false
SECRET_KEY=your_secret_key_here
LOG_LEVEL=INFO

# Optional: GPT-5 Responses API parameters
# Reasoning effort can be 'minimal', 'low', 'medium', 'high'
# OPENAI_REASONING_EFFORT_DEFAULT=low
# OPENAI_MAX_OUTPUT_TOKENS=2048
```
...
```

## Phase 2: Update Unit Tests and Mocks

This phase involves updating all unit tests that mock OpenAI API calls to reflect the switch from `chat.completions.create` to `responses.create`.

**Relevant Files:**
*   `tests/unit/test_ai.py`
*   `tests/unit/test_intent_router.py`

### Step 2.1: Update Mocks for `responses.create`

The response structure for `responses.create` is different from `chat.completions.create`. Mocks need to be updated to return a compatible structure that `call_function_tool` can parse.

**Example of an updated mock in `tests/unit/test_ai.py`:**

```python:tests/unit/test_ai.py
    def test_understand_create_task_simple(self, task_ai, user_context):
        """Should understand simple task creation requests."""
        query = "create a task to review the Q4 budget"
        
        # New mock structure for responses.create
        mock_response = MagicMock()
        mock_output = {
            "output": [{
                "type": "tool_call",
                "tool_call": {
                    "function": {
                        "arguments": json.dumps({
                            "intent": "create",
                            "task": {
                                "title": "Review the Q4 budget",
                                "priority": "P3"
                            }
                        })
                    }
                }
            }]
        }
        # Use model_dump() as the helper function does
        mock_response.model_dump.return_value = mock_output
        task_ai.client.responses.create.return_value = mock_response

        result = task_ai.understand_task_request(query, user_context)
        
        # Verify the call was made to the new endpoint
        task_ai.client.responses.create.assert_called_once()
        
        assert result["intent"] == "create"
        assert result["task"]["title"] == "Review the Q4 budget"
        assert result["task"]["priority"] is not None
```

Update all mocks in `tests/unit/test_ai.py` and `tests/unit/test_intent_router.py` to use `client.responses.create` and the new response format.

## Phase 3: Update E2E Tests and AI Grader

The E2E tests and the AI grader are crucial for validating the migration. The AI grader already uses the Responses API, so we just need to update the model.

**Relevant Files:**
*   `tests/e2e/utils/ai_grader.py`

### Step 3.1: Update AI Grader Model

The AI grader uses `gpt-5-mini`. For consistency and to test with the most capable model, we will update it to `gpt-5`. Note that this may increase cost and latency for grading; `gpt-5-mini` could be retained if this is a concern.

```python:tests/e2e/utils/ai_grader.py
    def grade_response(
        self,
        test_name: str,
        expected_behavior: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any]
    ) -> GradingResult:
        """Grade a test response using AI."""
        # Prepare the grading prompt
        prompt = self._build_grading_prompt(
            test_name, expected_behavior, request_data, response_data
        )
        try:
            # Call GPT-5 via Responses API (no Completions fallback)
            system_text = (
                "You are an expert, fair, and literal test grader for a productivity management system that integrates "
                "calendar events (Nylas) and tasks (Reclaim.ai). You understand approval flows, conflict detection, "
                "duplicate detection, and various response formats. Grade based on semantic correctness, not exact string "
                "matches. CRITICAL RULES: (1) Grade ONLY the behavior described in EXPECTED BEHAVIOR. The TEST NAME is just a label "
                "and must NOT cause you to require additional steps beyond EXPECTED BEHAVIOR. (2) If EXPECTED BEHAVIOR says 'after approval if needed', "
                "then BOTH of these are valid PASS outcomes: either a direct success (success=true, action done) with no needs_approval flag, OR a needs_approval=true response with appropriate action_type. "
                "(3) Warnings (e.g., 'This event involves other people') do NOT by themselves require approval; treat them as informational. "
                "(4) Approve or disapprove solely on whether the ACTUAL RESPONSE fulfills EXPECTED BEHAVIOR for THIS STEP."
            )
            resp = self.client.responses.create(
-               model="gpt-5-mini",
+               model="gpt-5",
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                ],
                # Some GPT-5 Responses models do not accept 'temperature'. Omit unless required.
                max_output_tokens=1000,
            )
```

### Step 3.2: Run and Validate E2E Tests

After the migration, run the full E2E test suite. The AI grader should handle minor semantic differences in `gpt-5`'s responses. Pay close attention to any failures and adjust the `expected_behavior` strings in the test files if `gpt-5`'s correct behavior differs slightly from `gpt-4.1`'s.

```bash
python3 -m pytest tests/e2e/
```

## Phase 4: Documentation Cleanup

Update all documentation to reflect the new model and API usage.

**Relevant Files:**
*   `docs/CLAUDE.md`
*   `docs/FUNCTION_CALLING_OPENAI.md`

### Step 4.1: Update Model Version in Documentation

Update the model version mentioned in `docs/CLAUDE.md`.

```diff:docs/CLAUDE.md
## Memories

-- **Always use gpt-4.1**
+- **Always use gpt-5**
```

### Step 4.2: Update Function Calling Documentation

The `FUNCTION_CALLING_OPENAI.md` file contains examples using `chat.completions.create`. Update these to use `responses.create` to reflect the new internal standard.

**Example update for `docs/FUNCTION_CALLING_OPENAI.md`:**

Replace Python examples like this:

```python
completion = client.chat.completions.create(
    model="gpt-4.1",
    messages=[{"role": "user", "content": "What is the weather like in Paris today?"}],
    tools=tools
)
```

With this new format:

```python
# Create structured input for the Responses API
messages = [
    {"role": "system", "content": [{"type": "input_text", "text": "You are a helpful assistant."}]},
    {"role": "user", "content": [{"type": "input_text", "text": "What is the weather like in Paris today?"}]}
]

# Use the Responses API
response = client.responses.create(
    model="gpt-5",
    input=messages,
    tools=tools,
    tool_choice={"type": "function", "name": "get_weather"} # Example of forcing a tool
)

# Parsing logic would be needed here to extract tool calls from response.output
```
Update all examples in `docs/FUNCTION_CALLING_OPENAI.md` to reflect the new API structure for consistency.

## Phase 5: Final Verification

After all code and test changes, perform a final verification to ensure the system is stable and correct.

1.  **Run All Tests**: Execute the entire test suite, including both unit and E2E tests, to confirm that all functionalities are working as expected and all tests pass.
    ```bash
    python3 -m pytest
    ```
2.  **Manual Debugging**: Run the debug scripts in `scripts/debug/` to manually check key user flows, such as conflict resolution and duplicate detection. This provides an extra layer of confidence.
    ```bash
    python3 scripts/debug/test_conflict_resolution.py
    python3 scripts/debug/test_duplicate.py
    ```
3.  **Code Review**: Conduct a final code review of all changed files to catch any potential issues and ensure adherence to codebase standards.

By following this plan, the migration to the OpenAI Responses API using `gpt-5` will be systematic, verifiable, and robust, ensuring the application continues to function correctly with enhanced AI capabilities.
--- End Plan ---
