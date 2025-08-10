# Inbox MCP Tools Documentation

Comprehensive documentation for all tools available in the Inbox MCP server, including the setup endpoint.

## Table of Contents
- [Setup Tool](#setup-tool)
- [manage_email](#manage_email)
- [find_emails](#find_emails)
- [organize_inbox](#organize_inbox)
- [email_insights](#email_insights)
- [smart_folders](#smart_folders)

---

## Setup Tool

**Endpoint**: `POST /mcp/tools/setup`

The setup tool guides users through connecting their email account via Nylas. It provides a multi-step wizard experience with validation.

### Parameters

```typescript
{
  action: "get_instructions" | "validate_credentials" | "test_connection",
  credentials?: {
    NYLAS_ACCESS_TOKEN?: string,
    NYLAS_GRANT_ID?: string
  }
}
```

### Actions

#### `get_instructions`
Returns step-by-step setup instructions.

**Request**:
```json
{
  "action": "get_instructions"
}
```

**Response**:
```json
{
  "type": "setup_instructions",
  "steps": [
    {
      "title": "Create Your Nylas Account",
      "description": "Sign up for a free Nylas account",
      "url": "https://dashboard-v3.nylas.com/register",
      "tips": [
        "Use the email you want to connect",
        "No credit card required"
      ]
    },
    {
      "title": "Get Your API Key",
      "description": "Find your API key in the dashboard",
      "tips": ["Look for 'API Keys' in the sidebar"]
    },
    {
      "title": "Connect Your Email",
      "description": "Add your email account as a grant",
      "tips": ["Click 'Add Test Grant'", "Authorize all permissions"]
    }
  ]
}
```

#### `validate_credentials`
Validates provided Nylas credentials.

**Request**:
```json
{
  "action": "validate_credentials",
  "credentials": {
    "NYLAS_ACCESS_TOKEN": "nyk_abc123...",
    "NYLAS_GRANT_ID": "grant_123..."
  }
}
```

**Success Response**:
```json
{
  "valid": true,
  "message": "Successfully connected to your email!",
  "email_address": "user@example.com",
  "provider": "gmail"
}
```

**Error Response**:
```json
{
  "valid": false,
  "error": "Invalid API key",
  "suggestion": "Check your API key starts with 'nyk_'"
}
```

#### `test_connection`
Tests the email connection after setup.

**Request**:
```json
{
  "action": "test_connection"
}
```

**Response**:
```json
{
  "connected": true,
  "email_count": 1247,
  "oldest_email": "2020-01-15",
  "provider": "gmail"
}
```

---

## manage_email

Send, reply, forward, or draft emails using natural language. The AI understands context and handles email composition intelligently.

### Parameters

```typescript
{
  action: "send" | "reply" | "forward" | "draft",
  query: string,                    // Natural language description
  context_message_id?: string,      // For replies/forwards
  require_approval?: boolean,       // Default: true
  
  // Context injection (auto-filled by Juli)
  user_name?: string,
  user_email?: string
}
```

### Examples

#### Send New Email
**Request**:
```json
{
  "action": "send",
  "query": "Email Sarah about postponing tomorrow's meeting to Friday at 2pm"
}
```

**Response** (Needs Approval):
```json
{
  "needs_approval": true,
  "action_type": "send_email",
  "action_data": {
    "email_content": {
      "to": ["sarah.johnson@company.com"],
      "subject": "Meeting Reschedule - Moving to Friday",
      "body": "Hi Sarah,\n\nI hope this email finds you well. I wanted to reach out about tomorrow's meeting.\n\nWould it be possible to reschedule our meeting to Friday at 2pm instead? Something urgent has come up that requires my attention tomorrow.\n\nPlease let me know if Friday at 2pm works for your schedule.\n\nBest regards,\nJohn"
    }
  },
  "preview": {
    "summary": "Send email to sarah.johnson@company.com",
    "details": {
      "recipient": "Sarah Johnson",
      "subject": "Meeting Reschedule - Moving to Friday",
      "word_count": 67
    }
  }
}
```

#### Reply to Email
**Request**:
```json
{
  "action": "reply",
  "query": "Thank her for the proposal and ask for clarification on the timeline",
  "context_message_id": "msg_abc123"
}
```

**Response**:
```json
{
  "needs_approval": true,
  "action_type": "send_email",
  "action_data": {
    "email_content": {
      "to": ["sender@example.com"],
      "subject": "Re: Project Proposal",
      "body": "Hi Jane,\n\nThank you for sending over the proposal. I've had a chance to review it and I'm impressed with the comprehensive approach.\n\nCould you please provide some clarification on the timeline? Specifically, I'd like to understand the key milestones and deliverable dates.\n\nLooking forward to your response.\n\nBest regards,\nJohn",
      "reply_to_message_id": "msg_abc123"
    }
  },
  "preview": {
    "summary": "Reply to Jane about Project Proposal",
    "details": {
      "in_reply_to": "Project Proposal",
      "thread_length": 3
    }
  }
}
```

#### Forward Email
**Request**:
```json
{
  "action": "forward",
  "query": "Forward this to the dev team with a note about prioritizing the security issues",
  "context_message_id": "msg_xyz789"
}
```

#### Draft Email
**Request**:
```json
{
  "action": "draft",
  "query": "Draft a follow-up email to all attendees from yesterday's meeting with action items"
}
```

**Response**:
```json
{
  "success": true,
  "draft_id": "draft_123",
  "message": "Draft saved successfully",
  "draft_preview": {
    "subject": "Follow-up: Yesterday's Meeting - Action Items",
    "recipients": ["attendee1@company.com", "attendee2@company.com"]
  }
}
```

---

## find_emails

Search and analyze emails using natural language queries. Returns intelligent summaries and insights.

### Parameters

```typescript
{
  query: string,                              // Natural language search
  analysis_type?: "summary" | "detailed" | "action_items" | "priority",
  limit?: number,                             // Max emails to analyze (default: 20)
  include_spam?: boolean,                     // Include spam folder (default: false)
  
  // Context injection
  user_timezone?: string
}
```

### Examples

#### Find Unread Important Emails
**Request**:
```json
{
  "query": "important unread emails from this week",
  "analysis_type": "priority"
}
```

**Response**:
```json
{
  "success": true,
  "total_found": 12,
  "analysis": {
    "high_priority": [
      {
        "id": "msg_123",
        "from": "boss@company.com",
        "subject": "Urgent: Budget Review Needed",
        "received": "2024-01-24T10:30:00Z",
        "importance_score": 0.95,
        "why_important": "From direct manager, marked urgent, mentions deadline"
      }
    ],
    "medium_priority": [
      {
        "id": "msg_456",
        "from": "client@example.com",
        "subject": "Re: Project Timeline",
        "importance_score": 0.75,
        "why_important": "Client response, ongoing project discussion"
      }
    ],
    "summary": "You have 3 high-priority emails requiring immediate attention"
  }
}
```

#### Find Emails with Action Items
**Request**:
```json
{
  "query": "emails that need my response",
  "analysis_type": "action_items"
}
```

**Response**:
```json
{
  "success": true,
  "total_found": 8,
  "action_items": [
    {
      "email_id": "msg_789",
      "from": "colleague@company.com",
      "subject": "Review needed: Q4 Report",
      "action_required": "Review and provide feedback on Q4 report",
      "deadline": "2024-01-26",
      "extracted_from": "Could you please review the attached Q4 report and provide your feedback by Friday?"
    }
  ]
}
```

#### Search with Natural Dates
**Request**:
```json
{
  "query": "invoices from last month",
  "analysis_type": "summary"
}
```

---

## organize_inbox

Perform bulk operations on emails using intelligent rules and natural language instructions.

### Parameters

```typescript
{
  instruction: string,                    // What to do
  scope?: {
    folder?: string,                      // Which folder (default: "inbox")
    date_range?: string,                  // Natural language date range
    limit?: number                        // Max emails to process
  },
  dry_run?: boolean,                      // Preview without executing (default: true)
  confirmed?: boolean                     // Execute the operation
}
```

### Examples

#### Archive Old Emails
**Request**:
```json
{
  "instruction": "Archive all emails older than 30 days except starred ones",
  "scope": {
    "folder": "inbox"
  },
  "dry_run": true
}
```

**Response** (Dry Run):
```json
{
  "preview": true,
  "operation": "archive",
  "would_affect": {
    "total": 156,
    "breakdown": {
      "newsletters": 89,
      "notifications": 45,
      "conversations": 22
    },
    "excluded": {
      "starred": 5,
      "important": 3
    }
  },
  "sample_emails": [
    {
      "subject": "Your Weekly Newsletter",
      "from": "newsletter@example.com",
      "date": "2023-12-15"
    }
  ],
  "to_execute": "Set 'confirmed': true to execute"
}
```

#### Clean Up Newsletters
**Request**:
```json
{
  "instruction": "Move all unread newsletters to a Newsletter folder",
  "confirmed": true
}
```

**Response**:
```json
{
  "success": true,
  "operation": "move",
  "processed": 34,
  "details": {
    "moved_to": "Newsletter",
    "folder_created": true,
    "time_saved": "Approximately 15 minutes of manual sorting"
  }
}
```

#### Smart Filtering
**Request**:
```json
{
  "instruction": "Delete promotional emails keeping only those from services I actually use",
  "dry_run": true
}
```

The AI will intelligently identify which services you use based on your email history.

---

## email_insights

Get AI-powered insights and analytics about your email patterns and important items.

### Parameters

```typescript
{
  insight_type: "daily_summary" | "important_items" | "response_needed" | 
                "analytics" | "relationships",
  time_period?: string,                   // Natural language (default: "today")
  focus_area?: string,                    // Specific topic/project/person
  
  // Context injection
  user_timezone?: string,
  current_date?: string
}
```

### Examples

#### Daily Summary
**Request**:
```json
{
  "insight_type": "daily_summary",
  "time_period": "today"
}
```

**Response**:
```json
{
  "success": true,
  "summary": {
    "date": "2024-01-24",
    "new_emails": 47,
    "important_count": 5,
    "urgent_items": [
      {
        "from": "manager@company.com",
        "subject": "Budget approval needed today",
        "action": "Requires approval by EOD"
      }
    ],
    "meetings_mentioned": [
      "Product Review - Tomorrow 2pm",
      "Client Call - Friday 10am"
    ],
    "key_topics": ["Q4 Report", "Budget Review", "Project Alpha"],
    "response_needed": 3,
    "can_archive": 31
  },
  "recommendation": "Focus on the budget approval first, then address the 3 emails needing responses"
}
```

#### Relationship Insights
**Request**:
```json
{
  "insight_type": "relationships",
  "time_period": "last month"
}
```

**Response**:
```json
{
  "success": true,
  "top_correspondents": [
    {
      "email": "sarah@company.com",
      "name": "Sarah Johnson",
      "interaction_count": 45,
      "your_average_response_time": "2.5 hours",
      "their_average_response_time": "1.2 hours",
      "topics": ["Project Alpha", "Budget Planning"],
      "relationship_type": "frequent_collaborator"
    }
  ],
  "communication_patterns": {
    "busiest_day": "Tuesday",
    "peak_hours": "9am-11am",
    "average_daily_emails": 67
  }
}
```

#### Response Analytics
**Request**:
```json
{
  "insight_type": "response_needed",
  "focus_area": "Project Alpha"
}
```

---

## smart_folders

Create and manage intelligent folders that automatically organize emails based on AI understanding.

### Parameters

```typescript
{
  action: "create" | "update" | "apply" | "list",
  rule?: string,                          // Natural language rule
  folder_name?: string,                   // Folder name (AI suggests if not provided)
  options?: {
    auto_apply?: boolean,                 // Apply to existing emails
    ongoing?: boolean                     // Apply to future emails
  }
}
```

### Examples

#### Create Smart Folder
**Request**:
```json
{
  "action": "create",
  "rule": "Important client emails that mention contracts or proposals",
  "folder_name": "Client Contracts"
}
```

**Response**:
```json
{
  "success": true,
  "folder_created": "Client Contracts",
  "rule_interpretation": {
    "conditions": [
      "From domain in known client list",
      "Contains keywords: contract, proposal, agreement, SOW",
      "Importance score > 0.7"
    ]
  },
  "would_match": 23,
  "sample_matches": [
    "Contract renewal - Acme Corp",
    "Proposal for Q1 Services"
  ]
}
```

#### Apply Smart Folder
**Request**:
```json
{
  "action": "apply",
  "folder_name": "Client Contracts",
  "options": {
    "auto_apply": true
  }
}
```

**Response**:
```json
{
  "success": true,
  "emails_organized": 23,
  "folder": "Client Contracts",
  "future_handling": "New matching emails will be automatically filed"
}
```

#### List Smart Folders
**Request**:
```json
{
  "action": "list"
}
```

**Response**:
```json
{
  "smart_folders": [
    {
      "name": "Client Contracts",
      "email_count": 23,
      "rule": "Important client emails with contracts/proposals",
      "auto_filing": true,
      "created": "2024-01-15"
    },
    {
      "name": "Team Updates",
      "email_count": 156,
      "rule": "Updates from team members about ongoing projects",
      "auto_filing": false
    }
  ]
}
```

---

## Error Responses

All tools return consistent error responses:

```json
{
  "error": "User-friendly error message",
  "error_code": "SPECIFIC_ERROR_CODE",
  "details": {
    "suggestion": "How to fix the issue",
    "retry_after": 60  // If rate limited
  }
}
```

Common error codes:
- `NEEDS_SETUP` - Credentials not configured
- `INVALID_CREDENTIALS` - Credentials validation failed
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `EMAIL_NOT_FOUND` - Referenced email doesn't exist
- `INVALID_PARAMETER` - Parameter validation failed
- `AI_PROCESSING_ERROR` - AI couldn't understand request

## Best Practices

1. **Use Natural Language**: Users should speak naturally, not in technical terms
2. **Provide Context**: Include context when referencing previous emails
3. **Test Edge Cases**: Empty inboxes, invalid email addresses, network failures
4. **Handle Errors Gracefully**: Always return helpful error messages
5. **Respect Rate Limits**: Implement exponential backoff for retries