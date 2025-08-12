# Juli Calendar Agent

An A2A (Agent-to-Agent) JSON-RPC agent for Juli that provides AI-powered calendar and task management. This agent intelligently combines Reclaim.ai for task management with Nylas for calendar operations, creating a comprehensive productivity assistant.

## 🌟 What it does

- **Smart Task Management**: Create, update, and manage tasks with natural language
- **Calendar Intelligence**: Check availability, schedule events, and manage conflicts
- **Unified Productivity**: Seamlessly integrates tasks and calendar events
- **AI-Powered**: Uses GPT-4 for intelligent scheduling and natural language understanding
- **Approval Flows**: Built-in approval system for sensitive operations

## 🚀 For Juli Users

Juli Calendar Agent is available as an official Juli integration. To use it:

1. Open Juli and navigate to the Agents section
2. Find "Calendar & Tasks" and click Connect
3. Follow the OAuth flow to connect your calendar (Google, Microsoft, or iCloud)
4. Connect your Reclaim.ai account for task management
5. Start using natural language commands like:
   - "Schedule a meeting with Sarah tomorrow at 2pm"
   - "Create a task to review the proposal by Friday"
   - "What's my availability next week?"
   - "Move my 3pm meeting to Thursday"

## 🛠️ For Developers

This repository serves as a reference implementation for building A2A agents for Juli. It demonstrates:

- **A2A Protocol**: Complete JSON-RPC implementation with discovery, authentication, and tool execution
- **Credential Injection**: Stateless architecture with Juli's credential management
- **Natural Language Tools**: AI-powered tool design with GPT-5 integration
- **Approval Flows**: User approval for sensitive operations
- **Hybrid Integration**: Combining multiple services (Reclaim.ai + Nylas)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/Juli-AI/juli-calendar-agent.git
cd juli-calendar-agent

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the server
python scripts/run_server.py

# Server starts at http://localhost:5002
```

### Agent Quickstart (A2A JSON-RPC)

1. **Discover the agent**:
```bash
curl http://localhost:5002/.well-known/a2a.json
```

2. **Get credential requirements**:
```bash
curl http://localhost:5002/.well-known/a2a-credentials.json
```

3. **Execute a tool**:
```bash
curl -X POST http://localhost:5002/a2a/rpc \
  -H "Content-Type: application/json" \
  -H "X-A2A-Dev-Secret: your-dev-secret" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tool.execute",
    "params": {
      "tool": "manage_productivity",
      "arguments": {
        "action": "create",
        "query": "Create a task to review the proposal"
      },
      "user_context": {
        "credentials": {
          "RECLAIM_API_KEY": "your_api_key_here",
          "NYLAS_GRANT_ID": "..."
        },
        "timezone": "America/New_York"
      }
    }
  }'
```

### Required Environment Variables

```bash
# AI Provider
OPENAI_API_KEY=sk-proj-...

# Calendar Integration (Nylas)
NYLAS_CLIENT_ID=...
NYLAS_API_KEY=nyk_v0_...
NYLAS_CALLBACK_URI=http://localhost:5002/api/nylas-calendar/callback

# Task Management (Reclaim.ai)
RECLAIM_API_KEY=your_api_key_here

# A2A Configuration
A2A_PUBLIC_BASE_URL=http://localhost:5002
A2A_DEV_SECRET=your-dev-secret  # Optional for development
```

### OAuth Setup (Nylas)

1. **Get the OAuth URL**:
```bash
curl http://localhost:5002/setup/connect-url
```

2. **Complete authentication** in your browser

3. **Receive grant_id** from callback:
```json
{
  "success": true,
  "grant_id": "...",
  "email": "user@example.com"
}
```

## 📚 Documentation

- [**Developer Guide**](docs/DEVELOPER_GUIDE.md) - Build and contribute to Juli agents
- [**Setup Guide**](docs/SETUP_GUIDE.md) - Detailed setup instructions
- [**A2A Protocol Guide**](docs/A2A_DEVELOPER_GUIDE.md) - Complete A2A implementation reference
- [**Tools Documentation**](docs/TOOLS_DOCUMENTATION.md) - All available tools and their parameters
- [**Approval System**](docs/APPROVAL_SYSTEM_GUIDE.md) - How the approval flow works
- [**Integration Details**](docs/INTEGRATION_DETAILS.md) - Reclaim.ai and Nylas specifics
- [**Docker Guide**](docs/DOCKER_GUIDE.md) - Container deployment instructions

## 🏗️ Architecture

```
┌─────────────┐     JSON-RPC      ┌──────────────┐
│  Juli Brain │ ◄──────────────► │ Calendar Agent│
└─────────────┘                   └──────┬───────┘
                                         │
                     ┌───────────────────┼───────────────────┐
                     │                   │                   │
              ┌──────▼──────┐    ┌──────▼──────┐   ┌────────▼────────┐
              │   GPT-5     │    │  Reclaim.ai │   │     Nylas      │
              │  (OpenAI)   │    │   (Tasks)   │   │  (Calendar)    │
              └─────────────┘    └─────────────┘   └────────────────┘
```

### Key Components

- **A2A Protocol Handler** (`src/a2a/`): Implements the complete A2A specification
- **Tool System** (`src/tools/`): Natural language tools for calendar and task operations
- **AI Integration** (`src/ai/`): GPT-4 powered intent routing and natural language processing
- **Approval System**: User approval for operations affecting others or causing conflicts
- **OAuth Flow**: Secure calendar connection via Nylas Hosted Auth

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run E2E tests
pytest tests/e2e/

# Run all tests
pytest
```

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up

# Or build manually
docker build -t juli-calendar-agent .
docker run -p 5002:5002 --env-file .env juli-calendar-agent
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Reclaim.ai](https://reclaim.ai) for intelligent task management
- Powered by [Nylas](https://nylas.com) for universal calendar access
- AI capabilities via [OpenAI](https://openai.com) GPT-4
- Part of the [Juli AI](https://juli.ai) ecosystem

## 📞 Support

- **Documentation**: [Full docs](docs/)
- **Issues**: [GitHub Issues](https://github.com/Juli-AI/juli-calendar-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Juli-AI/juli-calendar-agent/discussions)
- **Juli Support**: [support@juli.ai](mailto:support@juli.ai)