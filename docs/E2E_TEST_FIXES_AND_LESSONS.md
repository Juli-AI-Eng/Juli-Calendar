# E2E Test Fixes and Lessons Learned

## Overview
This document describes the fixes applied to make all E2E tests pass after migrating from OpenAI Chat Completions to the GPT-5 Responses API, and important lessons learned about the codebase architecture.

## Major Issues Fixed

### 1. AI Grader Not Getting Text Responses (Critical)
**Problem**: The AI grader was returning empty responses with 0% confidence because GPT-5 was only returning reasoning tokens without actual text output.

**Root Cause**: The new GPT-5 Responses API defaults to reasoning-only output unless explicitly told to produce text.

**Fix**: Modified `tests/e2e/utils/ai_grader.py` to force text output:
```python
resp = self.client.responses.create(
    model="gpt-5",
    reasoning={"effort": "low"},  # Minimize reasoning to force text output
    text={"format": {"type": "text"}, "verbosity": "high"}  # Force verbose text
)
```

**Lesson**: When using GPT-5 Responses API, always explicitly request text output with the `text` parameter.

### 2. Flask Server Hanging During Tests
**Problem**: E2E tests would hang indefinitely, especially when running the full suite.

**Root Cause**: Running Flask with `debug=True` enables the auto-reloader, which causes issues in test environments. Additionally, using `asyncio.new_event_loop()` in threaded Flask caused deadlocks.

**Fixes**:
1. Disabled debug mode for E2E tests in `scripts/run_server.py`:
```python
if args.mode == "e2e":
    debug = False  # Prevent Flask reloader issues
```

2. Changed from `asyncio.new_event_loop()` to `asyncio.run()` in `src/server.py`:
```python
# OLD (causes hangs):
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
result = loop.run_until_complete(tool.execute(data, credentials))

# NEW (fixed):
result = asyncio.run(tool.execute(data, credentials))
```

**Lesson**: Never run Flask in debug mode during automated testing. Use `asyncio.run()` for one-off async operations in sync contexts.

### 3. Time Parsing Issues ("this afternoon" returning morning slots)
**Problem**: Queries like "this afternoon" were returning morning time slots.

**Root Cause**: The AI was correctly parsing the intent but the actual slot filtering wasn't respecting time preferences.

**Fix**: Added strict time filtering in `src/tools/check_availability.py`:
```python
if preferences.get("prefer_afternoon"):
    # Afternoon: 12 PM to 5 PM
    day_start = max(day_start, user_context["now"].tzinfo.localize(
        datetime.combine(current_date, datetime.min.time().replace(hour=12))
    ))
    day_end = min(day_end, user_context["now"].tzinfo.localize(
        datetime.combine(current_date, datetime.min.time().replace(hour=17))
    ))
```

**Lesson**: AI intent detection is only half the solution - the actual business logic must enforce the constraints.

### 4. Multi-Participant Events Not Requiring Approval
**Problem**: Events like "team standup" weren't triggering approval flows despite involving multiple people.

**Root Cause**: The AI wasn't detecting implicit participants from event types.

**Fix**: Updated prompts in `src/ai/event_ai.py` and `src/ai/intent_router.py` to explicitly extract team-related keywords as participants:
```python
# In EventAI prompt:
"team standup" → participants: ["team"] (standup implies team participation)
"team meeting" → participants: ["team"]
"all-hands" → participants: ["all-hands"]
```

**Lesson**: AI prompts need explicit examples for implicit concepts. Don't assume the AI will infer participation from context.

### 5. Timezone Issues in Task Filtering
**Problem**: Tasks due "today" weren't being found when searching.

**Root Cause**: Task due dates in UTC weren't being converted to local timezone before date comparison.

**Fix**: Convert to local timezone before comparing dates in `src/tools/find_and_analyze.py`:
```python
# Convert UTC task due time to local timezone before comparing dates
task_due_local = task_due.astimezone(now.tzinfo)
if task_due_local.date() == now.date():
    filtered_tasks.append(task)
```

**Lesson**: Always be explicit about timezone conversions, especially when comparing dates across different systems.

### 6. Understanding Reclaim's Task/Event Model
**Problem**: Tests expected Reclaim tasks to appear as both tasks AND events, but they only appeared as events.

**Root Cause**: Misunderstanding of how Reclaim works. When Reclaim schedules a task, it creates calendar events. The task itself doesn't appear in calendar searches.

**Fix**: 
1. Added 15-second delay after creating Reclaim tasks to allow scheduling
2. Updated test expectations to reflect reality:
```python
# OLD expectation (wrong):
"Should return both tasks and events for today, including at least the financial report task."

# NEW expectation (correct):
"Should return at least the financial report (which Reclaim schedules as a calendar event)."
```

**Lesson**: Understand the third-party API's data model before writing tests. Reclaim tasks become calendar events when scheduled.

## Key Architecture Insights

### 1. The AI Router is Non-Deterministic
The system uses AI (GPT-5) to route requests between Reclaim (tasks) and Nylas (calendar). This means:
- Small prompt changes can completely alter routing
- Debugging requires understanding AI decision-making
- Test assertions must be flexible to handle valid variations

### 2. Multiple Layers of AI
```
User Query → Intent Router (AI) → Tool Selection → Provider API → Response → AI Grader (AI)
```
Each AI layer adds unpredictability. When debugging, check:
1. What the Intent Router decided
2. What the tool actually did
3. What the AI Grader understood

### 3. Approval Flows are Complex
The system has multiple approval types:
- `event_create_with_participants`: Events with other people
- `event_create_conflict_reschedule`: Scheduling conflicts
- `bulk_operation`: Multiple operations

Understanding when each triggers is crucial for testing.

### 4. Singleton Pattern Issues
**Warning**: `reclaim_sdk/client.py` uses a singleton pattern that's problematic for multi-user scenarios:
```python
class ReclaimClient:
    _instance = None  # Singleton - BAD for multi-user!
    _config = None
```
This can cause credential mixing between users. Should be fixed to create per-request instances.

## Testing Best Practices

### 1. Clean Test Data Between Runs
Always clean up test data to prevent interference:
```python
# In conftest.py
@pytest.fixture(autouse=True, scope="class")
def cleanup_before_class():
    """Clean up any leftover test data before class runs."""
```

### 2. Add Delays for External APIs
External services like Reclaim need time to process:
```python
# After creating a Reclaim task
print("\n[SETUP] Waiting 15s for Reclaim to schedule the task...")
time.sleep(15)
```

### 3. Use Flexible Assertions
With AI-powered systems, be flexible:
```python
# Use semantic validation, not exact string matching
assert_response_fulfills_expectation(
    response,
    "Should detect conflict and suggest alternative",  # What matters
    request_data
)
```

### 4. Debug with Logging
Add extensive logging when debugging AI routing:
```python
logger.info(f"[CHECK_AVAILABILITY] Checking if {start_time} is in working hours...")
logger.info(f"[CHECK_AVAILABILITY] is_working_hours={is_working_hours}")
```

### 5. Test Individual Components
When tests fail, isolate components:
1. Test the AI routing separately
2. Test the tool execution separately  
3. Test the AI grader separately

## Common Pitfalls to Avoid

1. **Don't assume AI will infer context** - Be explicit in prompts
2. **Don't run Flask in debug mode during tests** - Causes hangs
3. **Don't forget timezone conversions** - UTC vs local timezone issues
4. **Don't expect immediate API responses** - Add delays for external services
5. **Don't use exact string matching with AI** - Use semantic validation
6. **Don't mix async/sync carelessly** - Use `asyncio.run()` properly
7. **Don't trust test names over test expectations** - The AI grader only looks at expectations

## Recommendations for Future Development

1. **Remove singleton pattern from ReclaimClient** - Critical for multi-user support
2. **Add request-scoped credential management** - Prevent credential mixing
3. **Improve test isolation** - Better cleanup between tests
4. **Add retry logic for external APIs** - Handle transient failures
5. **Consider mocking external APIs** - For faster, more reliable tests
6. **Document API behaviors** - Especially Reclaim's task/event model
7. **Add integration test mode** - Test against real APIs with longer timeouts

## Summary

The main challenges were:
1. Understanding the new GPT-5 API requirements
2. Dealing with Flask/async issues in testing
3. Understanding how Reclaim tasks become calendar events
4. Making AI prompts explicit enough
5. Handling timezone conversions properly

The fixes were straightforward once the root causes were identified, but debugging AI-powered systems requires patience and systematic investigation. Always question assumptions about how external services work and be explicit in both AI prompts and test expectations.