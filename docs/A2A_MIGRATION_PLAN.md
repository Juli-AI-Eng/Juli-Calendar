# A2A Migration Plan for Juli Calendar Agent

## Overview

This document outlines the migration from the current MCP REST-based system to the A2A (Agent-to-Agent) JSON-RPC protocol, following the Juli-Email implementation as reference.

## Current State Analysis

### Current Architecture (MCP REST)
- **Endpoint**: `/mcp/tools/{toolName}` (POST)
- **Authentication**: Credentials passed via headers (`X-User-Credential-*`)
- **Discovery**: `/mcp/tools` (GET)
- **Tools**: manage_productivity, check_availability, find_and_analyze
- **Server**: Python Flask application
- **Approval System**: Custom implementation returning `needs_approval: true`

### Target Architecture (A2A JSON-RPC)
- **RPC Endpoint**: `/a2a/rpc` (POST) - JSON-RPC 2.0
- **Discovery**: `/.well-known/a2a.json` (Agent Card)
- **Authentication**: OIDC ID tokens or dev secret
- **Methods**: 
  - `agent.card` - Get agent information
  - `agent.handshake` - Initial connection
  - `tool.execute` - Execute tool with arguments
  - `tool.approve` - Approve pending actions
- **Stateless**: No per-user state stored

## Migration Steps

### Phase 1: Infrastructure Setup

#### 1.1 Add A2A Discovery Endpoint
Create `/.well-known/a2a.json` endpoint that returns the Agent Card:

```python
@app.route('/.well-known/a2a.json')
def agent_card():
    return jsonify({
        "agent_id": "juli-calendar",
        "agent_name": "Juli Calendar Agent",
        "version": "2.0.0",
        "description": "AI-powered calendar and task management agent",
        "author": {
            "name": "Juli AI",
            "email": "support@juli-ai.com"
        },
        "capabilities": {
            "tools": [
                {
                    "name": "manage_productivity",
                    "description": "Create, update, and manage tasks and calendar events"
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
                    "header": "X-A2A-Dev-Secret"
                }
            ]
        },
        "rpc": {
            "endpoint": "/a2a/rpc",
            "version": "2.0"
        },
        "approvals": {
            "required_for": [
                "event_create_with_participants",
                "bulk_operation",
                "event_create_conflict_reschedule"
            ]
        },
        "context": {
            "injections": [
                "user_name",
                "user_email", 
                "user_timezone",
                "current_date",
                "current_time"
            ]
        },
        "server_time": datetime.utcnow().isoformat() + "Z"
    })
```

#### 1.2 Add Credentials Discovery Endpoint
Create `/.well-known/a2a-credentials.json` for credential acquisition:

```python
@app.route('/.well-known/a2a-credentials.json')
def credentials_manifest():
    return jsonify({
        "credentials": [
            {
                "key": "RECLAIM_API_KEY",
                "display_name": "Reclaim.ai API Key",
                "sensitive": True,
                "flows": [
                    {
                        "type": "api_key",
                        "instructions": "Get your API key from Reclaim.ai settings"
                    }
                ]
            },
            {
                "key": "NYLAS_GRANT_ID",
                "display_name": "Email Calendar Grant",
                "sensitive": True,
                "flows": [
                    {
                        "type": "hosted_auth",
                        "connect_url": "/setup/connect-url",
                        "callback": "/api/nylas-calendar/callback",
                        "provider_scopes": {
                            "google": [
                                "https://www.googleapis.com/auth/calendar",
                                "https://www.googleapis.com/auth/calendar.events"
                            ],
                            "microsoft": [
                                "Calendars.ReadWrite",
                                "Tasks.ReadWrite"
                            ]
                        }
                    }
                ]
            }
        ]
    })
```

### Phase 2: JSON-RPC Implementation

#### 2.1 Create A2A RPC Handler
Implement the main JSON-RPC endpoint:

```python
@app.route('/a2a/rpc', methods=['POST'])
async def a2a_rpc():
    """Handle A2A JSON-RPC requests."""
    
    # Authenticate agent
    if not authenticate_a2a_agent(request):
        return jsonify({
            "jsonrpc": "2.0",
            "id": request.json.get('id'),
            "error": {
                "code": 401,
                "message": "Unauthorized agent"
            }
        }), 401
    
    # Parse JSON-RPC request
    try:
        rpc_request = request.json
        method = rpc_request.get('method')
        params = rpc_request.get('params', {})
        request_id = rpc_request.get('id')
        
        # Route to appropriate handler
        if method == 'agent.card':
            result = get_agent_card()
        elif method == 'agent.handshake':
            result = agent_handshake()
        elif method == 'tool.execute':
            result = await execute_tool(params)
        elif method == 'tool.approve':
            result = await approve_tool(params)
        else:
            return jsonify({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            })
        
        return jsonify({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        })
        
    except Exception as e:
        logger.error(f"A2A RPC error: {e}")
        return jsonify({
            "jsonrpc": "2.0",
            "id": request.json.get('id'),
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }), 500
```

#### 2.2 Implement Authentication
Add OIDC and dev secret authentication:

```python
def authenticate_a2a_agent(request):
    """Authenticate incoming A2A agent requests."""
    
    # Check for dev secret (development only)
    dev_secret = request.headers.get('X-A2A-Dev-Secret')
    if dev_secret and dev_secret == os.getenv('A2A_DEV_SECRET'):
        return True
    
    # Check for OIDC token
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
        # TODO: Validate OIDC token with Juli auth service
        # For now, accept any bearer token in dev mode
        if os.getenv('FLASK_ENV') == 'development':
            return True
    
    return False
```

#### 2.3 Migrate Tool Execution
Convert tool execution to JSON-RPC format:

```python
async def execute_tool(params):
    """Execute a tool via JSON-RPC."""
    tool_name = params.get('tool')
    arguments = params.get('arguments', {})
    user_context = params.get('user_context', {})
    request_id = params.get('request_id')
    
    # Extract credentials from user_context
    credentials = user_context.get('credentials', {})
    
    # Map credentials to expected format
    mapped_credentials = {
        'reclaim_api_key': credentials.get('RECLAIM_API_KEY'),
        'nylas_api_key': os.getenv('NYLAS_API_KEY'),  # Server key
        'nylas_grant_id': credentials.get('NYLAS_GRANT_ID')
    }
    
    # Get the tool
    tool = get_tool_by_name(tool_name)
    if not tool:
        raise ValueError(f"Tool not found: {tool_name}")
    
    # Merge arguments with user context injections
    merged_params = {
        **arguments,
        'user_timezone': user_context.get('timezone', 'UTC'),
        'current_date': user_context.get('current_date'),
        'current_time': user_context.get('current_time')
    }
    
    # Execute the tool
    result = await tool.execute(merged_params, mapped_credentials)
    
    # Handle approval flows
    if result.get('needs_approval'):
        return {
            'needs_approval': True,
            'action_type': result['action_type'],
            'action_data': result['action_data'],
            'preview': result['preview'],
            'request_id': request_id
        }
    
    return result
```

### Phase 3: Tool Migration

#### 3.1 Update Tool Schemas
Convert tools to return JSON-RPC compatible schemas:

```python
class ManageProductivityTool(BaseTool):
    def get_a2a_schema(self):
        """Get A2A-compatible tool schema."""
        return {
            "name": "manage_productivity",
            "description": "Create, update, and manage tasks and calendar events using natural language",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of what you want to do"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context or details"
                    },
                    "approved": {
                        "type": "boolean",
                        "description": "Whether this is an approval of a previous action"
                    },
                    "action_data": {
                        "type": "object",
                        "description": "Data from a previous approval request"
                    }
                },
                "required": ["query"]
            }
        }
```

### Phase 4: Backwards Compatibility

#### 4.1 Maintain Legacy Endpoints
Keep existing MCP endpoints during transition:

```python
# Keep existing endpoint
@app.route('/mcp/tools/<tool_name>', methods=['POST'])
async def legacy_mcp_tool(tool_name):
    """Legacy MCP endpoint - redirect to A2A."""
    # Convert to A2A format
    params = {
        'tool': tool_name,
        'arguments': request.json,
        'user_context': {
            'credentials': extract_credentials_from_headers(request.headers),
            'timezone': request.json.get('user_timezone'),
            'current_date': request.json.get('current_date'),
            'current_time': request.json.get('current_time')
        }
    }
    
    # Execute via A2A handler
    result = await execute_tool(params)
    return jsonify(result)
```

### Phase 5: Testing

#### 5.1 Create A2A Test Suite
Add tests for A2A endpoints:

```python
def test_a2a_discovery():
    """Test A2A discovery endpoint."""
    response = client.get('/.well-known/a2a.json')
    assert response.status_code == 200
    data = response.json()
    assert data['agent_id'] == 'juli-calendar'
    assert '/a2a/rpc' in data['rpc']['endpoint']

def test_a2a_rpc_tool_execute():
    """Test tool execution via JSON-RPC."""
    response = client.post('/a2a/rpc', 
        headers={'X-A2A-Dev-Secret': 'test-secret'},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tool.execute",
            "params": {
                "tool": "manage_productivity",
                "arguments": {
                    "query": "Create a task to test A2A"
                },
                "user_context": {
                    "credentials": {
                        "RECLAIM_API_KEY": "test-key"
                    }
                }
            }
        }
    )
    assert response.status_code == 200
    assert 'result' in response.json()
```

### Phase 6: Documentation

#### 6.1 Update README
- Add A2A quickstart section
- Update authentication docs
- Add JSON-RPC examples

#### 6.2 Create A2A Developer Guide
- Document all JSON-RPC methods
- Provide integration examples
- Include troubleshooting guide

## Migration Timeline

### Week 1: Infrastructure
- [ ] Implement discovery endpoints
- [ ] Add JSON-RPC handler
- [ ] Setup authentication

### Week 2: Tool Migration
- [ ] Convert manage_productivity tool
- [ ] Convert check_availability tool
- [ ] Convert find_and_analyze tool

### Week 3: Testing & Documentation
- [ ] Create comprehensive test suite
- [ ] Update all documentation
- [ ] Test with Juli Brain

### Week 4: Deployment
- [ ] Deploy to staging
- [ ] Test with real Juli Brain
- [ ] Deploy to production

## Key Differences from Current System

### 1. Stateless Design
- No user sessions stored
- Credentials passed per request
- All state in request/response

### 2. JSON-RPC Format
```python
# Old (REST)
POST /mcp/tools/manage_productivity
Body: {"query": "Create task"}

# New (JSON-RPC)
POST /a2a/rpc
Body: {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tool.execute",
    "params": {
        "tool": "manage_productivity",
        "arguments": {"query": "Create task"}
    }
}
```

### 3. Authentication
- OIDC tokens instead of just credential headers
- Dev secret for development
- Agent-to-agent authentication

### 4. Discovery
- Agent Card at `/.well-known/a2a.json`
- Credentials manifest at `/.well-known/a2a-credentials.json`
- No more `/mcp/tools` discovery

## Success Criteria

1. All tools accessible via A2A JSON-RPC
2. Backwards compatibility maintained
3. Authentication working with Juli Brain
4. All tests passing
5. Documentation complete
6. Successfully integrated with Juli Brain

## Risks and Mitigations

### Risk 1: Breaking Changes
**Mitigation**: Maintain legacy endpoints during transition

### Risk 2: Authentication Issues
**Mitigation**: Support both old and new auth methods initially

### Risk 3: Data Format Incompatibilities
**Mitigation**: Create adapters to convert between formats

## Next Steps

1. Review this plan with team
2. Set up development environment
3. Begin Phase 1 implementation
4. Create tracking issues for each phase

## References

- [Juli-Email A2A Implementation](https://github.com/Juli-AI-Eng/Juli-Email)
- [MCP Developer Guide](https://github.com/Juli-AI-Eng/Juli-Email/blob/main/docs/MCP_DEVELOPER_GUIDE.md)
- [A2A Protocol Specification](https://modelcontextprotocol.io)