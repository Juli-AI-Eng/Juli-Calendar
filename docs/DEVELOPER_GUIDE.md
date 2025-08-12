# Developer Guide

This guide provides comprehensive information for developers working with or contributing to the Juli Calendar Agent.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Principles](#core-principles)
3. [Project Structure](#project-structure)
4. [AI Integration](#ai-integration)
5. [Tool Development](#tool-development)
6. [A2A Protocol Implementation](#a2a-protocol-implementation)
7. [Testing Strategy](#testing-strategy)
8. [Contributing](#contributing)

## Architecture Overview

The Juli Calendar Agent follows a stateless, microservice architecture designed for scalability and maintainability.

```
┌─────────────────────────────────────────────────────────┐
│                      Juli Brain                         │
│                   (Orchestrator)                        │
└────────────────────────┬────────────────────────────────┘
                         │ JSON-RPC 2.0
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Calendar Agent                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │                A2A Protocol Layer               │   │
│  │  • Discovery (.well-known/a2a.json)            │   │
│  │  • Authentication (OIDC/Dev Secret)            │   │
│  │  • JSON-RPC Handler                            │   │
│  └──────────────────────┬──────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────┐   │
│  │                 Tool System                     │   │
│  │  • manage_productivity (Tasks & Events)        │   │
│  │  • find_and_analyze (Search & Analytics)       │   │
│  │  • check_availability (Calendar Availability)  │   │
│  │  • optimize_schedule (AI Optimization)         │   │
│  └──────────────────────┬──────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────┐   │
│  │              AI & Intent Layer                  │   │
│  │  • Intent Router (GPT-5)                       │   │
│  │  • TaskAI (Task Intelligence)                  │   │
│  │  • EventAI (Event Intelligence)                │   │
│  └──────────────────────┬──────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────┐   │
│  │           Integration Layer                     │   │
│  │  • Reclaim.ai Client (Tasks)                   │   │
│  │  • Nylas Client (Calendar)                     │   │
│  │  • Approval System                             │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

## Core Principles

### 1. Limit Your Toolkit to 5 Tools or Fewer

We maintain exactly 4 tools to keep the agent focused and prevent confusion:
- `manage_productivity`: Create, update, delete tasks and events
- `find_and_analyze`: Search and analyze calendar data
- `check_availability`: Check free/busy times
- `optimize_schedule`: AI-powered schedule optimization

### 2. Write Crystal Clear Descriptions

Every tool, parameter, and function must have clear, concise descriptions:

```python
class ManageProductivityTool(BaseTool):
    """
    Manages tasks and calendar events using natural language.
    Handles creation, updates, deletions, and modifications.
    """
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": "manage_productivity",
            "description": "Create, update, or delete tasks and calendar events",
            "parameters": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "delete", "list"],
                    "description": "The action to perform"
                },
                "query": {
                    "type": "string",
                    "description": "Natural language description of what to do"
                }
            }
        }
```

### 3. Stateless Architecture

The agent maintains no session state. All context is injected per request:

```python
def execute_tool_rpc(params: Dict[str, Any]) -> Dict[str, Any]:
    # Extract credentials from each request
    credentials = extract_credentials_from_context(params['user_context'])
    
    # Merge context with arguments
    merged_params = merge_context_with_arguments(
        params['arguments'],
        params['user_context']
    )
    
    # Execute tool with injected context
    return tool.execute(merged_params, credentials)
```

### 4. Natural Language First

All tools accept natural language queries processed by GPT-4:

```python
def process_natural_language(query: str) -> Dict[str, Any]:
    """Convert natural language to structured parameters."""
    intent_router = IntentRouter()
    return intent_router.analyze_intent(query)
```

## Project Structure

```
juli-calendar-agent/
├── src/
│   ├── a2a/                 # A2A protocol implementation
│   │   ├── __init__.py
│   │   ├── handlers.py      # JSON-RPC handlers
│   │   └── tool_adapter.py  # Tool execution adapter
│   │
│   ├── ai/                  # AI integration layer
│   │   ├── __init__.py
│   │   ├── intent_router.py # Natural language routing
│   │   ├── openai_utils.py  # OpenAI API utilities
│   │   ├── task_ai.py       # Task-specific AI
│   │   └── event_ai.py      # Event-specific AI
│   │
│   ├── tools/               # Tool implementations
│   │   ├── __init__.py
│   │   ├── base.py          # Base tool class
│   │   ├── manage_productivity.py
│   │   ├── find_and_analyze.py
│   │   ├── check_availability.py
│   │   └── optimize_schedule.py
│   │
│   ├── auth/                # Authentication
│   │   └── credential_manager.py
│   │
│   └── server.py            # Flask server
│
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── e2e/                 # End-to-end tests
│
├── docs/                    # Documentation
├── examples/                # Example scripts
└── scripts/                 # Utility scripts
```

## AI Integration

### Intent Router

The Intent Router uses GPT-5 to understand natural language and route to appropriate actions:

```python
class IntentRouter:
    def analyze_intent(self, query: str) -> Dict[str, Any]:
        """Analyze user intent from natural language."""
        
        # Use GPT-4 with function calling
        response = self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            functions=self.get_intent_functions(),
            function_call="auto"
        )
        
        return self.parse_function_call(response)
```

### Context Injection

Every AI call includes user context for better understanding:

```python
def build_context(user_context: Dict[str, Any]) -> str:
    """Build context string for AI."""
    return f"""
    Current date: {user_context.get('current_date')}
    User timezone: {user_context.get('timezone')}
    User name: {user_context.get('user_name', 'User')}
    """
```

## Tool Development

### Creating a New Tool

1. **Extend BaseTool**:
```python
from src.tools.base import BaseTool

class MyNewTool(BaseTool):
    def get_name(self) -> str:
        return "my_new_tool"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.get_name(),
            "description": "Clear description of what this tool does",
            "parameters": {
                # Define parameters
            }
        }
    
    def execute(self, params: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
        # Implementation
        pass
```

2. **Register the Tool**:
```python
# In src/tools/__init__.py
AVAILABLE_TOOLS = {
    "my_new_tool": MyNewTool(),
    # ... other tools
}
```

3. **Add to Agent Card**:
```python
# In src/a2a/handlers.py
def get_agent_card():
    return {
        "capabilities": {
            "tools": [
                {
                    "name": "my_new_tool",
                    "description": "..."
                },
                # ... other tools
            ]
        }
    }
```

### Approval Flows

For operations that affect others or may cause conflicts:

```python
def execute(self, params: Dict[str, Any], credentials: Dict[str, str]) -> Dict[str, Any]:
    # Check if approval is needed
    if self._needs_approval(params):
        return {
            "needs_approval": True,
            "approval_context": {
                "action": "create_event_with_participants",
                "preview": self._generate_preview(params),
                "warnings": ["This will send invitations to 5 people"]
            }
        }
    
    # Execute the action
    return self._perform_action(params, credentials)
```

## A2A Protocol Implementation

### Discovery Endpoint

```python
@app.route("/.well-known/a2a.json", methods=["GET"])
def a2a_discovery():
    """Return the Agent Card for discovery."""
    return jsonify(get_agent_card())
```

### Authentication

```python
def authenticate_agent(request: Request) -> bool:
    """Authenticate incoming A2A requests."""
    
    # Development authentication
    dev_secret = request.headers.get('X-A2A-Dev-Secret')
    if dev_secret == os.getenv('A2A_DEV_SECRET'):
        return True
    
    # OIDC authentication
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return validate_oidc_token(token)
    
    return False
```

### JSON-RPC Handler

```python
@app.route("/a2a/rpc", methods=["POST"])
def a2a_rpc():
    """Handle JSON-RPC 2.0 requests."""
    
    if not authenticate_agent(request):
        return jsonify({
            "jsonrpc": "2.0",
            "id": request.json.get('id'),
            "error": {
                "code": -32000,
                "message": "Unauthorized"
            }
        }), 401
    
    # Route to appropriate handler
    method = request.json.get('method')
    if method == 'tool.execute':
        result = execute_tool_rpc(request.json.get('params'))
    elif method == 'tool.approve':
        result = approve_tool_rpc(request.json.get('params'))
    else:
        # ... handle other methods
    
    return jsonify({
        "jsonrpc": "2.0",
        "id": request.json.get('id'),
        "result": result
    })
```

## Testing Strategy

### Unit Tests

Test individual components in isolation:

```python
def test_intent_router_create_task():
    router = IntentRouter()
    result = router.analyze_intent("Create a task to review the proposal")
    
    assert result['action'] == 'create'
    assert result['item_type'] == 'task'
    assert 'review the proposal' in result['title']
```

### Integration Tests

Test component interactions:

```python
def test_task_creation_flow():
    # Test the full flow from intent to Reclaim API
    tool = ManageProductivityTool()
    result = tool.execute({
        "action": "create",
        "query": "Create a task to review the proposal"
    }, credentials)
    
    assert result['success'] is True
    assert result['item']['type'] == 'TASK'
```

### E2E Tests

Test complete user scenarios:

```python
def test_complete_task_workflow():
    # 1. Create a task
    # 2. Update it
    # 3. Mark it complete
    # 4. Verify it appears in completed list
    pass
```

## Contributing

### Development Setup

1. Fork and clone the repository
2. Create a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Install pre-commit hooks: `pre-commit install`

### Code Style

- Use Black for formatting: `black src/ tests/`
- Type hints for all functions
- Docstrings for all public methods
- Maximum line length: 100 characters

### Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Write tests for your changes
3. Ensure all tests pass: `pytest`
4. Update documentation if needed
5. Submit a pull request with clear description

### Testing Requirements

- All new features must have unit tests
- Integration tests for external API interactions
- E2E tests for user-facing workflows
- Minimum 80% code coverage

## Best Practices

### Error Handling

```python
try:
    result = external_api_call()
except ExternalAPIError as e:
    logger.error(f"API call failed: {e}")
    return {
        "success": False,
        "error": "Service temporarily unavailable",
        "error_code": "SERVICE_ERROR"
    }
```

### Logging

```python
logger.info(f"Creating task: {task_title}")
logger.debug(f"Full task details: {task_data}")
logger.error(f"Failed to create task: {error}")
```

### Security

- Never log sensitive data (API keys, user credentials)
- Validate all input data
- Use parameterized queries
- Implement rate limiting
- Follow OWASP guidelines

## Resources

- [A2A Protocol Specification](A2A_DEVELOPER_GUIDE.md)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Reclaim.ai API Docs](https://api.reclaim.ai/docs)
- [Nylas API Docs](https://developer.nylas.com/docs/v3/)

## Support

For questions or issues:
- Check existing [GitHub Issues](https://github.com/Juli-AI/juli-calendar-agent/issues)
- Join our [Discord community](https://discord.gg/juli-ai)
- Email: [support@juli.ai](mailto:support@juli.ai)