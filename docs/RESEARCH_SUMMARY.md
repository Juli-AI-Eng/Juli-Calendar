# Reclaim MCP Research Summary

## Overview
This document summarizes the research findings from analyzing the Inbox-MCP implementation and planning how to convert the Reclaim SDK into an MCP server for the Juli ecosystem.

## Key Findings

### 1. MCP Architecture Pattern

The MCP (Model Context Protocol) servers for Juli follow a specific HTTP-based architecture:

- **Stateless Design**: All operations are stateless - no session management
- **RESTful Endpoints**: Standard REST API patterns with JSON payloads
- **Tool Discovery**: `/mcp/tools` endpoint lists available tools with schemas
- **Tool Execution**: `/mcp/tools/{toolName}` handles tool execution
- **Setup Flow**: `/mcp/needs-setup` and setup tools for credential configuration

### 2. Authentication Flow

Juli handles authentication through a credential injection system:

1. **User Setup**: Users provide credentials once through the setup flow
2. **Juli Storage**: Juli securely stores and manages credentials
3. **Header Injection**: Credentials are injected as `X-User-Credential-*` headers
4. **Per-Request Auth**: Each request includes credentials - no sessions

Example credential headers:
```
X-User-Credential-API_KEY: sk-1234567890
X-User-Credential-WORKSPACE_ID: ws_abc123
```

### 3. Current Reclaim SDK Authentication

The Reclaim SDK currently uses:
- **Bearer Token**: Single API token authentication
- **Environment Variable**: `RECLAIM_TOKEN` or `configure()` method
- **Single Client**: Singleton pattern with persistent session

### 4. Required Conversions

To convert Reclaim SDK to MCP:

1. **Remove Singleton Pattern**: Make stateless, per-request clients
2. **Add HTTP Server**: Express.js server with MCP endpoints
3. **Credential Extraction**: Extract token from headers per request
4. **Tool Schema Definition**: Define Zod schemas for each operation
5. **Natural Language Interface**: Design tools for natural language input

## Authentication Plan

### Setup Flow
```typescript
// 1. Check if setup needed
GET /mcp/needs-setup
Response: {
  needs_setup: true,
  auth_type: "api_key",
  service_name: "Reclaim.ai"
}

// 2. Get setup instructions  
POST /mcp/tools/setup
Body: { action: "get_instructions" }

// 3. Validate credentials
POST /mcp/tools/setup
Body: { 
  action: "validate_credentials",
  credentials: { reclaim_api_key: "..." }
}
```

### Request Flow
```typescript
// Juli sends credentials in headers
POST /mcp/tools/create_task
Headers: {
  "X-User-Credential-RECLAIM_API_KEY": "user_token_here"
}
Body: {
  query: "Create a task to review Q4 budget by Friday"
}
```

### MCP Server extracts credentials:
```typescript
function extractCredentials(headers) {
  const credentials = {};
  for (const [key, value] of Object.entries(headers)) {
    if (key.startsWith('x-user-credential-')) {
      const credKey = key.replace('x-user-credential-', '');
      credentials[credKey] = value;
    }
  }
  return credentials;
}

// Create per-request client
const client = new ReclaimClient();
client.configure(credentials.RECLAIM_API_KEY);
```

## Tool Design

### Natural Language Tools

1. **manage_tasks**
   - Create, update, complete tasks
   - Natural language parsing
   - Smart defaults and scheduling

2. **find_tasks** 
   - Search and filter tasks
   - Status, priority, date filtering
   - Summary or detailed views

3. **schedule_work**
   - Block time for tasks
   - Adjust task durations
   - Handle scheduling conflicts

4. **task_insights**
   - Analytics and summaries
   - Overdue tasks
   - Workload analysis

## Next Steps

1. Set up Express.js server structure
2. Implement credential extraction middleware  
3. Create tool schemas with Zod
4. Build natural language processors
5. Implement stateless Reclaim client usage
6. Add setup flow for API key configuration
7. Create comprehensive tool implementations
8. Add error handling and user-friendly messages
9. Write tests and documentation
10. Deploy with Docker support