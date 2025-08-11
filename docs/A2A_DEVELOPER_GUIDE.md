# A2A Developer Guide for Juli Calendar Agent

## Overview

The Juli Calendar Agent has been migrated to support the A2A (Agent-to-Agent) protocol, enabling seamless integration with Juli Brain and other Juli agents using JSON-RPC 2.0 communication.

## Quick Start

### 1. Discovery

The agent card is available at the well-known discovery endpoint:

```bash
curl http://localhost:3002/.well-known/a2a.json
```

Response:
```json
{
  "agent_id": "juli-calendar",
  "agent_name": "Juli Calendar Agent",
  "version": "2.0.0",
  "description": "AI-powered calendar and task management agent for Juli",
  "capabilities": {
    "tools": [
      {
        "name": "manage_productivity",
        "description": "Create, update, and manage tasks and calendar events using natural language"
      },
      {
        "name": "check_availability",
        "description": "Check calendar availability and find free time slots"
      },
      {
        "name": "find_and_analyze",
        "description": "Search and analyze calendar events and tasks"
      }
    ]
  },
  "auth": {
    "schemes": [
      {
        "type": "oidc",
        "issuers": ["https://auth.juli-ai.com"],
        "audiences": ["juli-calendar"]
      },
      {
        "type": "dev_secret",
        "header": "X-A2A-Dev-Secret",
        "description": "Development authentication using shared secret"
      }
    ]
  },
  "rpc": {
    "endpoint": "/a2a/rpc",
    "version": "2.0"
  }
}
```

### 2. Authentication

#### Development Mode
Set the `A2A_DEV_SECRET` environment variable and include it in requests:

```bash
export A2A_DEV_SECRET="your-secret-key"

curl -X POST http://localhost:3002/a2a/rpc \
  -H "Content-Type: application/json" \
  -H "X-A2A-Dev-Secret: your-secret-key" \
  -d '{"jsonrpc":"2.0","id":1,"method":"agent.handshake","params":{}}'
```

#### Production Mode
Use OIDC bearer tokens from Juli Auth:

```bash
curl -X POST http://localhost:3002/a2a/rpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt-token>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"agent.handshake","params":{}}'
```

## JSON-RPC Methods

### agent.card
Get the agent's capabilities and metadata.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "agent.card",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "agent_id": "juli-calendar",
    "agent_name": "Juli Calendar Agent",
    "version": "2.0.0",
    "capabilities": {...}
  }
}
```

### agent.handshake
Initial connection handshake with the agent.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "agent.handshake",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "agent": "juli-calendar",
    "card": {...},
    "server_time": "2025-01-08T12:00:00Z"
  }
}
```

### tool.list
List all available tools.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tool.list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "tools": [
      {
        "name": "manage_productivity",
        "description": "Create, update, and manage tasks and calendar events"
      },
      {
        "name": "check_availability",
        "description": "Check calendar availability"
      },
      {
        "name": "find_and_analyze",
        "description": "Search and analyze events and tasks"
      }
    ]
  }
}
```

### tool.execute
Execute a specific tool with arguments.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tool.execute",
  "params": {
    "tool": "manage_productivity",
    "arguments": {
      "query": "Create a meeting tomorrow at 2 PM with John"
    },
    "user_context": {
      "timezone": "America/Los_Angeles",
      "current_date": "2025-01-08",
      "current_time": "10:30:00",
      "user_name": "Alice",
      "user_email": "alice@example.com",
      "credentials": {
        "RECLAIM_API_KEY": "rk_...",
        "NYLAS_GRANT_ID": "grant_..."
      }
    },
    "request_id": "req_12345"
  }
}
```

**Response (Success):**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "success": true,
    "action_type": "event_created",
    "details": {
      "event_id": "evt_123",
      "title": "Meeting with John",
      "start": "2025-01-09T14:00:00-08:00",
      "end": "2025-01-09T15:00:00-08:00"
    }
  }
}
```

**Response (Needs Approval):**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "needs_approval": true,
    "action_type": "event_create_with_participants",
    "action_data": {
      "title": "Meeting with John",
      "participants": ["john@example.com"],
      "start": "2025-01-09T14:00:00-08:00",
      "duration": 60
    },
    "preview": "Create a 1-hour meeting 'Meeting with John' tomorrow at 2:00 PM with john@example.com",
    "request_id": "req_12345"
  }
}
```

### tool.approve
Approve or reject a pending action that requires approval.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tool.approve",
  "params": {
    "tool": "manage_productivity",
    "approved": true,
    "action_data": {
      "title": "Meeting with John",
      "participants": ["john@example.com"],
      "start": "2025-01-09T14:00:00-08:00",
      "duration": 60
    },
    "original_arguments": {
      "query": "Create a meeting tomorrow at 2 PM with John"
    },
    "user_context": {
      "timezone": "America/Los_Angeles",
      "credentials": {
        "RECLAIM_API_KEY": "rk_...",
        "NYLAS_GRANT_ID": "grant_..."
      }
    },
    "request_id": "req_12345"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "success": true,
    "action_type": "event_created",
    "details": {
      "event_id": "evt_123",
      "title": "Meeting with John"
    }
  }
}
```

## User Context

The `user_context` parameter provides essential information about the user and their environment:

### Required Fields
- `timezone`: User's timezone (e.g., "America/Los_Angeles")
- `current_date`: Current date in YYYY-MM-DD format
- `current_time`: Current time in HH:MM:SS format

### Optional Fields
- `user_name`: User's display name
- `user_email`: User's email address
- `credentials`: Object containing authentication credentials
  - `RECLAIM_API_KEY`: Reclaim.ai API key for task management
  - `NYLAS_GRANT_ID`: Nylas grant ID for calendar access

## Credentials

The agent requires credentials to access calendar and task services:

### Credential Manifest
Available at `/.well-known/a2a-credentials.json`:

```json
{
  "version": "1.0",
  "credentials": [
    {
      "key": "RECLAIM_API_KEY",
      "display_name": "Reclaim.ai API Key",
      "description": "Your personal API key from Reclaim.ai for task management",
      "sensitive": true,
      "required": true,
      "flows": [
        {
          "type": "api_key",
          "instructions": "Get your API key from Reclaim.ai...",
          "validation_endpoint": "/setup/validate-reclaim"
        }
      ]
    },
    {
      "key": "NYLAS_GRANT_ID",
      "display_name": "Calendar Account Grant",
      "description": "Grant for accessing your calendar",
      "sensitive": true,
      "required": true,
      "flows": [
        {
          "type": "hosted_auth",
          "connect_url": "/setup/connect-url",
          "callback": "/api/nylas-calendar/callback",
          "providers": ["google", "microsoft"]
        }
      ]
    }
  ]
}
```

## Approval Flows

Certain operations require user approval before execution:

### Operations Requiring Approval
1. **event_create_with_participants**: Creating events with other attendees
2. **bulk_operation**: Operations affecting multiple items
3. **event_create_conflict_reschedule**: Creating events that conflict with existing ones
4. **duplicate_task_creation**: Creating tasks that appear to be duplicates

### Approval Flow
1. Tool execution returns `needs_approval: true`
2. Client presents the preview to the user
3. User approves or rejects
4. Client calls `tool.approve` with the decision
5. Tool executes or cancels based on approval

## Error Handling

### JSON-RPC Error Codes
- `-32700`: Parse error - Invalid JSON
- `-32600`: Invalid Request - Not valid JSON-RPC 2.0
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32000`: Custom error - Authentication failed

### Tool-Specific Errors
Tools may return error responses with additional context:

```json
{
  "success": false,
  "error": "Task title is required",
  "error_code": "VALIDATION_ERROR",
  "tool": "manage_productivity"
}
```

## Testing

### Test Script
A comprehensive test script is available at `test_a2a.py`:

```bash
# Set dev secret
export A2A_DEV_SECRET="test-dev-secret"

# Start server
python3 scripts/run_server.py --port 3002

# Run tests
python3 test_a2a.py
```

### Manual Testing with curl

Test handshake:
```bash
curl -X POST http://localhost:3002/a2a/rpc \
  -H "Content-Type: application/json" \
  -H "X-A2A-Dev-Secret: test-dev-secret" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "agent.handshake",
    "params": {}
  }' | jq
```

Test tool execution:
```bash
curl -X POST http://localhost:3002/a2a/rpc \
  -H "Content-Type: application/json" \
  -H "X-A2A-Dev-Secret: test-dev-secret" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tool.execute",
    "params": {
      "tool": "find_and_analyze",
      "arguments": {
        "query": "Show my tasks for today"
      },
      "user_context": {
        "timezone": "America/Los_Angeles",
        "current_date": "2025-01-08",
        "current_time": "10:00:00",
        "credentials": {
          "RECLAIM_API_KEY": "your-api-key"
        }
      }
    }
  }' | jq
```


## Environment Variables

- `A2A_DEV_SECRET`: Development secret for authentication
- `FLASK_ENV`: Set to "development" for dev mode
- `NYLAS_API_KEY`: Server-side Nylas API key
- `RECLAIM_API_KEY`: Default Reclaim API key (optional)

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Ensure `A2A_DEV_SECRET` is set correctly
   - Check that the header `X-A2A-Dev-Secret` matches

2. **Tool Not Found**
   - Verify tool name in the request
   - Check available tools with `tool.list` method

3. **Missing Credentials**
   - Ensure credentials are provided in `user_context`
   - Check credential keys match expected format

4. **Invalid JSON-RPC**
   - Verify `jsonrpc: "2.0"` is included
   - Ensure `id` field is present for request-response correlation

## Support

For issues or questions about the A2A implementation:
- Review the [A2A Migration Plan](./A2A_MIGRATION_PLAN.md)
- Check the [test suite](../test_a2a.py) for examples
- Contact the Juli AI team at support@juli-ai.com