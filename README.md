# Juli Calendar Agent - MCP Server

An intelligent calendar and task management agent that seamlessly integrates Reclaim.ai (for smart task scheduling) and Nylas (for universal calendar access). Built as an MCP (Model Context Protocol) server for Juli AI, it uses OpenAI GPT-5 to understand natural language and handle complex scheduling operations.

## Key Features

### 🤖 Intelligent Natural Language Understanding
- **GPT-5 Integration**: Uses OpenAI's latest model with strict schema validation for reliable parsing
- **Smart Routing**: Automatically determines whether to create a task (Reclaim.ai) or calendar event (Nylas)
- **Context Awareness**: Understands time zones, relative dates ("tomorrow at 2pm"), and participant mentions

### 📋 Task Management (via Reclaim.ai)
- Create, update, complete, and delete tasks with natural language
- Smart scheduling that works around your calendar
- Priority-based task management (P1-P4)
- Duration estimation and due date handling

### 📅 Calendar Events (via Nylas)
- Universal calendar support (Google Calendar, Outlook, iCloud, and more)
- Create meetings with participants (with approval flow)
- Cancel and reschedule events
- Participant email validation and handling

### ✅ Safety & Approval System
- **Participant Protection**: Events with other people require explicit approval
- **Bulk Operation Safety**: Mass deletions/updates need confirmation
- **Duplicate Detection**: Smart detection prevents accidental duplicates (with numbered sequence support)
- **Conflict Resolution**: Identifies scheduling conflicts and suggests alternatives

### 🔍 Advanced Features
- **Availability Checking**: Find free time slots across both tasks and calendar
- **Schedule Optimization**: AI-powered suggestions for better time management
- **Workload Analysis**: Understand your productivity patterns
- **Semantic Search**: Find tasks and events using natural language

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/Juli-AI-Eng/Juli-Calendar.git
   cd Juli-Calendar
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

4. **Run the server**
   ```bash
   # Production mode
   python scripts/run_server.py --mode prod --port 5000

   # E2E testing mode
   python scripts/run_server.py --mode e2e --port 5002
   ```

5. **Connect via Juli**
   - The server will be available at `http://localhost:5002`
   - Juli will handle credential injection for Reclaim.ai and Nylas

## Architecture

This MCP server acts as an intelligent bridge between Juli AI and your productivity tools:

```
User → Juli → MCP Server → GPT-5 Intent Router → Reclaim.ai (tasks)
                                              → Nylas (calendar events)
```

The system uses multiple specialized AI components:
- **Intent Router**: Determines task vs. event and extracts basic information
- **TaskAI**: Specialized parser for Reclaim.ai task operations
- **EventAI**: Specialized parser for Nylas calendar events
- **Approval System**: Enforces safety checks for sensitive operations

## Tools Available

### 🎯 manage_productivity
Manage all aspects of your productivity with natural language:
- Create and track tasks
- Schedule meetings and appointments
- Check availability
- Block time for focused work

### 🔍 find_and_analyze
Search and analyze your productivity data:
- Find tasks and events
- Analyze workload patterns
- Get productivity insights
- Track project progress

### 📊 check_availability
Check availability and find free time:
- Check specific time slots
- Find available meeting times
- Identify scheduling conflicts
- Get smart suggestions

### ⚡ optimize_schedule
Optimize your schedule intelligently:
- Rebalance workload
- Find optimal times for tasks
- Resolve scheduling conflicts
- Create optimization action plans

## Setup Guide

### Prerequisites

1. **Reclaim.ai Account**: Sign up at [app.reclaim.ai](https://app.reclaim.ai)
2. **Nylas Account**: Sign up at [dashboard.nylas.com](https://dashboard-v3.nylas.com/register?utm_source=juli) (free tier available)
3. **OpenAI API Key**: For AI functionality

### Detailed Setup

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed setup instructions.

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# E2E tests (requires real API credentials in .env.test)
pytest tests/e2e -v
```

### Project Structure

```
├── src/
│   ├── server.py          # Main Flask server
│   ├── ai/                # AI components (routing, NLU)
│   ├── tools/             # MCP tool implementations
│   └── auth/              # Authentication handling
├── tests/                 # Test suites
├── scripts/               # Utility scripts
├── manual_tests/          # Manual testing scripts
└── juli-toolkit-config.json  # Juli integration config
```

## Documentation

- [Tools Documentation](docs/TOOLS_DOCUMENTATION.md) - Tool schemas and examples
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- [Development Guide](docs/MCP_DEVELOPER_GUIDE.md) - Contributing guidelines
- [Approval System](docs/APPROVAL_SYSTEM_GUIDE.md) - How approval flows work
- [OpenAI Function Calling](docs/FUNCTION_CALLING_OPENAI.md) - GPT-5 integration details

## Security

- **No stored credentials**: User credentials are injected per-request via headers
- **Approval flows**: Sensitive operations require explicit approval
- **Secure by design**: Following MCP best practices

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [troubleshooting guide](DEPLOYMENT.md#troubleshooting)
- Review the [documentation](docs/)