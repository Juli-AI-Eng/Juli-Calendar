Packing repository using Repomix...
Analyzing repository using gemini-2.5-flash...
The issue where events like 'Schedule team standup tomorrow at 10am' do not trigger an approval flow, despite implying multiple participants, stems from the AI's intent classification. Specifically, the `IntentRouter` is not explicitly instructed to detect implicit multi-participant terms (like "team", "group", "all-hands") and set the `involves_others` flag accordingly in its tool output. This flag is crucial for the `manage_productivity` tool to determine if approval is required.

The current `analyze_intent` tool in `src/ai/intent_router.py` does not include `involves_others` as a required parameter in its schema, nor does its system message explicitly guide the AI to populate this field based on collective terms.

To fix this, we need to:
1.  **Add `involves_others` to the `analyze_intent` tool's schema** in `src/ai/intent_router.py`.
2.  **Update the system message** for this tool to instruct the AI to set `involves_others` to `true` when a calendar query contains terms that imply multiple participants, even if no specific names are provided.

### Proposed Change

Modify the `src/ai/intent_router.py` file as follows:

```diff
--- a/src/ai/intent_router.py
+++ b/src/ai/intent_router.py
@@ -34,7 +34,12 @@
                             "type": "string",
                             "enum": ["reclaim", "nylas"]},
                             "intent_type": {"type": "string", "enum": ["task", "calendar"]}
+                            # ADDED: Explicitly define involves_others in the schema
+                            "involves_others": {
+                                "type": "boolean",
+                                "description": "True if the event or task clearly involves other people (e.g., 'meeting with John', 'team standup', 'group project'). False otherwise."
+                            }
                         },
-                        "required": ["provider", "intent_type"]
+                        "required": ["provider", "intent_type", "involves_others"] # ADDED: Make it required
                     }
                 }
             }
@@ -42,11 +47,15 @@
             messages = [
                 {
                     "role": "system", 
-                    "content": """You are a request classifier.
-RULE 1: If the query contains the word "task" → Return provider="reclaim", intent_type="task"
-RULE 2: Otherwise, if it mentions meetings/appointments/calendar OR has a specific time (like "at 3pm", "tomorrow morning", "Monday at 10am") → Return provider="nylas", intent_type="calendar"
-RULE 3: Otherwise → Return provider="reclaim", intent_type="task"
-CRITICAL: The word "task" ALWAYS means Reclaim. No exceptions.
-IMPORTANT: If the query has a SPECIFIC TIME (not just a due date), it should be a calendar event:
-- "at 3pm", "tomorrow at 10am", "Monday morning" = specific time → calendar event
-- "by Friday", "end of week", "next month" = due date → task
-- "tomorrow morning" = specific time (defaults to 9am) → calendar event
-You must call analyze_intent for every request."""
+                    "content": """You are a request classifier for a productivity system.
+
+RULES:
+RULE 1: If the query contains the word "task" (e.g., "create a task", "update my task list") → Return provider="reclaim", intent_type="task". Set involves_others=false unless specific names are mentioned for a collaborative task.
+RULE 2: Otherwise, if it mentions meetings/appointments/calendar (e.g., "schedule a meeting", "book an appointment", "check calendar") OR has a specific time (e.g., "at 3pm", "tomorrow morning", "Monday at 10am") → Return provider="nylas", intent_type="calendar".
+    For calendar events (provider="nylas"), set involves_others=true if the query implies multiple participants (e.g., "team standup", "group meeting", "all-hands", "meeting with John and Sarah", "staff meeting", "company-wide call"). Otherwise set involves_others=false (e.g., "personal appointment", "deep work", "solo study time").
+RULE 3: For all other queries not covered by Rule 1 or Rule 2 → Return provider="reclaim", intent_type="task", involves_others=false.
+
+CRITICAL: The word "task" ALWAYS means Reclaim. No exceptions.
+IMPORTANT: If a query has a SPECIFIC TIME (not just a due date), it should be a calendar event (Rule 2):
+- "at 3pm", "tomorrow at 10am", "Monday morning" = specific time → calendar event
+- "by Friday", "end of week", "next month" = due date → task
+
+You must always call the `analyze_intent` function with the extracted parameters."""
                 },
                 {
                     "role": "user",

```

### Reasoning for the fix:

1.  **Explicit Schema Definition**: By adding `involves_others` directly to the `analyze_intent` tool's `parameters` schema and making it `required`, we explicitly tell the AI that this piece of information is expected in its output. This forces the model to consider and populate this field for every classification.
2.  **Enhanced System Message**: The updated system message provides clear, rule-based instructions and examples for when to set `involves_others` to `true` for calendar events. It specifies terms like "team", "group", and "all-hands", which were implicitly expected before but not explicitly defined, leading to inconsistent detection. It also clarifies default behavior for `task` queries.
3.  **AI-Native Approach**: This approach leverages the AI's natural language understanding capabilities to infer participant involvement from conversational cues, rather than relying on brittle keyword matching. This ensures the system remains flexible and robust to varied user phrasing.

This change directly addresses the user's problem by ensuring that the `IntentRouter` correctly identifies multi-participant events, which then triggers the necessary approval flow in `manage_productivity.py`.

### Files most relevant to the user's query:

*   `src/ai/intent_router.py`
*   `src/tools/manage_productivity.py`
*   `src/config/approval_config.py`
*   `tests/e2e/test_approval_flow_e2e.py`
*   `local-research/test-analysis.md`