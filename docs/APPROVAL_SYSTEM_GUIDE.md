# Juli Calendar Agent Approval System Guide

Understanding how the approval system works between Juli and the Calendar A2A agent to ensure safe execution of actions that can impact a user's schedule, tasks, or invite other people to meetings.

## Overview

The approval system ensures users maintain control over potentially impactful calendar and productivity actions. When the Calendar agent needs user confirmation before proceeding, it returns a special response that Juli intercepts and handles with a native UI.

This is especially important for actions that:
- Send invitations to other people
- Modify events with existing participants  
- Perform bulk operations on multiple items
- Create potentially duplicate items
- Resolve scheduling conflicts by suggesting alternative times

## How It Works

### Flow Diagram

```
User Request → Calendar Agent → Needs Approval? → Return Approval Request
                                     ↓                        ↓
                                   No                    Juli Shows UI
                                     ↓                        ↓
                               Execute Action            User Decides
                                                             ↓
                                                       Approve/Deny
                                                             ↓
                                                    Retry with Decision
```

### The Stateless Approval Protocol

**Key Principle**: The Calendar agent doesn't store pending approvals. Instead, when an action requires confirmation, it returns a `needs_approval: true` response. This response contains all the necessary `action_data` for the client (Juli) to retry the request once the user gives their consent.

### The Approval Flow

1. A tool is called with a user request (e.g., `tool.execute` for `manage_productivity`).
2. The agent determines an approval is needed (e.g., scheduling with participants).
3. The agent responds with `needs_approval: true`, including `action_type`, `action_data`, and a `preview` object.
4. The client displays the `preview` information to the user in a confirmation UI.
5. If the user approves, the client re-calls the *same* `tool.execute` method, but this time includes `approved: true` and the `action_data` from the previous response.
6. The agent receives the approved request, bypasses the initial checks, and executes the action.

### Approval Response Format

When an action requires approval, the agent returns the following structure:

```json
{
  "needs_approval": true,
  "action_type": "string",        // e.g., "event_create_with_participants"
  "action_data": { ... },         // Complete data needed to execute the action upon approval
  "preview": {
    "summary": "string",          // A one-line summary for the user
    "details": { ... },           // Detailed information for the preview UI
    "risks": ["string"]           // Optional warnings about the action
  }
}
```

## Actions Requiring Approval

The following `action_type` values trigger an approval flow. This list is configured in the agent's `approval_config.py`.

| Action Type                        | Description                                                              |
| ---------------------------------- | ------------------------------------------------------------------------ |
| `event_create_with_participants`   | Creating a calendar event that invites other people                     |
| `event_update_with_participants`   | Updating an event that has other participants                           |
| `event_cancel_with_participants`   | Canceling an event that has other participants                          |
| `bulk_delete` / `bulk_cancel`      | Deleting multiple items (tasks or events) at once                       |
| `bulk_update` / `bulk_reschedule`  | Modifying multiple items (tasks or events) at once                      |
| `bulk_complete`                    | Marking multiple tasks as complete at once                              |
| `task_create_duplicate`            | Creating a task that appears to be a duplicate of an existing one       |
| `event_create_duplicate`           | Creating an event that appears to be a duplicate of an existing one     |
| `event_create_conflict_reschedule` | Creating an event that conflicts with another, requiring a reschedule   |
| `recurring_create`                 | Creating a recurring series of events                                   |
| `working_hours_update`             | Modifying the user's defined working hours                              |

Actions on single, personal items (like creating or completing a solo task or event) typically do not require approval and are executed immediately.

## Common Approval Scenarios

### 1. Scheduling a Meeting with Participants

Any event creation that includes other people requires approval to prevent sending unwanted invitations.

**Action Type**: `event_create_with_participants`

**Step 1: Initial Request**
The user asks to schedule a meeting with others.

*Request to `tool.execute`*:
```json
{
  "tool": "manage_productivity",
  "arguments": {
    "query": "Schedule a project sync with Alex and Maria tomorrow at 10am"
  },
  "user_context": {
    "timezone": "America/New_York",
    "current_date": "2025-08-12",
    "current_time": "14:30:00"
  }
}
```

**Step 2: Approval Required Response**
The agent detects participants and returns a request for approval.

*Agent Response*:
```json
{
  "needs_approval": true,
  "action_type": "event_create_with_participants",
  "action_data": {
    "tool": "manage_productivity",
    "params": { "query": "Schedule a project sync with Alex and Maria tomorrow at 10am" },
    "intent": { "action": "create", "item_type": "event", "has_participants": true },
    "event_details": {
      "title": "Project Sync",
      "start_time": "2025-08-13T10:00:00",
      "end_time": "2025-08-13T11:00:00",
      "participants": ["Alex", "Maria"]
    }
  },
  "preview": {
    "summary": "Schedule 'Project Sync' tomorrow at 10:00 AM",
    "details": {
      "has_participants": true,
      "participant_count": 2,
      "reasoning": "This action will send calendar invitations to other people."
    },
    "risks": ["This will send invitations to Alex and Maria."]
  }
}
```

**Step 3: Approved Request**
After the user confirms, the client re-sends the request with the approval flag and action data.

*Request to `tool.execute`*:
```json
{
  "tool": "manage_productivity",
  "arguments": {
    "approved": true,
    "action_data": { "...from previous response..." },
    "action_type": "event_create_with_participants"
  },
  "user_context": { "...same as before..." }
}
```

**Step 4: Final Execution**
The agent receives the approved request and creates the event.

*Final Agent Response*:
```json
{
  "success": true,
  "provider": "nylas",
  "action": "created",
  "data": {
    "id": "evt_123abc",
    "title": "Project Sync",
    "when": { "start": 1755037200, "end": 1755040800 }
  },
  "message": "Successfully scheduled 'Project Sync' for 10:00 AM on Wednesday, August 13. Invitations have been sent."
}
```

### 2. Resolving a Scheduling Conflict

If a user tries to schedule an event at a time that is already booked, the agent will detect the conflict and suggest an alternative time.

**Action Type**: `event_create_conflict_reschedule`

**Scenario**: The user's calendar already has an event from 3:00 PM to 4:00 PM.

**Step 1: Conflicting Request**
*Request to `tool.execute`*:
```json
{
  "tool": "manage_productivity",
  "arguments": { "query": "Book a 1-on-1 with Chloe for tomorrow at 3pm" }
}
```

**Step 2: Conflict Detected Response**
The agent identifies the conflict and proposes the next available slot. The `action_data` already contains the details for the *suggested* time.

*Agent Response*:
```json
{
  "needs_approval": true,
  "action_type": "event_create_conflict_reschedule",
  "action_data": {
    "event_details": {
      "title": "1-on-1 with Chloe",
      "start_time": "2025-08-13T16:00:00",
      "end_time": "2025-08-13T17:00:00"
    },
    "conflict_info": {
      "original_time": "2025-08-13T15:00:00",
      "conflicting_event": "Team All-Hands"
    }
  },
  "preview": {
    "summary": "Schedule conflict detected for '1-on-1 with Chloe'",
    "details": {
      "message": "The requested time (3:00 PM) conflicts with 'Team All-Hands'.",
      "suggested_alternative": {
        "start": "4:00 PM on Wednesday, August 13",
        "duration": "60 minutes"
      }
    },
    "risks": ["The originally requested time slot is not available."]
  }
}
```

**Step 3: Approved Request**
If the user accepts the alternative, the client sends the approval.

*Request to `tool.execute`*:
```json
{
  "tool": "manage_productivity",
  "arguments": {
    "approved": true,
    "action_data": { "...from previous response..." },
    "action_type": "event_create_conflict_reschedule"
  }
}
```

**Step 4: Final Execution**
The agent creates the event at the suggested alternative time of 4:00 PM.

### 3. Handling Duplicate Item Creation

To prevent accidental duplicate entries, the agent checks for existing tasks or events with a similar title and time before creating a new one.

**Action Type**: `task_create_duplicate` or `event_create_duplicate`

**Scenario**: A task named "Review Q3 Performance Report" already exists.

**Step 1: Duplicate Request**
*Request to `tool.execute`*:
```json
{
  "tool": "manage_productivity",
  "arguments": { "query": "create task to review the Q3 performance report" }
}
```

**Step 2: Duplicate Detected Response**
The agent finds a similar existing task and asks for confirmation.

*Agent Response*:
```json
{
  "needs_approval": true,
  "action_type": "task_create_duplicate",
  "action_data": {
    "task_details": {
      "title": "Review Q3 Performance Report",
      "priority": "P2",
      "due_date": "2025-08-15T17:00:00"
    }
  },
  "preview": {
    "summary": "Duplicate task detected: 'Review Q3 Performance Report'",
    "details": {
      "message": "A task with a similar title already exists. Do you want to create another one?",
      "existing_task": {
        "id": "task_456def",
        "title": "Review Q3 Performance Report",
        "status": "NEW"
      }
    },
    "risks": ["This will create a second task with a very similar title."]
  }
}
```

**Step 3 & 4: Approval and Execution**
If approved, the agent proceeds to create a new, separate task, acknowledging it's a duplicate.

### 4. Approving Bulk Operations

Actions that affect multiple items at once, such as deleting or completing several tasks, require approval to prevent accidental data loss.

**Action Type**: `bulk_complete`, `bulk_delete`, etc.

**Step 1: Bulk Request**
*Request to `tool.execute`*:
```json
{
  "tool": "manage_productivity",
  "arguments": { "query": "complete all tasks with 'onboarding' in the title" }
}
```

**Step 2: Bulk Action Approval Response**
The agent identifies this as a bulk operation and asks for confirmation. The preview should provide an idea of the scope.

*Agent Response*:
```json
{
  "needs_approval": true,
  "action_type": "bulk_complete",
  "action_data": {
    "operation": "complete",
    "task_ids": ["task_123", "task_456", "task_789", "task_abc"],
    "filter_criteria": "title contains 'onboarding'"
  },
  "preview": {
    "summary": "Complete 4 tasks matching 'onboarding'",
    "details": {
      "operation": "Complete",
      "item_count": 4,
      "sample_items": [
         "Draft onboarding welcome email",
         "Schedule onboarding check-in",
         "Review onboarding survey results",
         "Update onboarding documentation"
      ]
    },
    "risks": ["This action will mark 4 tasks as complete and cannot be easily undone."]
  }
}
```

**Step 3 & 4: Approval and Execution**
Once approved, the agent will find all matching tasks and mark them as complete, returning a summary of the result.

## What Juli Handles

### 1. Approval UI

When Juli receives a `needs_approval` response, it:

```typescript
// Juli's internal handling
if (response.needs_approval) {
  // Show native approval dialog
  const userDecision = await showApprovalDialog({
    title: response.action_type,
    summary: response.preview.summary,
    details: response.preview.details,
    risks: response.preview.risks
  });
  
  if (userDecision.approved) {
    // Retry with approval
    const finalResponse = await callA2ATool(toolName, {
      ...originalParams,
      approved: true,
      action_data: response.action_data,
      action_type: response.action_type
    });
    return finalResponse;
  } else {
    // User denied
    return {
      cancelled: true,
      message: 'Action cancelled by user'
    };
  }
}
```

### 2. Approval UI Components

Juli renders a confirmation dialog with:
- Clear action summary (e.g., "Schedule 'Project Sync' tomorrow at 10:00 AM")
- Detailed preview (participant count, conflict information, affected items)
- Risk warnings in red (e.g., "This will send invitations to 3 people")
- Approve/Deny buttons
- Optional "Modify" button for editable actions

### 3. Context-Aware Previews

Different approval types get specialized UI treatment:
- **Participant invitations**: Show who will be invited and what they'll receive
- **Conflict resolution**: Display the conflict and suggested alternative times
- **Bulk operations**: List affected items with counts and samples
- **Duplicate detection**: Show the existing item for comparison

## Best Practices for Client Implementation

### 1. Provide Clear Previews
Use the `preview` object to give the user a clear, unambiguous understanding of what will happen. For time-related actions, always show dates and times clearly.

**✅ Good:**
```json
"summary": "Reschedule 'Project Standup' to tomorrow at 4:00 PM"
```

**❌ Bad:**
```json
"summary": "Update event"
```

### 2. Handle Timezones
When displaying times from the `preview` object, make sure to present them in the user's local timezone to avoid confusion.

### 3. Design for Different Approval Types
Your UI should adapt to the `action_type`. A conflict resolution approval (`event_create_conflict_reschedule`) should clearly show the original time and the suggested new time. A bulk operation approval (`bulk_complete`) should show how many items will be affected.

### 4. Maintain Statelessness
Remember that the agent is stateless. Never rely on it to store a pending approval. The `action_data` object contains everything needed to re-run the request. Your client is responsible for managing the state of the approval UI.

### 5. Implement Smart Defaults
- Default to sending updates only to added/removed attendees for attendee list changes
- Default to "this event only" when editing a single occurrence of a recurring event
- Surface conflicts early with suggested alternative times

### 6. Provide Safety Nets
- Implement undo functionality for completed actions
- Show audit trails of calendar changes
- Allow easy revert of series changes

## Security Considerations

### 1. Action Data Validation

Always re-validate action data when executing approved actions:

```python
if params.get("approved") and params.get("action_data"):
    # Re-validate the action data
    action_data = params["action_data"]
    if not self._validate_event_details(action_data.get("event_details")):
        return {
            "error": "Invalid event details in approval data"
        }
    
    # Verify credentials are still valid
    if not self.credential_manager.is_setup_complete(credentials):
        return {
            "error": "Credentials no longer valid for approved action"
        }
```

### 2. Prevent Approval Bypass

```python
# Always check approval status for sensitive actions
if self._requires_approval(action_type) and not params.get("approved"):
    # Force approval flow
    return { "needs_approval": True, ... }

# Don't allow approval flag without action_data
if params.get("approved") and not params.get("action_data"):
    return {
        "error": "Approved flag requires action_data"
    }
```

### 3. Audit Trail

Log all approval actions for security and debugging:

```python
logger.info(f"Approval granted for {action_type}: {action_summary}")
```

## Testing Approval Flows

```python
def test_participant_invitation_approval():
    # Test that participant invitations require approval
    response = await calendar_agent.execute({
        "tool": "manage_productivity",
        "arguments": {
            "query": "Schedule team meeting with John and Sarah tomorrow at 2pm"
        }
    })
    
    assert response["needs_approval"] == True
    assert response["action_type"] == "event_create_with_participants"
    assert "participants" in response["action_data"]["event_details"]
    assert "This will send invitations" in response["preview"]["risks"][0]

def test_approved_execution():
    # Test that approved actions execute properly
    approval_response = await get_approval_response()
    
    final_response = await calendar_agent.execute({
        "tool": "manage_productivity", 
        "arguments": {
            "approved": True,
            "action_data": approval_response["action_data"],
            "action_type": "event_create_with_participants"
        }
    })
    
    assert final_response["success"] == True
    assert "Invitations have been sent" in final_response["message"]
```

## Summary

The Juli Calendar Agent approval system provides:

1. **User Control** - Users always have final say on actions affecting others or multiple items
2. **Transparency** - Clear previews of what will happen, including who gets notified
3. **Flexibility** - Developers decide what needs approval based on impact and risk
4. **Simplicity** - Stateless design makes implementation straightforward
5. **Security** - No way to bypass user approval for sensitive calendar actions

By following this guide, your implementation will integrate seamlessly with Juli's approval system, giving users confidence to use powerful calendar tools while maintaining control over their schedule and communications.