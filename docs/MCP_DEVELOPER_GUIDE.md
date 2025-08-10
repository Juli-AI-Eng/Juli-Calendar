# MCP Developer Guide for Juli Platform

A comprehensive guide to building Model Context Protocol (MCP) servers for Juli - the AI platform used by thousands of users worldwide.

## Table of Contents
- [Overview](#overview)
- [Juli Authentication System](#juli-authentication-system)
- [MCP Protocol Specification](#mcp-protocol-specification)
- [Building Your MCP Server](#building-your-mcp-server)
- [Tool Design Best Practices](#tool-design-best-practices)
- [Testing and Deployment](#testing-and-deployment)

## Overview

### What is Juli?

Juli is an AI platform that orchestrates multiple AI models and tools to help users accomplish complex tasks. MCP servers extend Juli's capabilities by providing specialized tools that integrate with external services.

### What is MCP?

Model Context Protocol (MCP) is a standardized way for AI systems to interact with external tools and services. It defines:
- How tools are discovered and described
- How requests and responses are formatted
- How authentication and context are handled
- How approvals and safety checks work

### Why Build for Juli?

- **Reach thousands of users** - Juli's growing user base needs quality tools
- **Monetization** - Premium MCP servers can generate revenue
- **Simple integration** - Juli handles all the complex infrastructure
- **Focus on your expertise** - Build tools in domains you know best

## Juli Authentication System

### How Juli Handles Credentials

Juli implements a secure, user-friendly authentication system that makes using MCP servers seamless:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   Juli Client   │────▶│  Juli Platform  │────▶│   MCP Server    │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                         │
        │                       │                         │
    User provides           Stores & manages         Receives creds
    credentials once        credentials              per request
```

### Credential Types

Juli supports multiple credential patterns:

#### 1. API Key Pattern
```typescript
// User provides
{
  "api_key": "sk-1234567890abcdef"
}

// Juli sends in headers
headers: {
  "X-User-Credential-API_KEY": "sk-1234567890abcdef"
}
```

#### 2. Multi-Field Pattern
```typescript
// User provides
{
  "client_id": "your-app-id",
  "client_secret": "your-app-secret",
  "workspace_id": "user-workspace"
}

// Juli sends in headers
headers: {
  "X-User-Credential-CLIENT_ID": "your-app-id",
  "X-User-Credential-CLIENT_SECRET": "your-app-secret",
  "X-User-Credential-WORKSPACE_ID": "user-workspace"
}
```

#### 3. OAuth2 Pattern
```typescript
// User completes OAuth flow
{
  "access_token": "bearer-token",
  "refresh_token": "refresh-token",
  "expires_at": 1234567890
}

// Juli handles refresh automatically
headers: {
  "X-User-Credential-ACCESS_TOKEN": "bearer-token"
}
```

### Setup Flow

When a user first installs your MCP:

```typescript
// 1. Juli calls your needs-setup endpoint
GET /mcp/needs-setup
Response: {
  "needs_setup": true,
  "auth_type": "api_key",
  "setup_url": "/mcp/tools/setup",
  "service_name": "Your Service"
}

// 2. User runs setup tool
POST /mcp/tools/setup
Body: {
  "action": "get_instructions"
}
Response: {
  "type": "setup_instructions",
  "steps": [...],
  "validation_endpoint": "validate_credentials"
}

// 3. User provides credentials
POST /mcp/tools/setup
Body: {
  "action": "validate_credentials",
  "credentials": {
    "api_key": "provided-key"
  }
}
Response: {
  "valid": true,
  "credentials_to_store": {
    "api_key": "provided-key"
  }
}

// 4. Juli stores credentials securely
// All future requests include them automatically
```

## MCP Protocol Specification

### Request Format

All tool execution requests follow this format:

```typescript
POST /mcp/tools/{toolName}
Headers: {
  "Content-Type": "application/json",
  "X-Request-ID": "unique-request-id",
  "X-User-ID": "juli-user-id",
  "X-User-Credential-*": "credential-values"
}
Body: {
  // Tool-specific parameters
  "param1": "value1",
  "param2": "value2",
  
  // Context injection (if configured)
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "user_timezone": "America/New_York"
}
```

### Response Format

#### Success Response
```typescript
{
  "success": true,
  "data": {
    // Tool-specific response data
  },
  "metadata": {
    "duration_ms": 234,
    "tokens_used": 150
  }
}
```

#### Error Response
```typescript
{
  "error": "User-friendly error message",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "details": {
    "retry_after": 60,
    "limit": 100,
    "current": 101
  }
}
```

#### Needs Setup Response
```typescript
{
  "needs_setup": true,
  "message": "Please complete setup to use this tool",
  "setup_tool": "setup_service"
}
```

#### Approval Required Response
```typescript
{
  "needs_approval": true,
  "action_type": "delete_data",
  "action_data": {
    // Complete data needed to execute action
  },
  "preview": {
    "summary": "Delete 42 old records",
    "details": {
      "records_affected": 42,
      "oldest_date": "2023-01-01"
    },
    "risks": ["This action cannot be undone"]
  }
}
```

### Tool Discovery Format

```typescript
GET /mcp/tools
Response: {
  "tools": [
    {
      "name": "tool_name",
      "description": "Clear description of what this tool does",
      "inputSchema": {
        "type": "object",
        "properties": {
          "param1": {
            "type": "string",
            "description": "What this parameter does"
          },
          "param2": {
            "type": "number",
            "description": "Another parameter",
            "minimum": 0,
            "maximum": 100
          }
        },
        "required": ["param1"]
      }
    }
  ]
}
```

### Context Injection

Juli can automatically inject user context into tool calls:

```typescript
// In your tool schema
"inputSchema": {
  "type": "object",
  "properties": {
    "message": {
      "type": "string",
      "description": "Message to send"
    },
    "user_name": {
      "type": "string",
      "description": "User's name",
      "x-context-injection": "user_name"  // Juli auto-fills
    },
    "user_timezone": {
      "type": "string",
      "description": "User's timezone",
      "x-context-injection": "user_timezone"
    }
  }
}
```

Available context fields:
- `user_name` - User's display name
- `user_email` - User's email address
- `user_timezone` - User's timezone (e.g., "America/New_York")
- `current_date` - Current date in user's timezone
- `current_time` - Current time in user's timezone

## Building Your MCP Server

### Server Architecture

```typescript
import express from 'express';
import { z } from 'zod';

class MCPServer {
  private app: express.Application;
  private tools: Map<string, Tool>;
  
  constructor() {
    this.app = express();
    this.tools = new Map();
    this.setupMiddleware();
    this.setupRoutes();
  }
  
  private setupMiddleware() {
    this.app.use(express.json());
    this.app.use(this.logRequests);
    this.app.use(this.extractCredentials);
  }
  
  private extractCredentials(req, res, next) {
    req.credentials = {};
    
    // Extract all X-User-Credential-* headers
    Object.keys(req.headers).forEach(header => {
      if (header.startsWith('x-user-credential-')) {
        const credName = header.replace('x-user-credential-', '');
        req.credentials[credName] = req.headers[header];
      }
    });
    
    next();
  }
  
  private setupRoutes() {
    this.app.get('/health', (req, res) => {
      res.json({ status: 'healthy', version: '1.0.0' });
    });
    
    this.app.get('/mcp/needs-setup', (req, res) => {
      const needsSetup = !this.hasRequiredCredentials(req.credentials);
      res.json({
        needs_setup: needsSetup,
        auth_type: 'api_key',
        service_name: 'Your Service',
        setup_tool: 'setup_service'
      });
    });
    
    this.app.get('/mcp/tools', (req, res) => {
      const tools = Array.from(this.tools.values()).map(tool => ({
        name: tool.name,
        description: tool.description,
        inputSchema: tool.getSchema()
      }));
      res.json({ tools });
    });
    
    this.app.post('/mcp/tools/:toolName', async (req, res) => {
      try {
        const { toolName } = req.params;
        const tool = this.tools.get(toolName);
        
        if (!tool) {
          return res.status(404).json({
            error: `Tool '${toolName}' not found`
          });
        }
        
        // Check credentials
        if (!this.hasRequiredCredentials(req.credentials)) {
          return res.json({
            needs_setup: true,
            message: 'Please complete setup first',
            setup_tool: 'setup_service'
          });
        }
        
        // Validate input
        const validatedInput = tool.validateInput(req.body);
        
        // Execute tool
        const result = await tool.execute(validatedInput, req.credentials);
        
        res.json(result);
      } catch (error) {
        console.error(`Error in tool ${req.params.toolName}:`, error);
        res.status(500).json({
          error: 'An error occurred processing your request',
          error_code: 'INTERNAL_ERROR'
        });
      }
    });
  }
}
```

### Tool Implementation Pattern

```typescript
abstract class Tool {
  constructor(
    public name: string,
    public description: string
  ) {}
  
  abstract getSchema(): object;
  abstract validateInput(input: any): any;
  abstract execute(input: any, credentials: any): Promise<any>;
}

class ExampleTool extends Tool {
  constructor() {
    super(
      'example_tool',
      'Does something useful with natural language'
    );
  }
  
  getSchema() {
    return {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Natural language description of what you want'
        },
        options: {
          type: 'object',
          properties: {
            include_details: {
              type: 'boolean',
              default: false
            }
          }
        }
      },
      required: ['query']
    };
  }
  
  validateInput(input: any) {
    // Use zod or another validator
    const schema = z.object({
      query: z.string().min(1),
      options: z.object({
        include_details: z.boolean().optional()
      }).optional()
    });
    
    return schema.parse(input);
  }
  
  async execute(input: any, credentials: any) {
    // Create service client with credentials
    const client = new YourServiceClient({
      apiKey: credentials.api_key
    });
    
    try {
      // Process natural language
      const intent = await this.understandQuery(input.query);
      
      // Execute action
      const result = await client.doSomething(intent);
      
      return {
        success: true,
        data: result
      };
    } catch (error) {
      if (error.code === 'RATE_LIMIT') {
        return {
          error: 'Rate limit exceeded. Please try again later.',
          error_code: 'RATE_LIMIT_EXCEEDED',
          details: {
            retry_after: 60
          }
        };
      }
      throw error;
    }
  }
}
```

### Stateless Design Principles

1. **No Session State**
   ```typescript
   // ❌ Bad: Storing user state
   const userSessions = new Map();
   
   // ✅ Good: Everything in request
   function handleRequest(req) {
     const credentials = req.credentials;
     const client = createClient(credentials);
     return client.doWork();
   }
   ```

2. **Request-Scoped Clients**
   ```typescript
   // ❌ Bad: Global client
   const client = new ServiceClient(process.env.API_KEY);
   
   // ✅ Good: Per-request client
   function handleRequest(req) {
     const client = new ServiceClient(req.credentials.api_key);
     return client.doWork();
   }
   ```

3. **Horizontal Scaling Ready**
   ```typescript
   // Your server should work with multiple instances
   // No in-memory caches for user data
   // No local file storage for user content
   // Use external services for persistence if needed
   ```

## Tool Design Best Practices

### 1. Natural Language First

```typescript
// ❌ Bad: Technical parameters
{
  name: "execute_query",
  parameters: {
    sql: "SELECT * FROM users WHERE...",
    database: "production",
    timeout: 30000
  }
}

// ✅ Good: Natural language
{
  name: "find_data",
  parameters: {
    query: "Show me active users from last week",
    include_details: true
  }
}
```

### 2. Progressive Disclosure

```typescript
// Start simple
{
  name: "analyze_data",
  parameters: {
    query: "What are my top selling products?"
  }
}

// Allow advanced options
{
  name: "analyze_data",
  parameters: {
    query: "What are my top selling products?",
    options: {
      time_range: "last_quarter",
      group_by: "category",
      include_trends: true
    }
  }
}
```

### 3. Clear Descriptions

```typescript
{
  name: "manage_email",
  description: "Send, reply, forward, or draft emails using natural language. Handles all email composition intelligently.",
  inputSchema: {
    type: "object",
    properties: {
      action: {
        type: "string",
        enum: ["send", "reply", "forward", "draft"],
        description: "What to do with the email"
      },
      query: {
        type: "string",
        description: "Natural language description. Examples: 'reply to Sarah thanking her for the proposal', 'forward the AWS alerts to the dev team with a summary'"
      }
    }
  }
}
```

### 4. Error Messages Users Understand

```typescript
// ❌ Bad: Technical errors
{
  error: "Connection timeout: ETIMEDOUT 192.168.1.1:5432"
}

// ✅ Good: User-friendly errors
{
  error: "Unable to connect to your database. Please check if your database is online and accessible.",
  error_code: "DATABASE_UNAVAILABLE",
  details: {
    suggestion: "Try again in a few moments or contact your database administrator"
  }
}
```

### 5. Approval Flow for Sensitive Actions

```typescript
async function deleteData(params, credentials) {
  // Calculate impact
  const itemsToDelete = await findItems(params.filter);
  
  // Request approval for large deletions
  if (itemsToDelete.length > 10) {
    return {
      needs_approval: true,
      action_type: 'bulk_delete',
      action_data: {
        filter: params.filter,
        ids: itemsToDelete.map(i => i.id)
      },
      preview: {
        summary: `Delete ${itemsToDelete.length} items`,
        details: {
          oldest_item: itemsToDelete[0].created_at,
          newest_item: itemsToDelete[itemsToDelete.length - 1].created_at
        },
        risks: ['This action cannot be undone']
      }
    };
  }
  
  // Execute for small deletions
  await performDelete(itemsToDelete);
  return {
    success: true,
    message: `Deleted ${itemsToDelete.length} items`
  };
}
```

## Testing and Deployment

### Testing Your MCP

```typescript
// Test the full flow
describe('MCP Server', () => {
  it('should handle the complete setup flow', async () => {
    // 1. Check needs setup
    const needsSetup = await fetch('/mcp/needs-setup');
    expect(needsSetup.body.needs_setup).toBe(true);
    
    // 2. Get instructions
    const instructions = await fetch('/mcp/tools/setup', {
      method: 'POST',
      body: { action: 'get_instructions' }
    });
    expect(instructions.body.steps).toHaveLength(3);
    
    // 3. Validate credentials
    const validation = await fetch('/mcp/tools/setup', {
      method: 'POST',
      body: {
        action: 'validate_credentials',
        credentials: { api_key: 'test-key' }
      }
    });
    expect(validation.body.valid).toBe(true);
  });
  
  it('should execute tools with credentials', async () => {
    const response = await fetch('/mcp/tools/my_tool', {
      method: 'POST',
      headers: {
        'X-User-Credential-API_KEY': 'test-key'
      },
      body: {
        query: 'test query'
      }
    });
    
    expect(response.body.success).toBe(true);
  });
});
```

### Docker Deployment

```dockerfile
# Multi-stage build for efficiency
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production image
FROM node:20-alpine
RUN apk add --no-cache tini
WORKDIR /app

# Copy only production dependencies
COPY package*.json ./
RUN npm ci --production && npm cache clean --force

# Copy built app
COPY --from=builder /app/dist ./dist

# Run as non-root
USER node

# Use tini for proper signal handling
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "dist/server.js"]

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"
```

### Production Checklist

- [ ] Comprehensive error handling
- [ ] Rate limiting implementation
- [ ] Request validation
- [ ] Secure credential handling
- [ ] Health check endpoint
- [ ] Structured logging
- [ ] Monitoring and metrics
- [ ] Graceful shutdown
- [ ] Documentation complete
- [ ] Security review passed

## Publishing to Juli

### Requirements

1. **Functional Requirements**
   - All tools must have clear descriptions
   - Natural language processing required
   - Proper error handling
   - Setup flow must be user-friendly

2. **Technical Requirements**
   - HTTP-only server (no WebSocket)
   - Stateless operation
   - Docker support recommended
   - Health check endpoint required

3. **Documentation Requirements**
   - README with clear examples
   - API documentation
   - Setup instructions
   - Troubleshooting guide

### Submission Process

1. Test thoroughly with multiple accounts
3. Submit via Juli Developer Portal
4. Respond to review feedback
5. Launch to thousands of users!

## Common Patterns

### Multi-Service Integration
```typescript
// When your MCP needs multiple API keys
headers: {
  'X-User-Credential-OPENAI_KEY': 'sk-...',
  'X-User-Credential-SERVICE_KEY': 'svc_...',
  'X-User-Credential-WORKSPACE': 'ws_123'
}
```

### Webhook Support
```typescript
// Register webhooks with callback URL
const callbackUrl = `https://juli-webhooks.com/mcp/${req.userId}/${toolName}`;
await client.registerWebhook(callbackUrl);
```

### Batch Operations
```typescript
// Process multiple items efficiently
{
  name: "bulk_process",
  parameters: {
    items: ["item1", "item2", "item3"],
    operation: "analyze"
  }
}
```

## Conclusion

Building MCP servers for Juli opens your tools to thousands of users who need specialized capabilities. Focus on:

1. **User Experience** - Natural language, clear errors, smooth setup
2. **Reliability** - Proper error handling, stateless design, monitoring
3. **Security** - Never store credentials, validate all input
4. **Performance** - Efficient operations, proper timeouts, scaling ready

Your MCP server will help Juli users be more productive and accomplish amazing things. Welcome to the Juli developer community!

## Resources

- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Juli Developer Portal](https://juli-ai.com/developers)
- [Support](ignacio@juli-ai.com)